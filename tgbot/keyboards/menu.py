from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.keyboard import InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from db.models import Exchange
from db.structs import ExchangeLiquidity


class ConfigExchangeCallbackData(CallbackData, prefix="config_exchange"):
    exchange_id: int
    type_name: str
    set_active: bool


class SetExchangeLiquidityLimitCallbackData(CallbackData, prefix="set_liquidity_limit"):
    exchange_id: int
    exchange_name: str


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
        InlineKeyboardButton(text="📕", callback_data="not_clickable"),
        InlineKeyboardButton(text="📗", callback_data="not_clickable"),
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


def get_config_exchanges_liquidity_keyboard(exchanges_info: list[ExchangeLiquidity]):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text="Exchange 📕", callback_data="not_clickable"),
        InlineKeyboardButton(text="Current Limit 💼", callback_data="not_clickable"),
        InlineKeyboardButton(text="Balance 💰", callback_data="not_clickable"),
    )

    for exchange_info in exchanges_info:
        keyboard.button(
            text=exchange_info.name,
            callback_data=SetExchangeLiquidityLimitCallbackData(
                exchange_id=exchange_info.exchange_id,
                exchange_name=exchange_info.name,
            ),
        )
        keyboard.button(
            text=f"{exchange_info.current_limit:.2f}",
            callback_data=SetExchangeLiquidityLimitCallbackData(
                exchange_id=exchange_info.exchange_id,
                exchange_name=exchange_info.name,
            ),
        )
        keyboard.button(
            text=f"{exchange_info.balance:.2f}",
            callback_data=SetExchangeLiquidityLimitCallbackData(
                exchange_id=exchange_info.exchange_id,
                exchange_name=exchange_info.name,
            ),
        )

    keyboard.adjust(3)
    return keyboard.as_markup()
