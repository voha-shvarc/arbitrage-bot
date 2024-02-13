import logging
import time
from typing import Tuple

import asyncio
from sqlalchemy import func, exists, and_
from sqlalchemy.orm import joinedload

from abstract import NoPriceFound
from celery_app.tasks import monitor_bundle
from celery_app.tasks import monitor_bundle, set_bundle_volume_statistics
from db.base import Session
from db.models import (
    Pair,
    Exchange,
    CoinNetworkExchange,
    Coin,
    Network,
    PairExchange,
    ProfitBundle,
    ProfitBundleItem,
    BundleStatus,
)
from abstract import NoPriceFound
from .price_analyzer import PriceAnalyzer

log = logging.getLogger("output")
error_log = logging.getLogger("error")


class ExchangePairAnalyzer:
    BASE_USDT_PROFIT = 4  # 4 USDT
    MIN_LIQUID_AMOUNT = 500  # 500 USDT

    def __init__(self, base_exchange, pair_exchange):
        self.base_exchange = base_exchange
        self.pair_exchange = pair_exchange

    async def manage_pair(self, pair):
        try:
            base_exchange_price = await self.base_exchange.async_get_price(pair)
            pair_exchange_price = await self.pair_exchange.async_get_price(pair)
        except NoPriceFound:
            log.info("skip")
            return

        base_to_second_network, second_to_base_network = self._get_best_networks(pair.base_coin)
        if not base_to_second_network and not second_to_base_network:
            log.info("no network found")
            return

        if base_to_second_network and self.base_exchange.NAME != "GateIO":
            buy_price_analyzer = PriceAnalyzer(
                buy_price=base_exchange_price[0],
                sell_price=pair_exchange_price[1],
                network=base_to_second_network,
            )
            try:
                buy_price_analyzer.run()
            except Exception as e:
                error_log.exception(e)

            if (
                    buy_price_analyzer.profit > self.BASE_USDT_PROFIT
                    and buy_price_analyzer.to_use_usdt > self.MIN_LIQUID_AMOUNT
            ):
                self._start_monitoring(pair, buy_price_analyzer)

        if second_to_base_network and self.pair_exchange.NAME != "GateIO":
            sell_price_analyzer = PriceAnalyzer(
                buy_price=pair_exchange_price[0],
                sell_price=base_exchange_price[1],
                network=second_to_base_network,
            )
            try:
                sell_price_analyzer.run()
            except Exception as e:
                error_log.exception(e)

            if (
                    sell_price_analyzer.profit > self.BASE_USDT_PROFIT
                    and sell_price_analyzer.to_use_usdt > self.MIN_LIQUID_AMOUNT
            ):
                self._start_monitoring(pair, sell_price_analyzer, from_base=False)

    async def run(self):
        running_tasks = set()
        loop = asyncio.get_event_loop()
        common_pairs = self._get_common_pairs()
        log.info(f"Found {len(common_pairs)} common pairs")
        if len(common_pairs) == 0:
            log.info("Sleeping for 5 seconds, waiting for sync scripts to run")
            time.sleep(5)

        for pair in common_pairs:
            log.info(f"processing {pair.default_name}")
            task = loop.create_task(self.manage_pair(pair))
            if self.base_exchange.NAME in ["Bitget"] or self.pair_exchange.NAME in ["Bitget"]:
                await asyncio.sleep(0.9)
            elif self.base_exchange.NAME in ["OKX"] or self.pair_exchange.NAME in ["OKX"]:
                await asyncio.sleep(0.08)
            elif self.base_exchange.NAME in ["GateIO"] or self.pair_exchange.NAME in ["GateIO"]:
                await asyncio.sleep(0.053)
            elif self.base_exchange.NAME in ["KuCoin"] or self.pair_exchange.NAME in ["KuCoin"]:
                await asyncio.sleep(0.023)
            else:
                await asyncio.sleep(0.01)

            running_tasks.add(task)

        while running_tasks:
            done, pending = await asyncio.wait(running_tasks, timeout=0.5)
            running_tasks.difference_update(done)

    def _get_common_pairs(self):
        with Session() as session:
            subquery = (
                session.query(PairExchange.pair_id).join(Exchange).filter(Exchange.id == self.base_exchange.db_id)
            )
            pairs = (
                session.query(Pair)
                .join(PairExchange)
                .join(Exchange)
                .filter(Exchange.id == self.pair_exchange.db_id, Pair.id.in_(subquery))
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
                    Exchange.id.in_([self.pair_exchange.db_id, self.base_exchange.db_id]),
                    Coin.name == coin.name,
                )
                .group_by(CoinNetworkExchange.base_network_id)
                .having(func.count(CoinNetworkExchange.id) == 2)
            )

            nets_mapping = {}
            for network_id, coin_network_exchange_ids in query:
                network: Network = session.query(Network).get(network_id)
                coin_network_exchange_qs = (
                    session.query(Exchange.name, CoinNetworkExchange)
                    .join(CoinNetworkExchange.exchange)
                    .filter(CoinNetworkExchange.id.in_(coin_network_exchange_ids))
                    .options(joinedload(CoinNetworkExchange.network))
                )
                nets_mapping[network.name] = {
                    exchange_name: coin_network_exchange
                    for exchange_name, coin_network_exchange in coin_network_exchange_qs
                }

        available_nets_to_transfer_from_base_to_second = [
            nets[self.base_exchange.NAME]
            for net_name, nets in nets_mapping.items()
            if nets[self.base_exchange.NAME].can_withdraw and nets[self.pair_exchange.NAME].can_deposit
        ]
        available_nets_to_transfer_from_second_to_base = [
            nets[self.pair_exchange.NAME]
            for net_name, nets in nets_mapping.items()
            if nets[self.pair_exchange.NAME].can_withdraw and nets[self.base_exchange.NAME].can_deposit
        ]

        try:
            best_base_to_second_network = min(
                available_nets_to_transfer_from_base_to_second or [None],
                key=lambda net: net.withdraw_fee if net else None,
            )
        except TypeError:
            best_base_to_second_network = None

        try:
            best_second_to_base_network = min(
                available_nets_to_transfer_from_second_to_base or [None],
                key=lambda net: net.withdraw_fee if net else None,
            )
        except TypeError:
            best_second_to_base_network = None

        return best_base_to_second_network, best_second_to_base_network

    def _start_monitoring(self, pair, price_analyzer: PriceAnalyzer, from_base=True):
        if from_base:
            from_exchange_id, to_exchange_id = self.base_exchange.db_id, self.pair_exchange.db_id
        else:
            from_exchange_id, to_exchange_id = self.pair_exchange.db_id, self.base_exchange.db_id

        with Session() as session:
            same_processing_bundle = session.query(
                exists().where(
                    and_(
                        ProfitBundle.status == BundleStatus.in_progress,
                        ProfitBundle.coin_network_exchange_id == price_analyzer.network.id,
                        ProfitBundle.pair_id == pair.id,
                        ProfitBundle.base_exchange_id == from_exchange_id,
                        ProfitBundle.pair_exchange_id == to_exchange_id,
                    )
                )
            ).scalar()
            if same_processing_bundle:
                return False

            bundle = ProfitBundle()
            bundle.pair_id = pair.id
            bundle.coin_network_exchange_id = price_analyzer.network.id
            bundle.base_exchange_id = from_exchange_id
            bundle.pair_exchange_id = to_exchange_id

            bundle_item = ProfitBundleItem(**price_analyzer.to_db())
            bundle.items.append(bundle_item)

            session.add_all([bundle_item, bundle])
            session.flush()

            set_bundle_volume_statistics.apply_async(args=[bundle.id], countdown=5)
            monitor_bundle.apply_async(args=[bundle.id], countdown=90)
            session.commit()

        return True
