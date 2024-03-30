import asyncio
import logging

from aiogram import Bot
from celery import Task
from celery.exceptions import MaxRetriesExceededError
from dotenv import dotenv_values
from sqlalchemy.orm import joinedload

from analyze.price_analyzer import PriceAnalyzer
from celery_app.conf import app
from db.base import Session
from db.models import BundleStatus
from db.models import CoinNetworkExchange
from db.models import Pair
from db.models import ProfitBundle
from db.models import ProfitBundleItem
from exchanges import EXCHANGES_MAPPING
from services.send_analytics_service import SendAnalyticsService
from tgbot.config import load_config
from tgbot.keyboards.bundle import get_bundle_keyboard
from tgbot.services.broadcaster import send_message
from tgbot.services.messages import get_bundle_message


config = dotenv_values(".env")

BASE_USDT_PROFIT = 4  # 4 USDT
REFRESH_BASE_USDT_PROFIT = 2  # 2 USDT

error_log = logging.getLogger("error")


@app.task(bind=True, max_retries=100)  # it takes 40 minutes to use all the retires
def monitor_bundle(self: Task, bundle_id, force_refresh: bool = False):
    with Session() as session:
        bundle = (
            session.query(ProfitBundle)
            .options(
                joinedload(ProfitBundle.withdraw_coin_network_exchange),
                joinedload(ProfitBundle.withdraw_coin_network_exchange).joinedload(CoinNetworkExchange.exchange),
                joinedload(ProfitBundle.withdraw_coin_network_exchange).joinedload(CoinNetworkExchange.network),
                joinedload(ProfitBundle.pair),
                joinedload(ProfitBundle.pair).joinedload(Pair.base_coin),
                joinedload(ProfitBundle.pair).joinedload(Pair.quote_coin),
                joinedload(ProfitBundle.base_exchange),
                joinedload(ProfitBundle.pair_exchange),
            )
            .get(bundle_id)
        )

    base_exchange = EXCHANGES_MAPPING[bundle.base_exchange.name](config, {})
    pair_exchange = EXCHANGES_MAPPING[bundle.pair_exchange.name](config, {})

    if bundle.buy_price_snapshot and not force_refresh:
        base_exchange_price = bundle.buy_price_snapshot, []
    else:
        base_exchange_price = base_exchange.get_price(bundle.pair)
    pair_exchange_price = pair_exchange.get_price(bundle.pair)

    price_analyzer = PriceAnalyzer(
        buy_price=base_exchange_price[0],
        sell_price=pair_exchange_price[1],
        withdraw_cne=bundle.withdraw_coin_network_exchange,
    )
    try:
        price_analyzer.run()
    except Exception as e:
        error_log.exception(e)
        return

    if price_analyzer.profit > REFRESH_BASE_USDT_PROFIT and price_analyzer.avg_spread >= 0.005:
        with Session() as session:
            bundle_item = ProfitBundleItem(**price_analyzer.to_db())
            bundle_item.profit_bundle_id = bundle.id
            if force_refresh:
                session.query(ProfitBundle).filter(ProfitBundle.id == bundle_id).update(
                    {
                        "status": BundleStatus.in_progress,
                        "buy_price_snapshot": None,
                    },
                    synchronize_session=False,
                )
            elif self.request.retries == 9:
                session.query(ProfitBundle).filter(ProfitBundle.id == bundle_id).update(
                    {"buy_price_snapshot": base_exchange_price[0]},
                    synchronize_session=False,
                )
            session.add(bundle_item)
            session.commit()

        if force_refresh:
            send_tg_message.apply_async(args=[bundle_id], countdown=0.5)

        try:
            if self.request.retries < 60:  # for first 10 minutes
                raise self.retry(countdown=10, args=[bundle_id])
            elif self.request.retries < 80:  # for next 10 minutes
                raise self.retry(countdown=30, args=[bundle_id])
            else:
                raise self.retry(countdown=60, args=[bundle_id])
        except MaxRetriesExceededError:
            pass

    # if bundle comes to this point, then it's over retried or isn't anymore profitable
    with Session() as session:
        session.query(ProfitBundle).filter(ProfitBundle.id == bundle_id).update(
            {"status": BundleStatus.done},
            synchronize_session=False,
        )
        session.commit()


@app.task
def send_tg_message(bundle_id):
    with Session() as session:
        bundle = joinedload(ProfitBundleItem.profit_bundle)
        bundle_item: ProfitBundleItem = (
            session.query(ProfitBundleItem)
            .filter(ProfitBundleItem.profit_bundle_id == bundle_id)
            .options(
                bundle,
                bundle.joinedload(ProfitBundle.base_exchange),
                bundle.joinedload(ProfitBundle.pair_exchange),
                bundle.joinedload(ProfitBundle.pair),
                bundle.joinedload(ProfitBundle.pair).joinedload(Pair.base_coin),
                bundle.joinedload(ProfitBundle.pair).joinedload(Pair.quote_coin),
                bundle.joinedload(ProfitBundle.deposit_coin_network_exchange),
                bundle.joinedload(ProfitBundle.deposit_coin_network_exchange).joinedload(CoinNetworkExchange.network),
                bundle.joinedload(ProfitBundle.deposit_coin_network_exchange).joinedload(CoinNetworkExchange.coin),
                bundle.joinedload(ProfitBundle.withdraw_coin_network_exchange),
                bundle.joinedload(ProfitBundle.withdraw_coin_network_exchange).joinedload(CoinNetworkExchange.network),
                bundle.joinedload(ProfitBundle.withdraw_coin_network_exchange).joinedload(CoinNetworkExchange.coin),
                bundle.joinedload(ProfitBundle.withdraw_coin_network_exchange).joinedload(
                    CoinNetworkExchange.base_network,
                ),
            )
            .order_by(ProfitBundleItem.created_at.desc())
            .first()
        )

        bundle: ProfitBundle = bundle_item.profit_bundle

        message = get_bundle_message(bundle, bundle_item)
        config_tg = load_config(".env")
        bot = Bot(token=config_tg.tg_bot.token, parse_mode="HTML")
        send_message_tasks = [
            send_message(
                bot,
                user_id,
                message,
                reply_markup=get_bundle_keyboard(bundle_id, bundle.base_exchange.name, bundle.pair_exchange.name),
                disable_web_page_preview=True,
            )
            for user_id in config_tg.tg_bot.admin_ids
        ]

        async def send_messages():
            await asyncio.gather(*send_message_tasks)

        asyncio.run(send_messages())


@app.task
def fill_up_bundle(bundle_id):
    with Session() as session:
        bundle: ProfitBundle = (
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

        base_exchange = EXCHANGES_MAPPING[bundle.base_exchange.name](config, {})
        pair_exchange = EXCHANGES_MAPPING[bundle.pair_exchange.name](config, {})

        bundle.base_exchange_trading_volume = base_exchange.get_pair_trading_volume(bundle.pair)
        bundle.pair_exchange_trading_volume = pair_exchange.get_pair_trading_volume(bundle.pair)

        bundle.base_exchange_chart_change = base_exchange.get_pair_chart_change(bundle.pair)
        bundle.pair_exchange_chart_change = pair_exchange.get_pair_chart_change(bundle.pair)

        session.commit()

    send_tg_message.apply_async(args=[bundle_id], countdown=1)


@app.task
def send_analytics():
    service = SendAnalyticsService(config)
    service.send_to_spreadsheet()
