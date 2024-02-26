import logging

from celery import Task
from celery.exceptions import MaxRetriesExceededError
from dotenv import dotenv_values
from sqlalchemy.orm import joinedload

from analyze.price_analyzer import PriceAnalyzer
from celery_app.conf import app
from db.base import Session
from db.models import Pair, CoinNetworkExchange, ProfitBundle, ProfitBundleItem, BundleStatus
from exchanges import BinanceAPI, BybitAPI, OkxAPI, GateIOAPI, HuobiAPI, KuCoinAPI, BitgetAPI
from services.send_analytics_service import SendAnalyticsService

config = dotenv_values(".env")

exchange_mapping = {
    BinanceAPI.NAME: BinanceAPI,
    BybitAPI.NAME: BybitAPI,
    HuobiAPI.NAME: HuobiAPI,
    GateIOAPI.NAME: GateIOAPI,
    OkxAPI.NAME: OkxAPI,
    KuCoinAPI.NAME: KuCoinAPI,
    BitgetAPI.NAME: BitgetAPI,
}

BASE_USDT_PROFIT = 2  # 2 USDT

error_log = logging.getLogger("error")


@app.task(bind=True, max_retries=100)  # if all retires are used, it takes 40 minutes to go off
def monitor_bundle(self: Task, bundle_id):
    with Session() as session:
        bundle = (
            session.query(ProfitBundle)
            .options(
                joinedload(ProfitBundle.coin_network_exchange),
                joinedload(ProfitBundle.coin_network_exchange).joinedload(CoinNetworkExchange.network),
                joinedload(ProfitBundle.pair),
                joinedload(ProfitBundle.pair).joinedload(Pair.base_coin),
                joinedload(ProfitBundle.pair).joinedload(Pair.quote_coin),
                joinedload(ProfitBundle.base_exchange),
                joinedload(ProfitBundle.pair_exchange),
            )
            .get(bundle_id)
        )

    base_exchange = exchange_mapping[bundle.base_exchange.name](config, {})
    pair_exchange = exchange_mapping[bundle.pair_exchange.name](config, {})

    if bundle.buy_price_snapshot:
        base_exchange_price = bundle.buy_price_snapshot, []
    else:
        base_exchange_price = base_exchange.get_price(bundle.pair)
    pair_exchange_price = pair_exchange.get_price(bundle.pair)

    price_analyzer = PriceAnalyzer(
        buy_price=base_exchange_price[0], sell_price=pair_exchange_price[1], network=bundle.coin_network_exchange
    )
    try:
        price_analyzer.run()
    except Exception as e:
        error_log.exception(e)
        return

    if price_analyzer.profit > BASE_USDT_PROFIT and price_analyzer.avg_spread >= 0.003:
        with Session() as session:
            bundle_item = ProfitBundleItem(**price_analyzer.to_db())
            bundle_item.profit_bundle_id = bundle.id
            if self.request.retries == 9:
                session.query(ProfitBundle).filter(ProfitBundle.id == bundle_id).update(
                    {"buy_price_snapshot": base_exchange_price[0]}, synchronize_session=False
                )
            session.add(bundle_item)
            session.commit()

        try:
            if self.request.retries < 60:  # for first 10 minutes
                raise self.retry(countdown=10)
            elif self.request.retries < 80:  # for next 10 minutes
                raise self.retry(countdown=30)
            else:
                raise self.retry(countdown=60)
        except MaxRetriesExceededError:
            pass

    # if bundle comes to this point, then it's over retried or isn't anymore profitable
    with Session() as session:
        session.query(ProfitBundle).filter(ProfitBundle.id == bundle_id).update(
            {"status": BundleStatus.done}, synchronize_session=False
        )
        session.commit()


@app.task
def set_bundle_volume_statistics(bundle_id):
    with Session() as session:
        bundle = (
            session.query(ProfitBundle)
            .options(
                joinedload(ProfitBundle.pair),
                joinedload(ProfitBundle.pair).joinedload(Pair.base_coin),
                joinedload(ProfitBundle.pair).joinedload(Pair.quote_coin),
                joinedload(ProfitBundle.base_exchange),
                joinedload(ProfitBundle.pair_exchange),
            )
            .get(bundle_id)
        )

        base_exchange = exchange_mapping[bundle.base_exchange.name](config, {})
        pair_exchange = exchange_mapping[bundle.pair_exchange.name](config, {})

        base_exchange_trading_volume = base_exchange.get_pair_trading_volume(bundle.pair)
        pair_exchange_trading_volume = pair_exchange.get_pair_trading_volume(bundle.pair)

        session.query(ProfitBundle).filter(ProfitBundle.id == bundle_id).update(
            {
                "base_exchange_trading_volume": base_exchange_trading_volume,
                "pair_exchange_trading_volume": pair_exchange_trading_volume,
            },
            synchronize_session=False,
        )
        session.commit()


@app.task
def send_analytics():
    service = SendAnalyticsService(config)
    service.send_to_spreadsheet()
