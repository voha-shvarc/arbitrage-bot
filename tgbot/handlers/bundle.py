import logging

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from dotenv import dotenv_values
from sqlalchemy.orm import joinedload

from abstract.abstract import AbstractExchange
from abstract.abstract import DepositAddressError
from abstract.abstract import WithdrawError
from celery_app.tasks import monitor_bundle
from db.base import Session
from db.models import CoinNetworkExchange
from db.models import Pair
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

from ..keyboards.bundle import ForceRefreshBundleCallbackData
from ..keyboards.bundle import get_refresh_keyboard
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
            reply_markup=get_refresh_keyboard(bundle.id),
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
        reply_markup=get_refresh_keyboard(bundle_id),
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

    try:
        deposit_address = pair_exchange.get_deposit_address(bundle.deposit_coin_network_exchange)
    except DepositAddressError:
        await query.message.reply("Couldn't get deposit address. Check logs")
        return

    try:
        body = base_exchange.withdraw(bundle.withdraw_coin_network_exchange, deposit_address)
    except WithdrawError as e:
        await query.message.reply(f"Error - {e}")
        return
    except NotImplementedError:
        await query.message.reply("Withdraw isn't implemented for this exchange.")
        return

    await query.message.reply(
        f"Your deposit info addr = {deposit_address.address}, memo = {deposit_address.memo}\n"
        f"Withdraw body - <code>{body}</code>",
    )
