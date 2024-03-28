from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder


class RefreshBundleCallbackData(CallbackData, prefix="refresh"):
    profit_bundle_id: int


class ForceRefreshBundleCallbackData(CallbackData, prefix="force_refresh"):
    profit_bundle_id: int


class WithdrawBundleCallbackData(CallbackData, prefix="withdraw"):
    profit_bundle_id: int


class CreateOrderCallbackData(CallbackData, prefix="create_order"):
    profit_bundle_id: int
    confirmed: bool = False
    set_limit: str = "False"


def get_bundle_keyboard(
        profit_bundle_id,
        buy_confirmed: bool = False,
        buy_label: str = "",
        withdraw_label: str = "",
        buy_limit_label: str = ""
):
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="Refresh",
        callback_data=RefreshBundleCallbackData(profit_bundle_id=profit_bundle_id),
    )
    keyboard.button(
        text=f"Buy {buy_label}",
        callback_data=CreateOrderCallbackData(profit_bundle_id=profit_bundle_id, confirmed=buy_confirmed),
    )

    keyboard.button(
        text="Force Refresh",
        callback_data=ForceRefreshBundleCallbackData(profit_bundle_id=profit_bundle_id),
    )
    keyboard.button(
        text=f"Withdraw {withdraw_label}",
        callback_data=WithdrawBundleCallbackData(profit_bundle_id=profit_bundle_id),
    )

    keyboard.button(
        text=f"Limit Buy {buy_limit_label}",
        callback_data=CreateOrderCallbackData(profit_bundle_id=profit_bundle_id, set_limit="True"),
    )

    keyboard.adjust(2)
    return keyboard.as_markup()
