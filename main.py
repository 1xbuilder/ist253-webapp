import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.types import ContentType
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from config import TOKEN

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

from handlers.start import (process_start_command, get_main_keyboard,
                             process_user_name, process_user_subgroup,
                             process_invite_code_input, process_group_name,
                             cancel_any_state, check_active_group)
from handlers.homework import (show_homework_menu, back_to_main_menu,
                                show_date_selection, show_today_homework,
                                show_tomorrow_homework, show_week_homework)
from handlers.admin_handlers import (show_help_menu, how_working_bot,
                                      find_mistacke_bot, Wanna_create_homework, write_me)
from handlers.calendar_handlers import handle_calendar_callback, show_date_selection as show_calendar_date_selection
from handlers.add_homework import (start_add_homework, process_date, process_subject,
                                    process_task, process_attachment_text,
                                    process_attachment_media, confirm_add_homework,
                                    cancel_add_homework)
from handlers.delete_homework import (start_delete_homework, process_date_selection,
                                       process_homework_selection, confirm_deletion)
from handlers.admin_panel import (open_group_admin, open_global_admin,
                                   group_admin_callback, global_admin_callback,
                                   process_institution_name, process_institution_city,
                                   process_institution_provider, process_user_search,
                                   process_schedule_id)
from handlers.profile import (open_profile, profile_callback, process_new_name)
from handlers.schedule_setup import (campus_chosen, group_chosen, manual_or_id_input)
from states.homework_states import AddHomework
from states.user_states import UserRegistration, Onboarding, Profile
from states.admin_states import GlobalAdmin
from states.delete_states import DeleteHomework

# ── Команды (всегда первый приоритет, в любом состоянии) ─────────
dp.register_message_handler(process_start_command, commands=['start'], state="*")
dp.register_message_handler(open_group_admin,  commands=['group'], state="*")
dp.register_message_handler(open_global_admin, commands=['admin'], state="*")
dp.register_message_handler(cancel_any_state,   commands=['cancel'], state="*")
dp.register_message_handler(open_profile,       commands=['profile'], state="*")

# ── Профиль (имя, группы, выход) ─────────────────────────────────
dp.register_message_handler(open_profile,     lambda m: m.text == "👤 Профиль", state="*")
dp.register_message_handler(process_new_name, state=Profile.waiting_for_new_name)
dp.register_callback_query_handler(profile_callback, lambda c: c.data.startswith('pf_'), state="*")

# ── Регистрация и онбординг (имя -> код/создание группы -> подгруппа) ──
dp.register_message_handler(process_user_name,        state=UserRegistration.waiting_for_name)
dp.register_message_handler(process_user_subgroup,    state=UserRegistration.waiting_for_subgroup)
dp.register_message_handler(process_invite_code_input, state=Onboarding.waiting_for_invite_code)
dp.register_message_handler(process_group_name,        state=Onboarding.waiting_for_group_name)
# Привязка расписания при создании группы (корпус → группа кнопками / ручной ввод)
dp.register_callback_query_handler(campus_chosen, lambda c: c.data.startswith('sb_campus_'), state=Onboarding.waiting_for_campus)
dp.register_callback_query_handler(group_chosen,  lambda c: c.data.startswith('sb_group'), state=Onboarding.waiting_for_sched_group)
dp.register_message_handler(manual_or_id_input,   state=Onboarding.waiting_for_sched_group)

# ── Главное меню ─────────────────────────────────────────────────
dp.register_message_handler(show_homework_menu,   lambda m: m.text == "📚 Посмотреть ДЗ")
dp.register_message_handler(start_add_homework,   lambda m: m.text == "➕ Добавить ДЗ")
dp.register_message_handler(start_delete_homework,lambda m: m.text == "❌ Удалить ДЗ")
dp.register_message_handler(show_help_menu,        lambda m: m.text == "❓ Помощь")
dp.register_message_handler(open_group_admin,      lambda m: m.text == "⚙️ Управление группой", state="*")

# ── Помощь ───────────────────────────────────────────────────────
dp.register_message_handler(how_working_bot,     lambda m: m.text == "Как работает бот")
dp.register_message_handler(find_mistacke_bot,   lambda m: m.text == "Сообщить об ошибке")
dp.register_message_handler(Wanna_create_homework,lambda m: m.text == "Хочу заполнять ДЗ")
dp.register_message_handler(write_me,            lambda m: m.text == "Связаться со старостой")

# ── Просмотр ДЗ ──────────────────────────────────────────────────
dp.register_message_handler(show_today_homework,    lambda m: m.text == "Сегодня")
dp.register_message_handler(show_tomorrow_homework, lambda m: m.text == "Завтра")
dp.register_message_handler(show_date_selection,    lambda m: m.text == "Выбрать дату")

# ── Удаление ДЗ ──────────────────────────────────────────────────
dp.register_message_handler(start_delete_homework,   lambda m: m.text == "❌ Удалить ДЗ", state="*")
dp.register_message_handler(process_date_selection,  state=DeleteHomework.waiting_for_date_selection)
dp.register_message_handler(process_homework_selection, state=DeleteHomework.waiting_for_homework_selection)
dp.register_message_handler(confirm_deletion,        state=DeleteHomework.waiting_for_confirmation)

# ── Админки (коллбэки; команды зарегистрированы выше) ────────────
dp.register_callback_query_handler(group_admin_callback,  lambda c: c.data.startswith('ga_'), state="*")
dp.register_callback_query_handler(global_admin_callback, lambda c: c.data.startswith('adm_'), state="*")
dp.register_message_handler(process_institution_name,     state=GlobalAdmin.waiting_for_institution_name)
dp.register_message_handler(process_institution_city,     state=GlobalAdmin.waiting_for_institution_city)
dp.register_message_handler(process_institution_provider, state=GlobalAdmin.waiting_for_institution_provider)
dp.register_message_handler(process_user_search,          state=GlobalAdmin.waiting_for_user_search)
dp.register_message_handler(process_schedule_id,          state=GlobalAdmin.waiting_for_schedule_id)

# ── Календарь ────────────────────────────────────────────────────
dp.register_callback_query_handler(
    handle_calendar_callback,
    lambda c: c.data.startswith(('calendar_', 'date_select_', 'ignore'))
)

# ── Добавление ДЗ (FSM) ──────────────────────────────────────────
dp.register_message_handler(cancel_add_homework, lambda m: m.text == "Отмена", state="*")
dp.register_message_handler(process_date,        state=AddHomework.waiting_for_date)
dp.register_message_handler(process_subject,     state=AddHomework.waiting_for_subject)
dp.register_message_handler(process_task,        state=AddHomework.waiting_for_task)

dp.register_message_handler(
    process_attachment_text,
    lambda m: m.text in ["Пропустить", "Завершить добавление файлов"],
    state=AddHomework.waiting_for_attachment
)
dp.register_message_handler(
    process_attachment_media,
    content_types=[ContentType.PHOTO, ContentType.DOCUMENT,
                   ContentType.VIDEO, ContentType.AUDIO, ContentType.VOICE],
    state=AddHomework.waiting_for_attachment
)
dp.register_message_handler(confirm_add_homework, state=AddHomework.waiting_for_confirmation)

# ── Назад ────────────────────────────────────────────────────────
dp.register_message_handler(back_to_main_menu, lambda m: m.text in ("🔙 Назад", "Назад"))

async def on_startup(dp):
    from photo_proxy import start_proxy
    await start_proxy()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # httpx логирует каждый запрос к Supabase — приглушаем, чтобы не засорять логи.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from config import SUPABASE_URL
    logging.warning(f"STARTUP: бот стартует, база = {SUPABASE_URL}")
    print("Бот запущен...", flush=True)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
