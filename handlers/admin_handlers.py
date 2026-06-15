from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from handlers.start import get_main_keyboard
from database.db_operations import (
    get_user_by_telegram_id, get_group_by_id, list_group_members,
)


def _help_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Как работает бот"))
    kb.add(KeyboardButton("Сообщить об ошибке"))
    kb.add(KeyboardButton("Хочу заполнять ДЗ"))
    kb.add(KeyboardButton("Связаться со старостой"))
    kb.add(KeyboardButton("🔙 Назад"))
    return kb


def _back_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🔙 Назад"))
    return kb


def _owner_contact(user_id: int):
    """(имя_группы, имя_старосты, @username|None) или None если не в группе."""
    user = get_user_by_telegram_id(telegram_id=user_id)
    if not user or not user.active_group_id:
        return None
    group = get_group_by_id(user.active_group_id)
    if not group:
        return None
    owners = list_group_members(user.active_group_id, role="owner")
    if not owners:
        return (group.name, None, None)
    owner = get_user_by_telegram_id(telegram_id=owners[0].user_id)
    if not owner:
        return (group.name, None, None)
    handle = f"@{owner.username}" if owner.username else None
    return (group.name, owner.first_name, handle)


def _owner_line(user_id: int) -> str:
    info = _owner_contact(user_id)
    if info is None:
        return "Ты пока не в группе. Чтобы вступить, нужна ссылка-приглашение от старосты."
    group_name, owner_name, handle = info
    if handle:
        return f"Староста группы «{group_name}» — {owner_name}, {handle}."
    if owner_name:
        return f"Староста группы «{group_name}» — {owner_name}. Напиши ему в чате группы."
    return f"В группе «{group_name}» пока нет старосты с контактом."


async def show_help_menu(message: types.Message):
    text = (
        "Помощь\n\n"
        "Выбери раздел ниже."
    )
    await message.answer(text, reply_markup=_help_keyboard())


async def how_working_bot(message: types.Message):
    text = (
        "Как работает бот\n\n"
        "Бот хранит домашние задания твоей группы.\n\n"
        "Посмотреть ДЗ — задания на сегодня, завтра или выбранную дату, "
        "вместе с прикреплёнными файлами.\n\n"
        "Добавление и удаление заданий доступно старосте и его помощникам.\n\n"
        "Если ты в нескольких группах — переключайся между ними в профиле. "
        "Бот всегда показывает задания активной группы."
    )
    await message.answer(text, reply_markup=_back_keyboard())


async def find_mistacke_bot(message: types.Message):
    text = (
        "Сообщить об ошибке\n\n"
        "Опиши, что произошло: что ты делал и какое сообщение увидел. "
        "Если есть скриншот — приложи его.\n\n"
        + _owner_line(message.from_user.id)
    )
    await message.answer(text, reply_markup=_back_keyboard())


async def Wanna_create_homework(message: types.Message):
    text = (
        "Как получить право заполнять ДЗ\n\n"
        "Добавлять и удалять задания может староста группы и назначенные им помощники.\n\n"
        "Чтобы стать помощником, обратись к старосте своей группы.\n\n"
        + _owner_line(message.from_user.id)
    )
    await message.answer(text, reply_markup=_back_keyboard())


async def write_me(message: types.Message):
    text = (
        "Связаться со старостой\n\n"
        "По вопросам о заданиях, расписании и доступе пиши старосте своей группы.\n\n"
        + _owner_line(message.from_user.id)
    )
    await message.answer(text, reply_markup=_back_keyboard())
