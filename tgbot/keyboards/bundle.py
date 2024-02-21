from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData


class RefreshBundleCallbackData(CallbackData, prefix="recalculate"):
    profit_bundle_id: int


def get_refresh_keyboard(profit_bundle_id):
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="Refresh",
        callback_data=RefreshBundleCallbackData(profit_bundle_id=profit_bundle_id),
    )

    return keyboard.as_markup()
