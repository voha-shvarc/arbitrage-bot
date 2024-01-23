import logging
import time
from typing import Tuple

from sqlalchemy import func, exists, and_
from sqlalchemy.orm import joinedload

from celery_app.tasks import monitor_bundle
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
from exchanges.abstract import NoPriceFound
from .price_analyzer import PriceAnalyzer

log = logging.getLogger("output")
error_log = logging.getLogger("error")


class ExchangePairAnalyzer:
    BASE_USDT_PROFIT = 4  # 4 USDT
    MIN_LIQUID_AMOUNT = 500  # 500 USDT

    def __init__(self, base_exchange, pair_exchange):
        self.base_exchange = base_exchange
        self.pair_exchange = pair_exchange

    def run(self):
        common_pairs = self._get_common_pairs()
        log.info(f"Found {len(common_pairs)} common pairs")
        if len(common_pairs) == 0:
            log.info("Sleeping for 5 seconds, waiting for sync scripts to run")
            time.sleep(5)

        for pair in common_pairs:
            log.info(f"processing {pair.default_name}")

            base_to_second_network, second_to_base_network = self._get_best_networks(pair.base_coin)
            if not base_to_second_network and not second_to_base_network:
                log.info("no network found")
                continue

            try:
                base_exchange_price = self.base_exchange.get_price(pair)
                pair_exchange_price = self.pair_exchange.get_price(pair)
            except NoPriceFound:
                log.info("skip")
                continue

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
                session.query(CoinNetworkExchange.network_id, func.array_agg(CoinNetworkExchange.id))
                .join(Exchange)
                .join(Coin)
                .filter(Exchange.id.in_([self.pair_exchange.db_id, self.base_exchange.db_id]), Coin.name == coin.name)
                .group_by(CoinNetworkExchange.network_id)
                .having(func.count(CoinNetworkExchange.id) == 2)
            )

            nets_mapping = {}
            for network_id, coin_network_exchange_ids in query:
                network: Network = session.query(Network).get(network_id)
                coin_network_exchange_qs = (
                    session.query(Exchange.name, CoinNetworkExchange)
                    .join(Exchange)
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

        best_base_to_second_network = min(
            available_nets_to_transfer_from_base_to_second or [None],
            key=lambda net: net.withdraw_fee if net else None,
        )
        best_second_to_base_network = min(
            available_nets_to_transfer_from_second_to_base or [None],
            key=lambda net: net.withdraw_fee if net else None,
        )

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

            monitor_bundle.apply_async(args=[bundle.id], countdown=90)
            session.commit()

        return True
