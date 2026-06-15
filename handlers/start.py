from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from config import ADMIN_IDS
from database.db_operations import (
    get_user_by_telegram_id, create_user, update_user_subgroup,
    set_active_group, set_global_role,
    get_invite_by_code, is_invite_usable, mark_invite_used,
    create_group, add_member, get_group_by_id,
    get_membership, list_user_memberships,
)
from states.user_states import UserRegistration, Onboarding

# Временное хранилище данных регистрации (в памяти процесса).
# TODO (Этап 6): вынести в Redis, чтобы переживало рестарт и работало на нескольких воркерах.
temp_users = {}


# ── Клавиатуры ─────────────────────────────────────────────────────────────────

def get_main_keyboard(user_id: int):
    """Главное меню адаптируется под роль:
    - все видят «Посмотреть ДЗ» и «Помощь»;
    - староста/помощник/админ дополнительно видят «Добавить/Удалить ДЗ»;
    - староста/админ видят «Управление группой»."""
    from database.db_operations import can_edit_homework, can_manage_group
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📚 Посмотреть ДЗ"))

    user = get_user_by_telegram_id(telegram_id=user_id)
    group_id = user.active_group_id if user else None

    if group_id and can_edit_homework(user_id, group_id):
        kb.add(KeyboardButton("➕ Добавить ДЗ"), KeyboardButton("❌ Удалить ДЗ"))
    if group_id and can_manage_group(user_id, group_id):
        kb.add(KeyboardButton("⚙️ Управление группой"))

    kb.add(KeyboardButton("👤 Профиль"), KeyboardButton("❓ Помощь"))
    return kb


def subgroup_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("1 подгруппа"), KeyboardButton("2 подгруппа"))
    return kb


# ── /start ─────────────────────────────────────────────────────────────────────

async def process_start_command(message: types.Message, state: FSMContext):
    await state.finish()
    user_id = message.from_user.id

    # Синхронизация глобальной роли админа: если ID в ADMIN_IDS, но пользователь
    # уже есть в БД с другой ролью — подтянем admin. Работает при каждом /start,
    # поэтому нового админа достаточно добавить в переменную ADMIN_IDS и перезапустить.
    if user_id in ADMIN_IDS:
        existing = get_user_by_telegram_id(telegram_id=user_id)
        if existing and existing.global_role != "admin":
            set_global_role(user_id, "admin")

    # 1) Deep-link с кодом приглашения: /start <code> или ссылка t.me/bot?start=<code>
    args = message.get_args()
    if args:
        code = args.strip()
        await handle_invite_code(message, state, code)
        return

    # 2) Уже зарегистрирован?
    user = get_user_by_telegram_id(telegram_id=user_id)
    if user:
        await route_existing_user(message, user)
        return

    # 3) Новый пользователь без ссылки — сначала имя, потом попросим код.
    temp_users[user_id] = {
        'username': message.from_user.username,
        'tg_first_name': message.from_user.first_name,
        'tg_last_name': message.from_user.last_name,
        'pending_invite': None,
    }
    await ask_name(message)


async def ask_name(message: types.Message):
    welcome = "Привет! 👋 Я бот для отслеживания домашних заданий.\nКак тебя зовут?"
    if message.from_user.first_name:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(KeyboardButton(f"Использовать '{message.from_user.first_name}'"))
        kb.add(KeyboardButton("Ввести другое имя"))
        await message.answer(
            f"{welcome}\n\nВижу, тебя зовут {message.from_user.first_name}. Использовать это имя?",
            reply_markup=kb,
        )
    else:
        await message.answer(welcome, reply_markup=ReplyKeyboardRemove())
    await UserRegistration.waiting_for_name.set()


async def route_existing_user(message: types.Message, user):
    """Маршрутизация зарегистрированного пользователя в зависимости от наличия группы."""
    user_id = message.from_user.id
    memberships = list_user_memberships(user_id)

    if not user.active_group_id or not memberships:
        # Зарегистрирован, но не в группе — нужен код приглашения.
        await message.answer(
            f"С возвращением, {user.first_name}! 👋\n\n"
            "Ты пока не состоишь ни в одной группе.\n"
            "Введи код приглашения, который тебе дал староста, "
            "или перейди по ссылке-приглашению:",
            reply_markup=ReplyKeyboardRemove(),
        )
        await Onboarding.waiting_for_invite_code.set()
        return

    group = get_group_by_id(user.active_group_id)
    gname = group.name if group else "—"
    await message.answer(
        f"С возвращением, {user.first_name}! 👋\nТвоя группа: {gname}\n\nВыбери опцию:",
        reply_markup=get_main_keyboard(user_id),
    )


# ── Обработка кода приглашения ─────────────────────────────────────────────────

async def handle_invite_code(message: types.Message, state: FSMContext, code: str):
    """Единая точка разбора инвайта (и из deep-link, и из ручного ввода)."""
    user_id = message.from_user.id
    invite = get_invite_by_code(code)
    ok, reason = is_invite_usable(invite)
    if not ok:
        await message.answer(
            f"❌ {reason}.\n\nПопроси актуальную ссылку у старосты или администратора."
        )
        # Если новый пользователь — всё равно зарегистрируем имя, чтобы не потерять.
        if not get_user_by_telegram_id(telegram_id=user_id):
            temp_users.setdefault(user_id, {
                'username': message.from_user.username,
                'tg_first_name': message.from_user.first_name,
                'tg_last_name': message.from_user.last_name,
                'pending_invite': None,
            })
            await ask_name(message)
        return

    # Гарантируем, что пользователь существует в БД.
    user = get_user_by_telegram_id(telegram_id=user_id)
    if not user:
        # Запомним инвайт и сначала спросим имя; применим после регистрации.
        temp_users[user_id] = {
            'username': message.from_user.username,
            'tg_first_name': message.from_user.first_name,
            'tg_last_name': message.from_user.last_name,
            'pending_invite': code,
        }
        await ask_name(message)
        return

    # Пользователь есть — применяем инвайт сразу.
    await apply_invite(message, state, user, invite)


async def apply_invite(message: types.Message, state: FSMContext, user, invite):
    """Применяет уже проверенный инвайт к существующему пользователю."""
    user_id = message.from_user.id

    if invite.invite_type == "create_group":
        # Ветка старосты: попросим название группы, создадим её на следующем шаге.
        await state.update_data(create_invite_code=invite.code,
                                institution_id=invite.institution_id)
        await message.answer(
            "🎓 По этой ссылке ты можешь создать свою группу и стать её старостой.\n\n"
            "Введи название группы (например: ИС-301):",
            reply_markup=ReplyKeyboardRemove(),
        )
        await Onboarding.waiting_for_group_name.set()
        return

    if invite.invite_type == "join_group":
        group = get_group_by_id(invite.group_id)
        if not group:
            await message.answer("❌ Группа из ссылки не найдена. Попроси новую ссылку.")
            return
        # Уже состоит в этой группе? Просто делаем её активной.
        if get_membership(group.id, user_id):
            set_active_group(user_id, group.id)
            await message.answer(
                f"Ты уже в группе «{group.name}». Сделал её активной ✅",
                reply_markup=get_main_keyboard(user_id),
            )
            await state.finish()
            return
        add_member(group.id, user_id, group_role="member")
        set_active_group(user_id, group.id)
        mark_invite_used(invite.code)
        await message.answer(
            f"✅ Ты вступил(а) в группу «{group.name}»!\n\n"
            "Теперь укажи свою подгруппу:",
            reply_markup=subgroup_keyboard(),
        )
        await UserRegistration.waiting_for_subgroup.set()
        return

    await message.answer("❌ Неизвестный тип ссылки.")


# ── Регистрация имени ──────────────────────────────────────────────────────────

async def process_user_name(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in temp_users:
        await message.answer("❌ Что-то пошло не так. Напиши /start ещё раз")
        await state.finish()
        return

    data = temp_users[user_id]
    if message.text == "Отмена":
        del temp_users[user_id]
        await state.finish()
        return
    elif message.text.startswith("Использовать '"):
        first_name = data['tg_first_name']
    elif message.text == "Ввести другое имя":
        kb = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("Отмена"))
        await message.answer("Напиши своё имя:", reply_markup=kb)
        return
    else:
        first_name = message.text.strip()
        if len(first_name) < 2:
            await message.answer("❌ Имя слишком короткое. Попробуй ещё раз:")
            return

    # Создаём пользователя в БД.
    user = create_user(
        telegram_id=user_id,
        username=data.get('username'),
        first_name=first_name,
        last_name=data.get('tg_last_name'),
    )
    if not user:
        from database import db_operations as _ops
        import logging
        reason = _ops.LAST_ERROR or "неизвестная причина"
        logging.warning(f"REGISTER FAIL: user_id={user_id}, причина={reason}")
        await message.answer(
            "❌ Ошибка при регистрации.\n\n"
            f"Причина: {reason}\n\n"
            "Попробуй /start"
        )
        await state.finish()
        return

    # Если глобально это владелец из ADMIN_IDS — выдадим роль admin.
    if user_id in ADMIN_IDS:
        set_global_role(user_id, "admin")

    pending = data.get('pending_invite')
    del temp_users[user_id]

    if pending:
        invite = get_invite_by_code(pending)
        ok, reason = is_invite_usable(invite)
        if ok:
            await apply_invite(message, state, user, invite)
            return
        else:
            await message.answer(f"⚠️ Ссылка больше недействительна: {reason}.")

    # Имени достаточно, но группы нет — просим код.
    await message.answer(
        f"Приятно познакомиться, {first_name}! 🎉\n\n"
        "Чтобы начать, введи код приглашения от старосты "
        "или перейди по ссылке-приглашению группы:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await Onboarding.waiting_for_invite_code.set()


# ── Ручной ввод кода приглашения ───────────────────────────────────────────────

async def process_invite_code_input(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if not code:
        await message.answer("Введи код приглашения текстом.")
        return
    # Команды (/admin, /group, /start и т.п.) не являются кодом приглашения.
    # Сбрасываем состояние ожидания кода и просим повторить команду —
    # её подхватит соответствующий обработчик (они с state="*").
    if code.startswith("/"):
        await state.finish()
        await message.answer("Окей, отменил ввод кода. Повтори команду ещё раз.")
        return
    await handle_invite_code(message, state, code)


async def cancel_any_state(message: types.Message, state: FSMContext):
    """Универсальный выход из любого состояния по /cancel."""
    await state.finish()
    user = get_user_by_telegram_id(telegram_id=message.from_user.id)
    if user and user.active_group_id:
        await message.answer("Отменено.", reply_markup=get_main_keyboard(message.from_user.id))
    else:
        await message.answer("Отменено. Напиши /start, чтобы начать.")


# ── Создание группы старостой ──────────────────────────────────────────────────

async def process_group_name(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    name = message.text.strip()
    # Команда вместо названия — выходим из создания группы.
    if name.startswith("/"):
        await state.finish()
        await message.answer("Создание группы отменено. Повтори команду ещё раз.")
        return
    if len(name) < 2:
        await message.answer("❌ Слишком короткое название. Введи название группы:")
        return

    data = await state.get_data()
    code = data.get('create_invite_code')
    institution_id = data.get('institution_id')

    invite = get_invite_by_code(code) if code else None
    ok, reason = is_invite_usable(invite)
    if not ok:
        await message.answer(f"❌ Ссылка на создание группы недействительна: {reason}.")
        await state.finish()
        return

    group = create_group(institution_id=institution_id, name=name, owner_user_id=user_id)
    if not group:
        await message.answer("❌ Не удалось создать группу. Попробуй ещё раз позже.")
        await state.finish()
        return

    # Создатель становится старостой (owner) и активной делается эта группа.
    add_member(group.id, user_id, group_role="owner")
    set_active_group(user_id, group.id)
    mark_invite_used(code)

    # Привязка расписания (выбор корпус→группа, если провайдер поддерживает).
    try:
        from handlers.schedule_setup import start_schedule_binding
        await start_schedule_binding(message, state, group.id)
    except Exception as e:
        import logging
        logging.getLogger("start").exception(f"Ошибка привязки расписания: {e}")
        # Подстраховка: не ломаем онбординг, идём к подгруппе.
        await state.finish()
        await message.answer(
            f"Группа «{group.name}» создана, ты её староста.\n\n"
            "Укажи свою подгруппу:",
            reply_markup=subgroup_keyboard(),
        )
        await UserRegistration.waiting_for_subgroup.set()


# ── Подгруппа ──────────────────────────────────────────────────────────────────

async def process_user_subgroup(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()
    if "1" in text:
        subgroup = "1"
    elif "2" in text:
        subgroup = "2"
    else:
        await message.answer("Выбери: 1 подгруппа или 2 подгруппа", reply_markup=subgroup_keyboard())
        return

    update_user_subgroup(telegram_id=user_id, subgroup=subgroup)
    # Дублируем подгруппу в членство активной группы.
    user = get_user_by_telegram_id(telegram_id=user_id)
    if user and user.active_group_id:
        add_member(user.active_group_id, user_id, group_role=_keep_role(user.active_group_id, user_id), subgroup=subgroup)

    await message.answer(
        f"✅ Подгруппа {subgroup} сохранена!",
        reply_markup=get_main_keyboard(user_id),
    )
    await state.finish()


def _keep_role(group_id, user_id):
    """Не понижаем роль при обновлении подгруппы — берём текущую."""
    m = get_membership(group_id, user_id)
    return m.group_role if m else "member"


# ── Вспомогательное ────────────────────────────────────────────────────────────

async def check_active_group(message: types.Message):
    """Возвращает group_id активной группы или None (с подсказкой пользователю)."""
    user = get_user_by_telegram_id(telegram_id=message.from_user.id)
    if not user:
        await message.answer("Сначала напиши /start")
        return None
    if not user.active_group_id:
        await message.answer("⚠️ Ты не в группе. Введи код приглашения или напиши /start")
        return None
    return user.active_group_id


def get_user_info(user_id: int):
    try:
        user = get_user_by_telegram_id(telegram_id=user_id)
        if user:
            return {'id': user.id, 'first_name': user.first_name,
                    'username': user.username, 'subgroup': user.subgroup,
                    'active_group_id': user.active_group_id,
                    'global_role': user.global_role}
        return None
    except Exception as e:
        print(f"Ошибка get_user_info: {e}")
        return None
