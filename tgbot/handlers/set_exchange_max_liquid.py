from aiogram import Router
from aiogram.filters import Command
from aiogram.filters import CommandObject
from aiogram.types import Message
from db.base import Session
from db.models import Exchange

set_exchange_max_liquid_router = Router()


@set_exchange_max_liquid_router.message(Command("set_liquid"))
async def set_exchange_max_liquid_handler(message: Message, command: CommandObject):
    if command.args is None:
        await message.reply("Please specify exchange and amount to set. E.g /set_liquid Bybit 800")
        return

    try:
        exchange_name, liquid_amount = command.args.split(" ")
    except ValueError:
        await message.reply("Please specify exchange and amount to set. E.g /set_liquid Bybit 800")
        return

    with Session() as session:
        exchange = session.query(Exchange).filter(Exchange.name == exchange_name).first()
        if not exchange:
            await message.reply("Couldn't find this exchange")
            return

        exchange.max_liquid_amount = liquid_amount
        session.commit()

    await message.reply("Updated successfully")
