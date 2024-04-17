import logging
from datetime import date

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
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from abstract.abstract import AbstractExchange
from abstract.abstract import CreateOrderError
from abstract.abstract import DepositAddressError
from analyze.price_analyzer import PriceAnalyzer
from celery_app.tasks import auto_sell
from celery_app.tasks import monitor_bundle
from db.base import Session
from db.models import CoinNetworkExchange
from db.models import Pair
from db.models import PairExchange
from db.models import ProfitBundle
from db.models import ProfitBundleItem
from exchanges import EXCHANGES_MAPPING

from ..keyboards.bundle import AutoSellBundleCallbackData
from ..keyboards.bundle import CheckedBundleCallbackData
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


class AutoSell(StatesGroup):
    set_price = State()
    set_timer = State()


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
        await query.message.edit_text(
            message,
            disable_web_page_preview=True,
            reply_markup=get_bundle_keyboard(bundle.id, bundle.base_exchange.name, bundle.pair_exchange.name),
        )
    except TelegramBadRequest:
        logger.warning(f"Bundle (id={bundle.id}) haven't changed...")


@bundle_router.callback_query(ForceRefreshBundleCallbackData.filter())
async def force_recalculate_bundle_callback_query(query: CallbackQuery, callback_data: ForceRefreshBundleCallbackData):
    await query.answer()

    monitor_bundle.apply_async(args=[callback_data.profit_bundle_id, True])

    await query.message.edit_reply_markup(
        reply_markup=get_bundle_keyboard(
            callback_data.profit_bundle_id,
            callback_data.withdraw_exchange_name,
            callback_data.deposit_exchange_name,
            force_refresh_label="✅",
        ),
    )


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
            # if bundle.bought_ccy_quantity:
            # ccy_quantity_to_withdraw = bundle.bought_ccy_quantity
            # else:
            ccy_quantity_to_withdraw = base_exchange.get_balance(bundle.pair.base_coin.name)

            logger.info(
                f"Withdraw - {bundle.withdraw_coin_network_exchange.coin.name} "
                f"| {bundle.withdraw_coin_network_exchange.network.name} \n"
                f"{ccy_quantity_to_withdraw = } | {bundle.bought_ccy_quantity = }",
            )
            base_exchange.withdraw(bundle.withdraw_coin_network_exchange, ccy_quantity_to_withdraw, deposit_address)
        except Exception as e:
            logger.error(f"Error proceeding withdraw. {e}")
            withdraw_label = "❌"
            await query.message.reply(str(e))

    await query.message.edit_reply_markup(
        reply_markup=get_bundle_keyboard(
            callback_data.profit_bundle_id,
            base_exchange.NAME,
            pair_exchange.NAME,
            withdraw_label=withdraw_label,
        ),
    )


async def create_order(profit_bundle_id: int, limit=None) -> tuple[str, str]:
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
        spot_buy_fee=bundle.spot_buy_fee,
        spot_sell_fee=bundle.spot_sell_fee,
        withdraw_cne=bundle.withdraw_coin_network_exchange,
        custom_liquid_limit=limit,
    )
    buy_label = "🛠️"
    response = ""
    try:
        price_analyzer.run()
    except Exception as e:
        logger.exception(e)
        response = str(e)
    else:
        if price_analyzer.profit > BASE_USDT_PROFIT:
            if pair_to_exchange.base_coin_precision is not None and pair_to_exchange.quote_coin_precision is not None:
                try:
                    spot_fee = price_analyzer.user_based_coin_available_amount * pair_to_exchange.taker_fee
                    logger.info(
                        f"Create order with {bundle.pair.default_name = };\n "
                        f"{price_analyzer.user_based_coin_available_amount = }; {pair_to_exchange.base_coin_precision};\n"
                        f"{price_analyzer.user_based_max_buy_price = }; {pair_to_exchange.quote_coin_precision};\n"
                        f"{pair_to_exchange.taker_fee = }, {spot_fee = }",
                    )

                    base_exchange.create_order(
                        pair=bundle.pair,
                        ccy_quantity=price_analyzer.user_based_coin_available_amount,
                        ccy_precision=pair_to_exchange.base_coin_precision,
                        price=price_analyzer.user_based_max_buy_price,
                        price_precision=pair_to_exchange.quote_coin_precision,
                        spot_fee=spot_fee,
                    )
                    buy_label = "✅"
                except (CreateOrderError, Exception) as e:
                    logger.error(e)
                    response = str(e)
                finally:
                    ccy_quantity_to_withdraw = (
                        price_analyzer.user_based_coin_available_amount
                        - price_analyzer.user_based_coin_available_amount * bundle.spot_buy_fee
                    )
                    with Session() as session:
                        (
                            session.query(ProfitBundle)
                            .filter(ProfitBundle.id == profit_bundle_id)
                            .update(
                                {"bought_ccy_quantity": ccy_quantity_to_withdraw},
                            )
                        )
                        session.commit()
            else:
                response = "Creating order. No precision info found"
                logger.error(response)
        else:
            buy_label = "💀"

    return buy_label, response


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
        buy_label, response = await create_order(callback_data.profit_bundle_id)
        await query.message.edit_reply_markup(
            reply_markup=get_bundle_keyboard(
                callback_data.profit_bundle_id,
                callback_data.withdraw_exchange_name,
                callback_data.deposit_exchange_name,
                buy_label=buy_label,
            ),
        )
        if response:
            await query.message.reply(response)


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
        buy_label, response = await create_order(profit_bundle_id, float(limit))

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
        if response:
            await message.reply(response)


@bundle_router.callback_query(CheckedBundleCallbackData.filter())
async def checked_bundle_callback_query(query: CallbackQuery, callback_data: CheckedBundleCallbackData):
    await query.answer()
    with Session() as session:
        withdraw_cne_id, deposit_cne_id = (
            session.query(ProfitBundle.withdraw_coin_network_exchange_id, ProfitBundle.deposit_coin_network_exchange_id)
            .filter(ProfitBundle.id == callback_data.profit_bundle_id)
            .first()
        )

        (
            session.query(CoinNetworkExchange)
            .filter(CoinNetworkExchange.id.in_([withdraw_cne_id, deposit_cne_id]))
            .update(
                {"is_checked": True, "checked_at": date.today()},
            )
        )
        try:
            session.commit()
            checked_label = "✅"
        except SQLAlchemyError as e:
            logger.error(f"Error checking bundle {e}")
            checked_label = "❌"

        await query.message.edit_reply_markup(
            reply_markup=get_bundle_keyboard(
                callback_data.profit_bundle_id,
                callback_data.withdraw_exchange_name,
                callback_data.deposit_exchange_name,
                checked_label=checked_label,
            ),
        )


@bundle_router.callback_query(StateFilter(None), AutoSellBundleCallbackData.filter())
async def auto_sell_bundle_callback_query(
    query: CallbackQuery,
    callback_data: AutoSellBundleCallbackData,
    state: FSMContext,
):
    await query.answer()
    await query.message.reply("Please enter a limit price...")
    await state.set_state(AutoSell.set_price)
    await state.set_data(
        {
            "profit_bundle_id": callback_data.profit_bundle_id,
            "withdraw_exchange_name": callback_data.withdraw_exchange_name,
            "deposit_exchange_name": callback_data.deposit_exchange_name,
            "chat_id": query.message.chat.id,
            "message_id": query.message.message_id,
        },
    )


@bundle_router.message(StateFilter(AutoSell.set_price))
async def set_limit_price(message: Message, state: FSMContext):
    try:
        price = float(message.text)
    except ValueError as e:
        await message.reply(f"It should be a number. Try again...\n{e}")
    else:
        await state.update_data({"price": price})
        await message.reply("Please enter seconds to wait till trying to sell...")
        await state.set_state(AutoSell.set_timer)


@bundle_router.message(StateFilter(AutoSell.set_timer))
async def set_timer(message: Message, state: FSMContext):
    try:
        timer = int(message.text)
    except ValueError as e:
        await message.reply(f"It should be a number. Try again...\n{e}")
    else:
        state_data = await state.get_data()

        await message.bot.edit_message_reply_markup(
            chat_id=state_data["chat_id"],
            message_id=state_data["message_id"],
            reply_markup=get_bundle_keyboard(
                state_data["profit_bundle_id"],
                state_data["withdraw_exchange_name"],
                state_data["deposit_exchange_name"],
                sell_label="✅",
            ),
        )
        await state.clear()

        auto_sell.apply_async(args=(state_data["price"], state_data["profit_bundle_id"]), countdown=timer)
