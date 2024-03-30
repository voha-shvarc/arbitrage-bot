import logging

from aiogram import F
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.fsm.state import StatesGroup
from aiogram.types import CallbackQuery
from aiogram.types import Message
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
from exchanges import EXCHANGES_MAPPING

from ..keyboards.bundle import CreateOrderCallbackData
from ..keyboards.bundle import ForceRefreshBundleCallbackData
from ..keyboards.bundle import get_bundle_keyboard
from ..keyboards.bundle import RefreshBundleCallbackData
from ..keyboards.bundle import WithdrawBundleCallbackData
from ..services.messages import get_bundle_message


logger = logging.getLogger(__name__)
config = dotenv_values(".env")

bundle_router = Router()

BASE_USDT_PROFIT = 4  # 4 USDT


class SetLimitedOrder(StatesGroup):
    set_amount = State()


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
        message = get_bundle_message(bundle, bundle_item)
        await query.message.edit_text(message, disable_web_page_preview=True)
    except TelegramBadRequest:
        logger.warning(f"Bundle (id={bundle.id}) haven't changed...")


@bundle_router.callback_query(ForceRefreshBundleCallbackData.filter())
async def force_recalculate_bundle_callback_query(query: CallbackQuery, callback_data: ForceRefreshBundleCallbackData):
    await query.answer()

    await query.message.edit_text(
        f"{query.message.html_text}\n\nUpdating...",
        disable_web_page_preview=True,
    )

    monitor_bundle.apply_async(args=[callback_data.profit_bundle_id, True])


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

    base_exchange: AbstractExchange = EXCHANGES_MAPPING[bundle.base_exchange.name](config, {}, logger)
    pair_exchange: AbstractExchange = EXCHANGES_MAPPING[bundle.pair_exchange.name](config, {}, logger)

    withdraw_label = "✅"
    try:
        deposit_address = pair_exchange.get_deposit_address(bundle.deposit_coin_network_exchange)
    except DepositAddressError:
        await query.message.reply("Error getting deposit")
        withdraw_label = "❌"
    else:
        try:
            base_exchange.withdraw(bundle.withdraw_coin_network_exchange, deposit_address)
        except Exception as e:
            await query.message.reply(
                f"Error proceeding withdraw. {e}. {deposit_address.address = }, {deposit_address.memo = }",
            )
            withdraw_label = "❌"

    await query.message.edit_reply_markup(
        reply_markup=get_bundle_keyboard(
            callback_data.profit_bundle_id,
            base_exchange.NAME,
            pair_exchange.NAME,
            withdraw_label=withdraw_label,
        ),
    )


async def create_order(profit_bundle_id: int, limit=None) -> str:
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
            .get(profit_bundle_id)
        )
        pair_to_exchange: PairExchange = (
            session.query(PairExchange)
            .filter(
                PairExchange.exchange_id == bundle.base_exchange_id,
                PairExchange.pair_id == bundle.pair_id,
            )
            .first()
        )

    base_exchange = EXCHANGES_MAPPING[bundle.base_exchange.name](config, {}, logger)
    pair_exchange = EXCHANGES_MAPPING[bundle.pair_exchange.name](config, {}, logger)

    base_exchange_price = base_exchange.get_price(bundle.pair)
    pair_exchange_price = pair_exchange.get_price(bundle.pair)

    price_analyzer = PriceAnalyzer(
        buy_price=base_exchange_price[0],
        sell_price=pair_exchange_price[1],
        withdraw_cne=bundle.withdraw_coin_network_exchange,
        custom_liquid_limit=limit,
    )
    buy_label = "🛠️"
    try:
        price_analyzer.run()
    except Exception as e:
        logger.exception(e)
    else:
        if price_analyzer.profit > BASE_USDT_PROFIT:
            if pair_to_exchange.base_coin_precision is not None and pair_to_exchange.quote_coin_precision is not None:
                try:
                    base_exchange.create_order(
                        pair=bundle.pair,
                        ccy_quantity=price_analyzer.user_based_coin_available_amount,
                        ccy_precision=pair_to_exchange.base_coin_precision,
                        price=price_analyzer.user_based_max_buy_price,
                        price_precision=pair_to_exchange.quote_coin_precision,
                    )
                    buy_label = "✅"
                except (CreateOrderError, Exception):
                    pass
            else:
                logger.error("Creating order. No precision info found")
        else:
            buy_label = "💀"

    return buy_label


@bundle_router.callback_query(CreateOrderCallbackData.filter(F.set_limit == "False"))
async def create_order_callback_query(query: CallbackQuery, callback_data: CreateOrderCallbackData):
    await query.answer()

    if not callback_data.confirmed:
        await query.message.edit_reply_markup(
            reply_markup=get_bundle_keyboard(
                callback_data.profit_bundle_id,
                callback_data.withdraw_exchange_name,
                callback_data.deposit_exchange_name,
                buy_confirmed=True,
                buy_label="🔓",
            ),
        )
    else:
        buy_label = await create_order(callback_data.profit_bundle_id)
        await query.message.edit_reply_markup(
            reply_markup=get_bundle_keyboard(
                callback_data.profit_bundle_id,
                callback_data.withdraw_exchange_name,
                callback_data.deposit_exchange_name,
                buy_label=buy_label,
            ),
        )


@bundle_router.callback_query(StateFilter(None), CreateOrderCallbackData.filter(F.set_limit == "True"))
async def set_amount_limited_order_callback_query(
    query: CallbackQuery,
    callback_data: CreateOrderCallbackData,
    state: FSMContext,
):
    await query.answer()

    await query.message.reply("Set your buy limit...")
    await state.set_state(SetLimitedOrder.set_amount)
    await state.set_data(
        {
            "profit_bundle_id": callback_data.profit_bundle_id,
            "withdraw_exchange_name": callback_data.withdraw_exchange_name,
            "deposit_exchange_name": callback_data.deposit_exchange_name,
            "chat_id": query.message.chat.id,
            "message_id": query.message.message_id,
        },
    )


@bundle_router.message(StateFilter(SetLimitedOrder.set_amount))
async def create_limited_order(message: Message, state: FSMContext):
    limit = message.text
    state_data = await state.get_data()

    if not limit.isnumeric():
        await message.reply("Please enter a whole number...")
    else:
        profit_bundle_id = state_data["profit_bundle_id"]
        buy_label = await create_order(profit_bundle_id, float(limit))

        await message.bot.edit_message_reply_markup(
            chat_id=state_data["chat_id"],
            message_id=state_data["message_id"],
            reply_markup=get_bundle_keyboard(
                profit_bundle_id,
                state_data["withdraw_exchange_name"],
                state_data["deposit_exchange_name"],
                buy_limit_label=buy_label,
            ),
        )
        await state.clear()
