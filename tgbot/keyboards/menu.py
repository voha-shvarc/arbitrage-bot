from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_menu_keyboard():
    keyboard = ReplyKeyboardBuilder()

    keyboard.button(
        text="Total Balance",
    )

    return keyboard.as_markup(resize_keyboard=True)
