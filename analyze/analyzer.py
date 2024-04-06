import asyncio
import logging
import time
from collections import defaultdict
from typing import Generator
from typing import Tuple
from typing import Union

from httpcore import ConnectError
from httpx import PoolTimeout
from sqlalchemy import and_
from sqlalchemy import exists
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import contains_eager
from sqlalchemy.orm import joinedload

from abstract import NoPriceFound
from abstract.abstract import AbstractExchange
from celery_app.tasks import fill_up_bundle
from celery_app.tasks import monitor_bundle
from db.base import AsyncSession
from db.base import Session
from db.models import BundleStatus
from db.models import Coin
from db.models import CoinNetworkExchange
from db.models import Exchange
from db.models import Pair
from db.models import PairExchange
from db.models import ProfitBundle
from db.models import ProfitBundleItem
from db.models import Whitelist

from .price_analyzer import PriceAnalyzer


log = logging.getLogger("output")
error_log = logging.getLogger("error")
best_cne_T = Union[dict[str, CoinNetworkExchange], None]


class ExchangePairAnalyzer:
    BASE_USDT_PROFIT = 4  # 4 USDT

    def __init__(self, base_exchange, pair_exchange):
        self.base_exchange: AbstractExchange = base_exchange
        self.pair_exchange: AbstractExchange = pair_exchange

    async def run(self):
        running_tasks = set()
        loop = asyncio.get_event_loop()
        common_pairs = self._get_common_pairs()

        for pair in common_pairs:
            task = loop.create_task(self.manage_pair(pair))
            running_tasks.add(task)

        log.info(f"Found {len(running_tasks)} common pairs")
        if len(running_tasks) == 0:
            log.info("Sleeping for 5 seconds, waiting for sync scripts to run")
            time.sleep(5)

        while running_tasks:
            done, pending = await asyncio.wait(running_tasks, timeout=0.5)
            running_tasks.difference_update(done)

    async def manage_pair(self, pair_data: dict[str, Union[Pair, dict[str, float]]]):
        pair = pair_data["pair"]
        from_base_net_mapping, from_second_net_mapping = await self._get_best_networks(pair.base_coin)
        if not from_base_net_mapping and not from_second_net_mapping:
            log.info(f"no network found - {pair.default_name}")
            return

        try:
            async with self.base_exchange.async_limiter:
                base_exchange_price = await self.base_exchange.async_get_price(pair)

            async with self.pair_exchange.async_limiter:
                pair_exchange_price = await self.pair_exchange.async_get_price(pair)

        except NoPriceFound:
            log.info(f"no price found - {pair.default_name}")
            return
        except (PoolTimeout, ConnectError):
            error_log.error(
                f"[{self.base_exchange.NAME};{self.pair_exchange.NAME}] connection error - {pair.default_name}",
            )
            return
        except Exception as e:
            error_log.error(
                f"[{self.base_exchange.NAME};{self.pair_exchange.NAME}] unknown error getting price - {e} - {pair.default_name}",
            )
            return

        if from_base_net_mapping:
            withdraw_cne = from_base_net_mapping[self.base_exchange.NAME]
            deposit_cne = from_base_net_mapping[self.pair_exchange.NAME]

            if withdraw_cne.exchange.active_buy and deposit_cne.exchange.active_sell:
                buy_price_analyzer = PriceAnalyzer(
                    buy_price=base_exchange_price[0],
                    sell_price=pair_exchange_price[1],
                    spot_buy_fee=pair_data["taker_fees"][self.base_exchange.NAME],
                    spot_sell_fee=pair_data["taker_fees"][self.pair_exchange.NAME],
                    withdraw_cne=withdraw_cne,
                    deposit_cne=deposit_cne,
                )
                try:
                    buy_price_analyzer.run()
                except Exception as e:
                    error_log.exception(e)

                is_withdrawable = self._check_withdraw_limits(
                    ccy_quantity_to_withdraw=buy_price_analyzer.user_based_coin_available_amount,
                    withdraw_cne=withdraw_cne,
                    deposit_cne=deposit_cne,
                )

                if buy_price_analyzer.user_based_profit > self.BASE_USDT_PROFIT and is_withdrawable:
                    await self._start_monitoring(pair, buy_price_analyzer)

        if from_second_net_mapping:
            withdraw_cne = from_second_net_mapping[self.pair_exchange.NAME]
            deposit_cne = from_second_net_mapping[self.base_exchange.NAME]

            if withdraw_cne.exchange.active_buy and deposit_cne.exchange.active_sell:
                sell_price_analyzer = PriceAnalyzer(
                    buy_price=pair_exchange_price[0],
                    sell_price=base_exchange_price[1],
                    spot_buy_fee=pair_data["taker_fees"][self.pair_exchange.NAME],
                    spot_sell_fee=pair_data["taker_fees"][self.base_exchange.NAME],
                    withdraw_cne=withdraw_cne,
                    deposit_cne=deposit_cne,
                )
                try:
                    sell_price_analyzer.run()
                except Exception as e:
                    error_log.exception(e)

                is_withdrawable = self._check_withdraw_limits(
                    ccy_quantity_to_withdraw=sell_price_analyzer.user_based_coin_available_amount,
                    withdraw_cne=withdraw_cne,
                    deposit_cne=deposit_cne,
                )

                if sell_price_analyzer.user_based_profit > self.BASE_USDT_PROFIT and is_withdrawable:
                    await self._start_monitoring(pair, sell_price_analyzer)

    @staticmethod
    def _check_withdraw_limits(
        ccy_quantity_to_withdraw: float,
        withdraw_cne: CoinNetworkExchange,
        deposit_cne: CoinNetworkExchange,
    ) -> bool:
        if withdraw_cne.withdraw_max:
            can_withdraw = withdraw_cne.withdraw_min < ccy_quantity_to_withdraw < withdraw_cne.withdraw_max
        else:
            can_withdraw = withdraw_cne.withdraw_min < ccy_quantity_to_withdraw

        if deposit_cne.deposit_min:
            can_withdraw = can_withdraw and ccy_quantity_to_withdraw > deposit_cne.deposit_min

        return can_withdraw

    def _get_common_pairs(self) -> Generator[dict[str, Union[Pair, dict[str, float]]], None, None]:
        with Session() as session:
            subq = (
                session.query(Pair.id)
                .join(PairExchange)
                .join(Exchange)
                .filter(Exchange.name.in_([self.base_exchange.NAME, self.pair_exchange.NAME]))
                .group_by(Pair.id)
                .having(func.count(PairExchange.id) == 2)
            )
            pairs = (
                session.query(Pair, Exchange.name, PairExchange.taker_fee)
                .select_from(Pair)
                .join(PairExchange)
                .join(Exchange)
                .filter(Pair.id.in_(subq), Exchange.name.in_([self.base_exchange.NAME, self.pair_exchange.NAME]))
                .options(joinedload(Pair.base_coin), joinedload(Pair.quote_coin))
                .order_by(Pair.id)
                .all()
            )

        for idx in range(0, len(pairs), 2):
            pair, exchange_name1, taker_fee1 = pairs[idx]
            _, exchange_name2, taker_fee2 = pairs[idx + 1]
            yield {
                "pair": pair,
                "taker_fees": {
                    exchange_name1: taker_fee1,
                    exchange_name2: taker_fee2,
                },
            }

    async def _get_best_networks(self, coin: Coin) -> Tuple[best_cne_T, best_cne_T]:
        async with AsyncSession() as session:
            subq = (
                select(CoinNetworkExchange.base_network_id)
                .join(Exchange)
                .where(CoinNetworkExchange.coin_id == coin.id)
                .where(Exchange.name.in_([self.base_exchange.NAME, self.pair_exchange.NAME]))
                .group_by(CoinNetworkExchange.base_network_id)
                .having(func.count(CoinNetworkExchange.id) == 2)
            )
            coin_network_exchange_qs = await session.scalars(
                select(CoinNetworkExchange)
                .join(CoinNetworkExchange.exchange)
                .where(CoinNetworkExchange.base_network_id.in_(subq))
                .where(CoinNetworkExchange.coin_id == coin.id)
                .where(Exchange.name.in_([self.base_exchange.NAME, self.pair_exchange.NAME]))
                .options(
                    contains_eager(CoinNetworkExchange.exchange),
                    joinedload(CoinNetworkExchange.network),
                    joinedload(CoinNetworkExchange.base_network),
                    joinedload(CoinNetworkExchange.coin),
                ),
            )

        nets_mapping = defaultdict(dict)
        for cne in coin_network_exchange_qs:
            nets_mapping[cne.base_network.name][cne.exchange.name] = cne

        best_base_to_second_network = self._get_best_cne(
            self.base_exchange.NAME,
            self.pair_exchange.NAME,
            nets_mapping,
        )
        best_second_to_base_network = self._get_best_cne(
            self.pair_exchange.NAME,
            self.base_exchange.NAME,
            nets_mapping,
        )

        return best_base_to_second_network, best_second_to_base_network

    @staticmethod
    def _get_best_cne(
        withdraw_exchange_name: str,
        deposit_exchange_name: str,
        cnes_mapping: dict[str, [dict[str, CoinNetworkExchange]]],
    ) -> best_cne_T:
        available_cne_mapping = []
        for _, cne_mapping in cnes_mapping.items():
            if (
                cne_mapping[withdraw_exchange_name].can_withdraw
                and cne_mapping[withdraw_exchange_name].withdraw_fee
                and cne_mapping[deposit_exchange_name].can_deposit
            ):
                available_cne_mapping.append(cne_mapping)
            # else:
            #     log.info(
            #         f"{cne_mapping[withdraw_exchange_name].coin.name} "
            #         f"- {cne_mapping[withdraw_exchange_name].base_network.name} is closed",
            #     )

        if not available_cne_mapping:
            return None

        best_cne = min(
            available_cne_mapping,
            key=lambda cne_map: (
                cne_map[deposit_exchange_name].confirmations_needed
                * cne_map[deposit_exchange_name].network.block_creation_time
            )
            if cne_map[deposit_exchange_name].confirmations_needed
            and cne_map[deposit_exchange_name].network.block_creation_time
            else cne_map[withdraw_exchange_name].withdraw_fee,
        )
        return best_cne

    @staticmethod
    async def _start_monitoring(pair: Pair, price_analyzer: PriceAnalyzer):
        async with AsyncSession() as session:
            same_processing_bundle = await session.scalar(
                select(
                    exists().where(
                        and_(
                            ProfitBundle.status == BundleStatus.in_progress,
                            ProfitBundle.withdraw_coin_network_exchange_id == price_analyzer.withdraw_cne.id,
                            ProfitBundle.deposit_coin_network_exchange_id == price_analyzer.deposit_cne.id,
                            ProfitBundle.pair_id == pair.id,
                        ),
                    ),
                ),
            )
            if same_processing_bundle:
                return False

            if not price_analyzer.deposit_cne:
                error_log.error("Error in setting up deposit cne")
                return False

            if (
                price_analyzer.deposit_cne.confirmations_needed
                and price_analyzer.deposit_cne.base_network.block_creation_time
            ):
                network_speed = (
                    price_analyzer.deposit_cne.confirmations_needed
                    * price_analyzer.deposit_cne.base_network.block_creation_time
                    / 60
                )
            else:
                network_speed = None

            bundle = ProfitBundle()
            bundle.pair_id = pair.id
            bundle.withdraw_coin_network_exchange_id = price_analyzer.withdraw_cne.id
            bundle.deposit_coin_network_exchange_id = price_analyzer.deposit_cne.id
            bundle.base_exchange_id = price_analyzer.withdraw_cne.exchange_id
            bundle.pair_exchange_id = price_analyzer.deposit_cne.exchange_id
            bundle.network_speed = network_speed
            bundle.spot_buy_fee = price_analyzer.spot_buy_fee
            bundle.spot_sell_fee = price_analyzer.spot_sell_fee
            bundle.back_way_network_fee = price_analyzer.back_way_network_fee
            bundle.is_checked = price_analyzer.withdraw_cne.is_checked and price_analyzer.deposit_cne.is_checked
            bundle.is_whitelisted = await session.scalar(
                select(
                    exists().where(
                        and_(
                            bundle.base_exchange_id == Whitelist.withdraw_exchange_id,
                            bundle.pair_exchange_id == Whitelist.deposit_exchange_id,
                            price_analyzer.withdraw_cne.base_network_id == Whitelist.base_network_id,
                        ),
                    ),
                ),
            )

            bundle_item = ProfitBundleItem(**price_analyzer.to_db())
            bundle.items.append(bundle_item)

            session.add_all([bundle_item, bundle])
            await session.flush()

            bundle_id = bundle.id
            await session.commit()

            fill_up_bundle.apply_async(args=[bundle_id], countdown=5)
            monitor_bundle.apply_async(args=[bundle_id], countdown=10)

        return True
