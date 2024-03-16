from aiogram import F
from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.types import Message
from dotenv import dotenv_values

from db.base import Session
from db.models import Exchange
from exchanges import BinanceAPI
from exchanges import BingxAPI
from exchanges import BitgetAPI
from exchanges import BybitAPI
from exchanges import GateIOAPI
from exchanges import HuobiAPI
from exchanges import KuCoinAPI
from exchanges import MexcAPI
from exchanges import OkxAPI
from exchanges import WhitebitAPI

from ..keyboards.menu import ConfigExchangeCallbackData
from ..keyboards.menu import get_config_exchanges_keyboard


exchange_mapping = {
    BybitAPI.NAME: BybitAPI,
    BitgetAPI.NAME: BitgetAPI,
    HuobiAPI.NAME: HuobiAPI,
    OkxAPI.NAME: OkxAPI,
    KuCoinAPI.NAME: KuCoinAPI,
    BinanceAPI.NAME: BinanceAPI,
    GateIOAPI.NAME: GateIOAPI,
    WhitebitAPI.NAME: WhitebitAPI,
    BingxAPI.NAME: BingxAPI,
    MexcAPI.NAME: MexcAPI,
}

menu_router = Router()


@menu_router.message(F.text == "Total Balance💰")
async def get_total_balance(message: Message):
    config = dotenv_values(".env")
    info = ""
    total_balance = 0
    for name, exchange in exchange_mapping.items():
        exchange = exchange(config, {})
        balance = exchange.get_balance()
        info += f"{name}: <b>{balance:.2f}$</b>\n"
        total_balance += balance

    await message.reply(f"💰Balance: <b>{total_balance:.2f}$</b>\n\n{info}")


@menu_router.message(F.text == "Exchanges 🛒")
async def configure_exchanges(message: Message):
    with Session() as session:
        reply_markup = get_config_exchanges_keyboard(session)

    await message.answer("Configure your exchanges...", reply_markup=reply_markup)


@menu_router.message(F.text == "Exchanges Liquid 💸")
async def show_exchanges_liquidity(message: Message):
    with Session() as session:
        exchanges = session.query(Exchange)

    exchanges_info = [f"{exchange.name}: <b>{exchange.max_liquid_amount}</b>" for exchange in exchanges]
    await message.answer("Exchanges Liquid 💸\n\n" + "\n".join(exchanges_info))


@menu_router.callback_query(ConfigExchangeCallbackData.filter())
async def configure_exchange_callback_query(query: CallbackQuery, callback_data: ConfigExchangeCallbackData):
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


@menu_router.callback_query(F.data.in_({"sell", "buy"}))
async def configure_exchange_header_buttons(query: CallbackQuery):
    await query.answer()
