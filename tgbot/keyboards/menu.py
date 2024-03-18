from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.keyboard import InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from db.models import Exchange


class ConfigExchangeCallbackData(CallbackData, prefix="config_exchange"):
    exchange_id: int
    type_name: str
    set_active: bool


def get_menu_keyboard():
    keyboard = ReplyKeyboardBuilder()

    keyboard.button(
        text="Balance💰",
    )
    keyboard.button(
        text="Exchanges 🛒",
    )
    keyboard.button(
        text="Limits 💸",
    )

    return keyboard.as_markup(resize_keyboard=True)


def get_config_exchanges_keyboard(session):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text="📕", callback_data="buy"),
        InlineKeyboardButton(text="📗", callback_data="sell"),
    )
    for exchange in session.query(Exchange).order_by(Exchange.id):
        keyboard.button(
            text=f"{exchange.name}{' ✅' if exchange.active_buy else ''}",
            callback_data=ConfigExchangeCallbackData(
                exchange_id=exchange.id,
                type_name="active_buy",
                set_active=not exchange.active_buy,
            ),
        )
        keyboard.button(
            text=f"{exchange.name}{' ✅' if exchange.active_sell else ''}",
            callback_data=ConfigExchangeCallbackData(
                exchange_id=exchange.id,
                type_name="active_sell",
                set_active=not exchange.active_sell,
            ),
        )

    keyboard.adjust(2)
    return keyboard.as_markup()
