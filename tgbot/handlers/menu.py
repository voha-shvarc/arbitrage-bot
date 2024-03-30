import logging

from aiogram import F
from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.fsm.state import StatesGroup
from aiogram.types import CallbackQuery
from aiogram.types import Message
from dotenv import dotenv_values

from db.base import Session
from db.models import Exchange
from db.models import Network
from db.models import Whitelist
from db.structs import ExchangeLiquidity
from exchanges import EXCHANGES_MAPPING

from ..keyboards.menu import AddToWhitelistCallbackData
from ..keyboards.menu import ConfigExchangeCallbackData
from ..keyboards.menu import get_config_exchanges_keyboard
from ..keyboards.menu import get_config_exchanges_liquidity_keyboard
from ..keyboards.menu import get_menu_keyboard
from ..keyboards.menu import get_whitelisting_exchanges_keyboard
from ..keyboards.menu import SetExchangeLiquidityLimitCallbackData


logger = logging.getLogger(__name__)
config = dotenv_values(".env")

menu_router = Router()


class SetExchangeLiquidity(StatesGroup):
    set_amount = State()


class AddToWhitelist(StatesGroup):
    set_network = State()


@menu_router.message(F.text == "Balance💰")
async def get_total_balance(message: Message):
    info = ""
    total_balance = 0
    for name, exchange in EXCHANGES_MAPPING.items():
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
            EXCHANGES_MAPPING[exchange.name](config, {}, logger).get_balance(),
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


@menu_router.message(F.text == "Whitelist 📝")
async def add_to_whitelist(message: Message, state: FSMContext):
    with Session() as session:
        exchanges = session.query(Exchange.id, Exchange.name).all()

    await message.answer(
        "Choose the withdraw exchange...",
        reply_markup=get_whitelisting_exchanges_keyboard(exchanges),
    )


@menu_router.callback_query(AddToWhitelistCallbackData.filter(~F.deposit_exchange_id))
async def set_whitelist_withdraw_exchange_callback_query(
    query: CallbackQuery,
    callback_data: AddToWhitelistCallbackData,
):
    await query.answer()

    with Session() as session:
        exchanges = session.query(Exchange.id, Exchange.name).all()

    await query.message.edit_text(
        "Choose the deposit exchange...",
        reply_markup=get_whitelisting_exchanges_keyboard(
            exchanges=exchanges,
            withdraw_exchange_id=callback_data.withdraw_exchange_id,
        ),
    )


@menu_router.callback_query(StateFilter(None), AddToWhitelistCallbackData.filter(F.deposit_exchange_id))
async def set_whitelist_deposit_exchange_callback_query(
    query: CallbackQuery,
    callback_data: AddToWhitelistCallbackData,
    state: FSMContext,
):
    await query.answer()
    await state.set_state(AddToWhitelist.set_network)
    await state.set_data(
        {
            "withdraw_exchange_id": callback_data.withdraw_exchange_id,
            "deposit_exchange_id": callback_data.deposit_exchange_id,
        },
    )

    await query.message.answer(
        "Enter the network name...",
        reply_markup=get_menu_keyboard(),
    )


@menu_router.message(StateFilter(AddToWhitelist.set_network))
async def set_whitelist_network(message: Message, state: FSMContext):
    state_data = await state.get_data()
    network_name = message.text

    await state.clear()
    with Session() as session:
        network_id = session.query(Network.id).filter(Network.name == network_name).scalar()
        if not network_id:
            await message.reply(f"Couldn't find the network <b>{network_name}</b>. Try again...")
            return

        whitelist = Whitelist(
            withdraw_exchange_id=state_data["withdraw_exchange_id"],
            deposit_exchange_id=state_data["deposit_exchange_id"],
            base_network_id=network_id,
        )

        session.add(whitelist)
        session.commit()

    await message.answer(
        "Successfully whitelisted!",
    )
