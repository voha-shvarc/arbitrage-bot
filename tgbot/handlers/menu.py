from aiogram import F
from aiogram import Router
from aiogram.types import Message
from dotenv import dotenv_values

from exchanges import BinanceAPI
from exchanges import BitgetAPI
from exchanges import BybitAPI
from exchanges import GateIOAPI
from exchanges import HuobiAPI
from exchanges import KuCoinAPI
from exchanges import OkxAPI


exchange_mapping = {
    BybitAPI.NAME: BybitAPI,
    BitgetAPI.NAME: BitgetAPI,
    HuobiAPI.NAME: HuobiAPI,
    OkxAPI.NAME: OkxAPI,
    KuCoinAPI.NAME: KuCoinAPI,
    BinanceAPI.NAME: BinanceAPI,
    GateIOAPI.NAME: GateIOAPI,
}

menu_router = Router()


@menu_router.message(F.text == "Total Balance")
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
