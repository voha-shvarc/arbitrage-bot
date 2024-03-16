from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder


class RefreshBundleCallbackData(CallbackData, prefix="refresh"):
    profit_bundle_id: int
    show_more: bool = False


class ForceRefreshBundleCallbackData(CallbackData, prefix="force_refresh"):
    profit_bundle_id: int


class WithdrawBundleCallbackData(CallbackData, prefix="withdraw"):
    profit_bundle_id: int


class CreateOrderCallbackData(CallbackData, prefix="create_order"):
    profit_bundle_id: int


def get_refresh_keyboard(profit_bundle_id):
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="Refresh",
        callback_data=RefreshBundleCallbackData(profit_bundle_id=profit_bundle_id),
    )
    keyboard.button(
        text="Buy",
        callback_data=CreateOrderCallbackData(profit_bundle_id=profit_bundle_id),
    )
    keyboard.button(
        text="Withdraw",
        callback_data=WithdrawBundleCallbackData(profit_bundle_id=profit_bundle_id),
    )
    keyboard.button(
        text="Force Refresh",
        callback_data=ForceRefreshBundleCallbackData(profit_bundle_id=profit_bundle_id),
    )
    keyboard.button(
        text="More",
        callback_data=RefreshBundleCallbackData(profit_bundle_id=profit_bundle_id, show_more=True),
    )

    keyboard.adjust(3)
    return keyboard.as_markup()
