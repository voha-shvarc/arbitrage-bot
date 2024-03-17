import logging

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from dotenv import dotenv_values
from sqlalchemy.orm import joinedload

from abstract.abstract import AbstractExchange
from abstract.abstract import CreateOrderError
from abstract.abstract import DepositAddressError
from analyze.price_analyzer import PriceAnalyzer
from celery_app.tasks import monitor_bundle
from db.base import Session
from db.models import CoinNetworkExchange
from db.models import Pair
from db.models import PairExchange
from db.models import ProfitBundle
from db.models import ProfitBundleItem
from exchanges import BinanceAPI
from exchanges import BingxAPI
from exchanges import BitgetAPI
from exchanges import BybitAPI
from exchanges import HuobiAPI
from exchanges import KuCoinAPI
from exchanges import MexcAPI
from exchanges import OkxAPI
from exchanges import WhitebitAPI

from ..keyboards.bundle import CreateOrderCallbackData
from ..keyboards.bundle import ForceRefreshBundleCallbackData
from ..keyboards.bundle import get_bundle_keyboard
from ..keyboards.bundle import RefreshBundleCallbackData
from ..keyboards.bundle import WithdrawBundleCallbackData
from ..services.messages import get_bundle_message


logger = logging.getLogger(__name__)
config = dotenv_values(".env")

bundle_router = Router()

exchange_mapping = {
    BinanceAPI.NAME: BinanceAPI,
    BybitAPI.NAME: BybitAPI,
    HuobiAPI.NAME: HuobiAPI,
    OkxAPI.NAME: OkxAPI,
    KuCoinAPI.NAME: KuCoinAPI,
    BitgetAPI.NAME: BitgetAPI,
    WhitebitAPI.NAME: WhitebitAPI,
    BingxAPI.NAME: BingxAPI,
    MexcAPI.NAME: MexcAPI,
}

BASE_USDT_PROFIT = 4  # 4 USDT


@bundle_router.callback_query(RefreshBundleCallbackData.filter())
async def recalculate_bundle_callback_query(query: CallbackQuery, callback_data: RefreshBundleCallbackData):
    await query.answer()
    with Session() as session:
        bundle = joinedload(ProfitBundleItem.profit_bundle)
        bundle_item: ProfitBundleItem = (
            session.query(ProfitBundleItem)
            .filter(ProfitBundleItem.profit_bundle_id == callback_data.profit_bundle_id)
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

    bundle = bundle_item.profit_bundle
    try:
        message = get_bundle_message(bundle, bundle_item, callback_data.show_more)
        await query.message.edit_text(
            message,
            reply_markup=get_bundle_keyboard(bundle.id),
            disable_web_page_preview=True,
        )
    except TelegramBadRequest:
        logger.warning(f"Bundle (id={bundle.id}) haven't changed...")


@bundle_router.callback_query(ForceRefreshBundleCallbackData.filter())
async def force_recalculate_bundle_callback_query(query: CallbackQuery, callback_data: ForceRefreshBundleCallbackData):
    await query.answer()
    bundle_id = callback_data.profit_bundle_id

    text = query.message.html_text
    await query.message.edit_text(
        f"{text}\n\nUpdating...",
        reply_markup=get_bundle_keyboard(bundle_id),
        disable_web_page_preview=True,
    )

    monitor_bundle.apply_async(args=[bundle_id, True])


@bundle_router.callback_query(WithdrawBundleCallbackData.filter())
async def withdraw_bundle_callback_query(query: CallbackQuery, callback_data: WithdrawBundleCallbackData):
    await query.answer()
    bundle_id = callback_data.profit_bundle_id

    with Session() as session:
        bundle: ProfitBundle = (
            session.query(ProfitBundle)
            .options(
                joinedload(ProfitBundle.withdraw_coin_network_exchange),
                joinedload(ProfitBundle.withdraw_coin_network_exchange).joinedload(CoinNetworkExchange.coin),
                joinedload(ProfitBundle.withdraw_coin_network_exchange).joinedload(CoinNetworkExchange.network),
                joinedload(ProfitBundle.deposit_coin_network_exchange),
                joinedload(ProfitBundle.deposit_coin_network_exchange).joinedload(CoinNetworkExchange.coin),
                joinedload(ProfitBundle.deposit_coin_network_exchange).joinedload(CoinNetworkExchange.network),
                joinedload(ProfitBundle.pair),
                joinedload(ProfitBundle.pair).joinedload(Pair.base_coin),
                joinedload(ProfitBundle.pair).joinedload(Pair.quote_coin),
                joinedload(ProfitBundle.base_exchange),
                joinedload(ProfitBundle.pair_exchange),
            )
            .get(bundle_id)
        )

    base_exchange: AbstractExchange = exchange_mapping[bundle.base_exchange.name](config, {})
    pair_exchange: AbstractExchange = exchange_mapping[bundle.pair_exchange.name](config, {})

    text = query.message.html_text
    withdraw_label = "✅"
    try:
        deposit_address = pair_exchange.get_deposit_address(bundle.deposit_coin_network_exchange)
    except DepositAddressError:
        withdraw_label = "❌"
    else:
        try:
            base_exchange.withdraw(bundle.withdraw_coin_network_exchange, deposit_address)
        except Exception:
            withdraw_label = "❌"

    await query.message.edit_text(
        text,
        reply_markup=get_bundle_keyboard(callback_data.profit_bundle_id, withdraw_label=withdraw_label),
        disable_web_page_preview=True,
    )


@bundle_router.callback_query(CreateOrderCallbackData.filter())
async def create_order_callback_query(query: CallbackQuery, callback_data: CreateOrderCallbackData):
    await query.answer()

    with Session() as session:
        bundle: ProfitBundle = (
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
            .get(callback_data.profit_bundle_id)
        )
        pair_to_exchange: PairExchange = (
            session.query(PairExchange)
            .filter(
                PairExchange.exchange_id == bundle.base_exchange_id,
                PairExchange.pair_id == bundle.pair_id,
            )
            .first()
        )

    base_exchange = exchange_mapping[bundle.base_exchange.name](config, {})
    pair_exchange = exchange_mapping[bundle.pair_exchange.name](config, {})

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
        logger.exception(e)
        return

    text = query.message.html_text
    buy_label = "❌"
    if price_analyzer.profit > BASE_USDT_PROFIT:
        if pair_to_exchange.base_coin_precision and pair_to_exchange.quote_coin_precision:
            try:
                base_exchange.create_order(
                    pair=bundle.pair,
                    ccy_quantity=price_analyzer.user_based_coin_available_amount,
                    ccy_precision=pair_to_exchange.base_coin_precision,
                    price=price_analyzer.user_based_max_buy_price,
                    price_precision=pair_to_exchange.quote_coin_precision,
                )
            except CreateOrderError:
                pass
            else:
                buy_label = "✅"
        else:
            logger.error("Creating order. No precision info found")

    await query.message.edit_text(
        text,
        reply_markup=get_bundle_keyboard(callback_data.profit_bundle_id, buy_label=buy_label),
        disable_web_page_preview=True,
    )
