from aiogram.dispatcher.filters.state import State, StatesGroup


class GroupAdmin(StatesGroup):
    """Админка старосты (owner) над своей группой."""
    menu = State()


class GlobalAdmin(StatesGroup):
    """Глобальная админка (admin)."""
    waiting_for_institution_name     = State()  # ввод названия нового заведения
    waiting_for_institution_city     = State()  # ввод города
    waiting_for_institution_provider = State()  # ввод провайдера расписания
    waiting_for_schedule_id          = State()  # external_schedule_id для группы
    waiting_for_user_search          = State()  # поиск пользователя по имени
    waiting_for_moderator_id         = State()  # назначение модератора по ID
