import asyncio
import logging
import time
from typing import Tuple

from httpcore import ConnectError
from httpx import PoolTimeout
from sqlalchemy import and_
from sqlalchemy import exists
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from abstract import NoPriceFound
from celery_app.tasks import fill_up_bundle
from celery_app.tasks import monitor_bundle
from db.base import Session
from db.models import BundleStatus
from db.models import Coin
from db.models import CoinNetworkExchange
from db.models import Exchange
from db.models import Network
from db.models import Pair
from db.models import PairExchange
from db.models import ProfitBundle
from db.models import ProfitBundleItem

from .price_analyzer import PriceAnalyzer


log = logging.getLogger("output")
error_log = logging.getLogger("error")


class ExchangePairAnalyzer:
    BASE_USDT_PROFIT = 4  # 4 USDT

    def __init__(self, base_exchange, pair_exchange):
        self.base_exchange = base_exchange
        self.pair_exchange = pair_exchange

    async def manage_pair(self, pair):
        base_to_second_network, second_to_base_network = self._get_best_networks(pair.base_coin)
        if not base_to_second_network and not second_to_base_network:
            log.info(f"no network found - {pair.default_name}")
            return

        try:
            base_exchange_price = await self.base_exchange.async_get_price(pair)
            pair_exchange_price = await self.pair_exchange.async_get_price(pair)
        except NoPriceFound:
            log.info(f"no price found - {pair.default_name}")
            return
        except (PoolTimeout, ConnectError):
            error_log.error(f"connection error - {pair.default_name}")
            return
        except Exception as e:
            error_log.error(f"unknown error getting price - {e} - {pair.default_name}")
            return

        if base_to_second_network and base_to_second_network.withdraw_fee:
            buy_price_analyzer = PriceAnalyzer(
                buy_price=base_exchange_price[0],
                sell_price=pair_exchange_price[1],
                network=base_to_second_network,
            )
            try:
                buy_price_analyzer.run()
            except Exception as e:
                error_log.exception(e)

            if buy_price_analyzer.profit > self.BASE_USDT_PROFIT:
                await self._start_monitoring(pair, buy_price_analyzer)

        if second_to_base_network and second_to_base_network.withdraw_fee:
            sell_price_analyzer = PriceAnalyzer(
                buy_price=pair_exchange_price[0],
                sell_price=base_exchange_price[1],
                network=second_to_base_network,
            )
            try:
                sell_price_analyzer.run()
            except Exception as e:
                error_log.exception(e)

            if sell_price_analyzer.profit > self.BASE_USDT_PROFIT:
                await self._start_monitoring(pair, sell_price_analyzer, from_base=False)

    async def run(self):
        """
        Limits - Bitget (20r/1s, 1r/0.05s); OKX (20r/1s)
        """
        running_tasks = set()
        loop = asyncio.get_event_loop()
        common_pairs = self._get_common_pairs()
        log.info(f"Found {len(common_pairs)} common pairs")
        if len(common_pairs) == 0:
            log.info("Sleeping for 5 seconds, waiting for sync scripts to run")
            time.sleep(5)

        for pair in common_pairs:
            task = loop.create_task(self.manage_pair(pair))
            if self.base_exchange.NAME in ["Mexc"] or self.pair_exchange.NAME in ["Mexc"]:
                await asyncio.sleep(0.12)
            elif self.base_exchange.NAME in ["OKX"] or self.pair_exchange.NAME in ["OKX"]:
                await asyncio.sleep(0.09)
            elif self.base_exchange.NAME in ["Bitget", "Bingx"] or self.pair_exchange.NAME in ["Bitget", "Bingx"]:
                await asyncio.sleep(0.07)
            elif self.base_exchange.NAME in ["GateIO"] or self.pair_exchange.NAME in ["GateIO"]:
                await asyncio.sleep(0.053)
            elif self.base_exchange.NAME in ["KuCoin"] or self.pair_exchange.NAME in ["KuCoin"]:
                await asyncio.sleep(0.028)
            elif self.base_exchange.NAME in ["Huobi"] or self.pair_exchange.NAME in ["Huobi"]:
                await asyncio.sleep(0.02)
            else:
                await asyncio.sleep(0.01)

            running_tasks.add(task)

        while running_tasks:
            done, pending = await asyncio.wait(running_tasks, timeout=0.5)
            running_tasks.difference_update(done)

    def _get_common_pairs(self):
        with Session() as session:
            subquery = (
                session.query(PairExchange.pair_id).join(Exchange).filter(Exchange.id == self.base_exchange.get_db_id())
            )
            pairs = (
                session.query(Pair)
                .join(PairExchange)
                .join(Exchange)
                .filter(Exchange.id == self.pair_exchange.get_db_id(), Pair.id.in_(subquery))
                .options(joinedload(Pair.base_coin), joinedload(Pair.quote_coin))
                .all()
            )
            return pairs

    def _get_best_networks(self, coin: Coin) -> Tuple[CoinNetworkExchange, CoinNetworkExchange]:
        with Session() as session:
            query = (
                session.query(CoinNetworkExchange.base_network_id, func.array_agg(CoinNetworkExchange.id))
                .join(Exchange)
                .join(Coin)
                .filter(
                    Exchange.id.in_([self.pair_exchange.get_db_id(), self.base_exchange.get_db_id()]),
                    Coin.name == coin.name,
                )
                .group_by(CoinNetworkExchange.base_network_id)
                .having(func.count(CoinNetworkExchange.id) == 2)
            )

            nets_mapping = {}
            for network_id, coin_network_exchange_ids in query:
                network: Network = session.query(Network).get(network_id)
                coin_network_exchange_qs = (
                    session.query(CoinNetworkExchange)
                    .filter(CoinNetworkExchange.id.in_(coin_network_exchange_ids))
                    .options(
                        joinedload(CoinNetworkExchange.exchange),
                        joinedload(CoinNetworkExchange.network),
                        joinedload(CoinNetworkExchange.base_network),
                        joinedload(CoinNetworkExchange.coin),
                    )
                )
                nets_mapping[network.name] = {
                    coin_network_exchange.exchange.name: coin_network_exchange
                    for coin_network_exchange in coin_network_exchange_qs
                }

        available_nets_to_transfer_from_base_to_second = [
            cne_mapping[self.base_exchange.NAME]
            for net_name, cne_mapping in nets_mapping.items()
            if len(cne_mapping) == 2
            and cne_mapping[self.base_exchange.NAME].can_withdraw
            and cne_mapping[self.pair_exchange.NAME].can_deposit
        ]
        available_nets_to_transfer_from_second_to_base = [
            cne_mapping[self.pair_exchange.NAME]
            for net_name, cne_mapping in nets_mapping.items()
            if len(cne_mapping) == 2
            and cne_mapping[self.pair_exchange.NAME].can_withdraw
            and cne_mapping[self.base_exchange.NAME].can_deposit
        ]

        if available_nets_to_transfer_from_base_to_second:
            best_base_to_second_network = min(
                available_nets_to_transfer_from_base_to_second,
                key=lambda cne: (cne.confirmations_needed * cne.network.block_creation_time)
                if cne.confirmations_needed and cne.network.block_creation_time
                else cne.withdraw_fee,
            )
        else:
            best_base_to_second_network = None

        if available_nets_to_transfer_from_second_to_base:
            best_second_to_base_network = min(
                available_nets_to_transfer_from_second_to_base,
                key=lambda cne: (cne.confirmations_needed * cne.network.block_creation_time)
                if cne.confirmations_needed and cne.network.block_creation_time
                else cne.withdraw_fee,
            )
        else:
            best_second_to_base_network = None

        return best_base_to_second_network, best_second_to_base_network

    async def _start_monitoring(self, pair, price_analyzer: PriceAnalyzer, from_base=True):
        if from_base:
            from_exchange, to_exchange = self.base_exchange, self.pair_exchange
        else:
            from_exchange, to_exchange = self.pair_exchange, self.base_exchange

        with Session() as session:
            same_processing_bundle = session.query(
                exists().where(
                    and_(
                        ProfitBundle.status == BundleStatus.in_progress,
                        ProfitBundle.coin_network_exchange_id == price_analyzer.coin_network_exchange.id,
                        ProfitBundle.pair_id == pair.id,
                        ProfitBundle.base_exchange_id == from_exchange.get_db_id(),
                        ProfitBundle.pair_exchange_id == to_exchange.get_db_id(),
                    ),
                ),
            ).scalar()
            if same_processing_bundle:
                return False

            deposit_coin_network_exchange = (
                session.query(CoinNetworkExchange)
                .filter(
                    CoinNetworkExchange.exchange_id == to_exchange.get_db_id(),
                    CoinNetworkExchange.coin_id == price_analyzer.coin_network_exchange.coin_id,
                    CoinNetworkExchange.base_network_id == price_analyzer.coin_network_exchange.base_network_id,
                )
                .first()
            )
            if not deposit_coin_network_exchange:
                error_log.error("Error in setting up deposit cne")
                return False

            if (
                deposit_coin_network_exchange.confirmations_needed
                and deposit_coin_network_exchange.base_network.block_creation_time
            ):
                network_speed = (
                    deposit_coin_network_exchange.confirmations_needed
                    * deposit_coin_network_exchange.base_network.block_creation_time
                    / 60
                )
            else:
                network_speed = None

            bundle = ProfitBundle()
            bundle.pair_id = pair.id
            bundle.coin_network_exchange_id = price_analyzer.coin_network_exchange.id
            bundle.base_exchange_id = from_exchange.get_db_id()
            bundle.pair_exchange_id = to_exchange.get_db_id()
            bundle.network_speed = network_speed

            bundle_item = ProfitBundleItem(**price_analyzer.to_db())
            bundle.items.append(bundle_item)

            session.add_all([bundle_item, bundle])
            session.flush()

            bundle_id = bundle.id
            session.commit()

            fill_up_bundle.apply_async(args=[bundle_id], countdown=5)
            monitor_bundle.apply_async(args=[bundle_id], countdown=10)

        return True
