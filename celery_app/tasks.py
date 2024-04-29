import asyncio
import logging
import time

from aiogram import Bot
from celery import Task
from celery.exceptions import MaxRetriesExceededError
from dotenv import dotenv_values
from sqlalchemy import and_
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from analyze.price_analyzer import PriceAnalyzer
from celery_app.conf import app
from db.base import Session
from db.models import BundleStatus
from db.models import CoinNetworkExchange
from db.models import Pair
from db.models import PairExchange
from db.models import ProfitBundle
from db.models import ProfitBundleItem
from exchanges import EXCHANGES_MAPPING
from tgbot.config import load_config
from tgbot.keyboards.bundle import get_bundle_keyboard
from tgbot.services.broadcaster import send_message
from tgbot.services.messages import get_bundle_message


config = dotenv_values(".env")

BASE_USDT_PROFIT = 4  # 4 USDT
REFRESH_BASE_USDT_PROFIT = 2  # 2 USDT

log_file = "celery_tasks.log"
formatt = logging.Formatter("%(asctime)s - %(message)s")
logger = logging.getLogger("celery_tasks")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(log_file)
handler.setFormatter(formatt)
logger.addHandler(handler)


@app.task(bind=True, max_retries=100)  # it takes 40 minutes to use all the retires
def monitor_bundle(self: Task, bundle_id, force_refresh: bool = False):
    with Session() as session:
        bundle: ProfitBundle = session.scalar(
            select(ProfitBundle)
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
            .where(ProfitBundle.id == bundle_id),
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
        spot_buy_fee=bundle.spot_buy_fee,
        spot_sell_fee=bundle.spot_sell_fee,
        withdraw_cne=bundle.withdraw_coin_network_exchange,
    )
    try:
        price_analyzer.run()
    except Exception as e:
        logger.exception(e)
        return

    if price_analyzer.user_based_profit > REFRESH_BASE_USDT_PROFIT:
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
                bundle.joinedload(ProfitBundle.withdraw_pair_exchange),
                bundle.joinedload(ProfitBundle.deposit_pair_exchange),
            )
            .filter(ProfitBundleItem.profit_bundle_id == bundle_id)
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
        bundle: ProfitBundle = session.scalar(
            select(ProfitBundle)
            .options(
                joinedload(ProfitBundle.pair),
                joinedload(ProfitBundle.pair).joinedload(Pair.base_coin),
                joinedload(ProfitBundle.pair).joinedload(Pair.quote_coin),
                joinedload(ProfitBundle.base_exchange),
                joinedload(ProfitBundle.pair_exchange),
            )
            .where(ProfitBundle.id == bundle_id),
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
def auto_sell(price: float, profit_bundle_id: int):
    """
    Getting balance rate limit
    Mexc: 2r/1s but 0.2 good
    Bingx: 5r/1s  0.2 good
    Bitget: 0.2 good
    Huobi: 0.2 good
    Gateio: 0.2 good
    OKX: 10r/2s  0.2 good
    ByBit: needs 1r/1s but this is too rarely  0.7 is good
    Kucoin: 0.2 good
    Whitebit: 0.2 good
    XT: 0.2 good
    Binance: 0.2 good
    Poloniex: 0.2 good
    """
    try:
        with Session() as session:
            pair_to_exchange: PairExchange = session.scalar(
                select(PairExchange)
                .join(
                    ProfitBundle,
                    and_(
                        ProfitBundle.pair_id == PairExchange.pair_id,
                        ProfitBundle.pair_exchange_id == PairExchange.exchange_id,
                    ),
                )
                .options(
                    joinedload(PairExchange.pair),
                    joinedload(PairExchange.pair).joinedload(Pair.base_coin),
                    joinedload(PairExchange.pair).joinedload(Pair.quote_coin),
                    joinedload(PairExchange.exchange),
                )
                .where(ProfitBundle.id == profit_bundle_id),
            )

        exchange_api = EXCHANGES_MAPPING[pair_to_exchange.exchange.name]
        exchange_api = exchange_api(config, {}, logger)
        params = {
            "coin_name": pair_to_exchange.pair.base_coin.name,
        }
        if exchange_api.NAME == "KuCoin":
            params["account_type"] = "main"  # deposits is credited on main account in kucoin

        start_balance = exchange_api.get_balance(**params)
        while True:
            balance = exchange_api.get_balance(**params)

            if balance <= start_balance:
                time.sleep(exchange_api.get_balance_limit)
            else:
                break

        if exchange_api.NAME == "KuCoin":
            exchange_api.transfer(
                coin_name=params["coin_name"],
                amount=str(balance),
                from_account="main",
                to_account="trade",
            )
            time.sleep(0.5)

        logger.info(
            f"Creation auto sell order for {pair_to_exchange.pair.default_name}\n"
            f"{start_balance = }; {balance = }; {price = }",
        )
        exchange_api.create_order(
            pair=pair_to_exchange.pair,
            ccy_quantity=balance,
            ccy_precision=pair_to_exchange.base_coin_precision,
            price=price,
            price_precision=pair_to_exchange.quote_coin_precision,
            spot_fee=balance * pair_to_exchange.taker_fee,
            is_buy=False,
        )
    except Exception as e:
        msg = f"[{pair_to_exchange.pair.dashed_name}] ❌\nError occurred while auto selling {e}"
    else:
        msg = f"[{pair_to_exchange.pair.dashed_name}] ✅\nAuto sell completed successfully!"

    bot = Bot(token=config["BOT_TOKEN"], parse_mode="HTML")
    asyncio.run(send_message(bot, config["SYSTEM_CHANNEL_ID"], msg))
