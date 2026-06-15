from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_date_selection_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Сегодня", callback_data="date_today"))
    keyboard.add(InlineKeyboardButton("Завтра", callback_data="date_tomorrow"))
    keyboard.add(InlineKeyboardButton("Выбрать дату", callback_data="date_custom"))
    return keyboard