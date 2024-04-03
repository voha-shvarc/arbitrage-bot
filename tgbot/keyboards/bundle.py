from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from abstract.abstract import AbstractExchange
from exchanges import EXCHANGES_MAPPING


class RefreshBundleCallbackData(CallbackData, prefix="refresh"):
    profit_bundle_id: int


class ForceRefreshBundleCallbackData(CallbackData, prefix="force_refresh"):
    profit_bundle_id: int
    withdraw_exchange_name: str
    deposit_exchange_name: str


class WithdrawBundleCallbackData(CallbackData, prefix="withdraw"):
    profit_bundle_id: int


class CreateOrderCallbackData(CallbackData, prefix="create_order"):
    profit_bundle_id: int
    withdraw_exchange_name: str
    deposit_exchange_name: str
    confirmed: bool = False
    set_limit: str = "False"


class CheckedBundleCallbackData(CallbackData, prefix="checked"):
    profit_bundle_id: int
    withdraw_exchange_name: str
    deposit_exchange_name: str


def _get_withdraw_status(
    withdraw_exchange_name: str,
    deposit_exchange_name: str,
    withdraw_label: str,
) -> str:
    withdraw_exchange: AbstractExchange = EXCHANGES_MAPPING[withdraw_exchange_name]
    deposit_exchange: AbstractExchange = EXCHANGES_MAPPING[deposit_exchange_name]

    labels = [withdraw_exchange.withdraw_status, deposit_exchange.deposit_status, withdraw_label]

    return " ".join([label for label in labels if label])


def get_bundle_keyboard(
    profit_bundle_id,
    withdraw_exchange_name: str,
    deposit_exchange_name: str,
    buy_confirmed: bool = False,
    buy_label: str = "",
    withdraw_label: str = "",
    buy_limit_label: str = "",
    force_refresh_label: str = "",
    checked_label: str = "",
):
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="Refresh",
        callback_data=RefreshBundleCallbackData(profit_bundle_id=profit_bundle_id),
    )
    keyboard.button(
        text=f"Buy {buy_label}",
        callback_data=CreateOrderCallbackData(
            profit_bundle_id=profit_bundle_id,
            withdraw_exchange_name=withdraw_exchange_name,
            deposit_exchange_name=deposit_exchange_name,
            confirmed=buy_confirmed,
        ),
    )

    keyboard.button(
        text=f"Force Refresh {force_refresh_label}",
        callback_data=ForceRefreshBundleCallbackData(
            profit_bundle_id=profit_bundle_id,
            withdraw_exchange_name=withdraw_exchange_name,
            deposit_exchange_name=deposit_exchange_name,
        ),
    )
    withdraw_label = _get_withdraw_status(withdraw_exchange_name, deposit_exchange_name, withdraw_label)
    keyboard.button(
        text=f"Withdraw {withdraw_label}",
        callback_data=WithdrawBundleCallbackData(profit_bundle_id=profit_bundle_id),
    )

    keyboard.button(
        text=f"Checked {checked_label}",
        callback_data=CheckedBundleCallbackData(
            profit_bundle_id=profit_bundle_id,
            withdraw_exchange_name=withdraw_exchange_name,
            deposit_exchange_name=deposit_exchange_name,
        ),
    )
    keyboard.button(
        text=f"Limit Buy {buy_limit_label}",
        callback_data=CreateOrderCallbackData(
            profit_bundle_id=profit_bundle_id,
            withdraw_exchange_name=withdraw_exchange_name,
            deposit_exchange_name=deposit_exchange_name,
            set_limit="True",
        ),
    )

    keyboard.adjust(2)
    return keyboard.as_markup()
