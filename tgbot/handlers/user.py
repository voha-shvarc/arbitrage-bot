from aiogram import Router
from aiogram.filters import Command
from aiogram.filters import CommandStart
from aiogram.types import Message

from ..keyboards.menu import get_menu_keyboard


user_router = Router()


@user_router.message(CommandStart())
async def user_start(message: Message):
    await message.reply(f"Your user id is {message.from_user.id}")


@user_router.message(Command("menu"))
async def show_menu(message: Message):
    await message.reply("Here's menu:", reply_markup=get_menu_keyboard())
