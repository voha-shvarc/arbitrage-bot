import logging

from aiogram import F
from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.types import Message
from dotenv import dotenv_values

from db.base import Session
from db.models import Exchange
from db.structs import ExchangeLiquidity
from exchanges import BinanceAPI
from exchanges import BingxAPI
from exchanges import BitgetAPI
from exchanges import BybitAPI
from exchanges import HuobiAPI
from exchanges import KuCoinAPI
from exchanges import MexcAPI
from exchanges import OkxAPI
from exchanges import PoloniexAPI
from exchanges import WhitebitAPI

from ..keyboards.menu import ConfigExchangeCallbackData
from ..keyboards.menu import get_config_exchanges_keyboard
from ..keyboards.menu import get_config_exchanges_liquidity_keyboard
from ..keyboards.menu import SetExchangeLiquidityLimitCallbackData


exchange_mapping = {
    BybitAPI.NAME: BybitAPI,
    BitgetAPI.NAME: BitgetAPI,
    HuobiAPI.NAME: HuobiAPI,
    OkxAPI.NAME: OkxAPI,
    KuCoinAPI.NAME: KuCoinAPI,
    BinanceAPI.NAME: BinanceAPI,
    WhitebitAPI.NAME: WhitebitAPI,
    BingxAPI.NAME: BingxAPI,
    MexcAPI.NAME: MexcAPI,
    PoloniexAPI.NAME: PoloniexAPI,
}

logger = logging.getLogger(__name__)
config = dotenv_values(".env")

menu_router = Router()

from aiogram.fsm.state import State
from aiogram.fsm.state import StatesGroup


class SetExchangeLiquidity(StatesGroup):
    set_amount = State()


@menu_router.message(F.text == "Balance💰")
async def get_total_balance(message: Message):
    info = ""
    total_balance = 0
    for name, exchange in exchange_mapping.items():
        exchange = exchange(config, {}, logger)
        balance = exchange.get_balance()
        info += f"{name}: <b>{balance:.2f}$</b>\n"
        total_balance += balance

    await message.reply(f"💰Balance: <b>{total_balance:.2f}$</b>\n\n{info}")


@menu_router.message(F.text == "Exchanges 🛒")
async def configure_exchanges(message: Message):
    with Session() as session:
        reply_markup = get_config_exchanges_keyboard(session)

    await message.answer("Configure your exchanges...", reply_markup=reply_markup)


@menu_router.message(F.text == "Limits 💸")
async def configure_exchanges_liquidity(message: Message):
    with Session() as session:
        exchanges = session.query(Exchange).filter(Exchange.active_buy)

    exchanges_info = [
        ExchangeLiquidity(
            exchange.id,
            exchange.name,
            exchange.max_liquid_amount,
            exchange_mapping[exchange.name](config, {}, logger).get_balance(),
        )
        for exchange in exchanges
    ]
    await message.answer(
        "Exchanges Liquid 💸\n\n",
        reply_markup=get_config_exchanges_liquidity_keyboard(exchanges_info),
    )


@menu_router.callback_query(StateFilter(None), SetExchangeLiquidityLimitCallbackData.filter())
async def configure_exchanges_liquidity_callback_query(
    query: CallbackQuery,
    callback_data: SetExchangeLiquidityLimitCallbackData,
    state: FSMContext,
):
    await query.answer()
    await query.message.reply(f"Set your liquidity for {callback_data.exchange_name}...")
    await state.set_state(SetExchangeLiquidity.set_amount)
    await state.set_data({"exchange_id": callback_data.exchange_id})


@menu_router.message(SetExchangeLiquidity.set_amount)
async def set_exchange_liquidity(message: Message, state: FSMContext):
    amount = message.text
    state_data = await state.get_data()
    if amount.isnumeric():
        with Session() as session:
            (
                session.query(Exchange)
                .filter(Exchange.id == state_data["exchange_id"])
                .update({"max_liquid_amount": amount})
            )
            session.commit()

        await message.reply("Successfully set")
        await state.clear()
    else:
        await message.reply("Please enter a number...")


@menu_router.callback_query(ConfigExchangeCallbackData.filter())
async def configure_active_exchanges_callback_query(query: CallbackQuery, callback_data: ConfigExchangeCallbackData):
    await query.answer()
    with Session() as session:
        (
            session.query(Exchange)
            .filter(Exchange.id == callback_data.exchange_id)
            .update({callback_data.type_name: callback_data.set_active})
        )
        reply_markup = get_config_exchanges_keyboard(session)
        session.commit()

    await query.message.edit_text("Configure your exchanges...", reply_markup=reply_markup)


@menu_router.callback_query(F.data == "not_clickable")
async def configure_exchange_header_buttons(query: CallbackQuery):
    await query.answer()
