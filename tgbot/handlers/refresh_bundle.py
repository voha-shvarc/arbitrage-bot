import logging
from datetime import datetime

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from dotenv import dotenv_values
from sqlalchemy.orm import joinedload

from db.base import Session
from db.models import ProfitBundle, ProfitBundleItem, CoinNetworkExchange, Pair, BundleStatus
from exchanges import BinanceAPI, BybitAPI, OkxAPI, GateIOAPI, HuobiAPI, KuCoinAPI, BitgetAPI
from ..keyboards.bundle import get_refresh_keyboard, RefreshBundleCallbackData


logger = logging.getLogger(__name__)
config = dotenv_values(".env")

refresh_bundle_router = Router()

exchange_mapping = {
    BinanceAPI.NAME: BinanceAPI,
    BybitAPI.NAME: BybitAPI,
    HuobiAPI.NAME: HuobiAPI,
    GateIOAPI.NAME: GateIOAPI,
    OkxAPI.NAME: OkxAPI,
    KuCoinAPI.NAME: KuCoinAPI,
    BitgetAPI.NAME: BitgetAPI,
}


BASE_USDT_PROFIT = 4  # 4 USDT


@refresh_bundle_router.callback_query(RefreshBundleCallbackData.filter())
async def recalculate_callback_query(query: CallbackQuery, callback_data: RefreshBundleCallbackData):
    await query.answer()
    logger.info(f"Test callback with bundle_id = {callback_data.profit_bundle_id}")
    with Session() as session:
        bundle = joinedload(ProfitBundleItem.profit_bundle)
        bundle_item: ProfitBundleItem = session.query(ProfitBundleItem) \
            .filter(ProfitBundleItem.profit_bundle_id == callback_data.profit_bundle_id) \
            .options(bundle,
                     bundle.joinedload(ProfitBundle.base_exchange),
                     bundle.joinedload(ProfitBundle.pair_exchange),
                     bundle.joinedload(ProfitBundle.pair),
                     bundle.joinedload(ProfitBundle.pair).joinedload(Pair.base_coin),
                     bundle.joinedload(ProfitBundle.pair).joinedload(Pair.quote_coin),
                     bundle.joinedload(ProfitBundle.coin_network_exchange),
                     bundle.joinedload(ProfitBundle.coin_network_exchange).joinedload(CoinNetworkExchange.network),
                     bundle.joinedload(ProfitBundle.coin_network_exchange).joinedload(CoinNetworkExchange.coin),
                     bundle.joinedload(ProfitBundle.coin_network_exchange).joinedload(CoinNetworkExchange.base_network)) \
            .order_by(ProfitBundleItem.created_at.desc()) \
            .first()

    bundle = bundle_item.profit_bundle
    try:
        message = _get_message(bundle, bundle_item, callback_data.show_more)
        await query.message.edit_text(
            message,
            reply_markup=get_refresh_keyboard(bundle.id),
            disable_web_page_preview=True,
        )
    except TelegramBadRequest:
        logger.warning(f"Bundle (id={bundle.id}) haven't changed...")

    session.commit()


def _get_message(bundle, bundle_item: ProfitBundleItem, show_more: bool = False) -> str:
    if bundle.status == BundleStatus.in_progress:
        time_live = datetime.utcnow() - bundle.created_at
    else:
        time_live = bundle.updated_at - bundle.created_at

    base_exchange = exchange_mapping[bundle.base_exchange.name]
    pair_exchange = exchange_mapping[bundle.pair_exchange.name]

    base_ex_spot_link = base_exchange.spot_link(bundle.pair)
    base_ex_withdraw_link = base_exchange.withdraw_link(bundle.coin_network_exchange)
    pair_ex_spot_link = pair_exchange.spot_link(bundle.pair)
    pair_ex_deposit_link = pair_exchange.deposit_link(bundle.coin_network_exchange)

    base_exchange_price_section = (
        f"📕 {bundle.base_exchange.name} | <a href='{base_ex_spot_link}'>spot</a> | <a href='{base_ex_withdraw_link}'>withdraw</a>\n"
        f"📈 [ {round(bundle_item.user_based_base_exchange_min_price, 12)}-{round(bundle_item.user_based_base_exchange_min_price, 12)} ]"
        f" | {bundle_item.user_based_used_buy_orders} orders | {(bundle_item.user_based_percent_of_base_trading_vol * 100):.3f}%"
    )
    if show_more:
        base_exchange_price_section += (
            f"\n🛒 {bundle_item.used_buy_orders} orders | {bundle_item.to_use_usdt:.2f}$ | {(bundle_item.percent_of_base_trading_vol * 100):.3f}%"
        )

    pair_exchange_price_section = (
        f"📗 {bundle.pair_exchange.name} | <a href='{pair_ex_spot_link}'>spot</a> | <a href='{pair_ex_deposit_link}'>deposit</a>\n"
        f"📈 [ {round(bundle_item.user_based_pair_exchange_min_price, 12)}-{round(bundle_item.user_based_pair_exchange_max_price, 12)} ]"
        f" | {bundle_item.user_based_used_sell_orders} orders | {(bundle_item.user_based_percent_of_pair_trading_vol * 100):.3f}%"
    )
    if show_more:
        pair_exchange_price_section += (
            f"\n🛒 {bundle_item.used_sell_orders} orders | {bundle_item.to_use_usdt:.2f}$ | {(bundle_item.percent_of_pair_trading_vol * 100):.3f}%"
        )

    fees_section = f"‼️️ Spot Fee: <b>{bundle_item.user_based_spot_fee:.2f}$</b> | Network Fee: <b>{bundle_item.user_based_network_fee:.2f}$</b>"

    status = f"🟢 Status: {bundle.status}" if bundle.status == BundleStatus.in_progress else f"🔴 Status: {bundle.status}"
    message = (
        f"<b>{bundle.base_exchange.name} -> {bundle.pair_exchange.name} | {bundle_item.user_based_to_use_usdt:.2f}$ "
        f"+{bundle_item.user_based_profit:.2f}$ ({bundle_item.user_based_avg_spread * 100:.2f}%)</b>\n\n"
        f"<b>{bundle.pair.dashed_name}</b> | <b>{bundle.coin_network_exchange.base_network.name}</b>\n\n"
        f"{base_exchange_price_section}\n\n"
        f"{pair_exchange_price_section}\n\n"
        f"{fees_section}\n\n"
        f"{status}\n"
        f"⏳ Alive: {time_live.total_seconds() / 60:.1f} minutes"
    )

    return message
