from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData


class RefreshBundleCallbackData(CallbackData, prefix="refresh"):
    profit_bundle_id: int
    show_more: bool = False


def get_refresh_keyboard(profit_bundle_id):
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="Refresh",
        callback_data=RefreshBundleCallbackData(profit_bundle_id=profit_bundle_id),
    )
    keyboard.button(
        text="More",
        callback_data=RefreshBundleCallbackData(profit_bundle_id=profit_bundle_id, show_more=True),
    )

    return keyboard.as_markup()
