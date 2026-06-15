# handlers/admin_panel.py
"""Админки: старосты (над своей группой) и глобальная (полное администрирование)."""
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from handlers.start import get_main_keyboard
from states.admin_states import GlobalAdmin
from database.db_operations import (
    get_user_by_telegram_id, get_group_by_id,
    can_manage_group, create_invite, list_group_invites,
    list_group_members, set_member_role, remove_member,
    list_institutions, create_institution, set_global_role,
    get_institution_by_id, delete_institution, update_institution,
    list_groups_by_institution, delete_group, update_group,
    count_group_members, search_users, get_membership,
)


# ── Утилиты ────────────────────────────────────────────────────────────────────

async def _bot_username(message: types.Message) -> str:
    me = await message.bot.get_me()
    return me.username


def _invite_link(bot_username: str, code: str) -> str:
    return f"https://t.me/{bot_username}?start={code}"


def _role_label(role: str) -> str:
    return {"owner": "👑 Староста", "helper": "🛠 Помощник", "member": "👤 Участник"}.get(role, role)


def _is_admin(user_id) -> bool:
    u = get_user_by_telegram_id(telegram_id=user_id)
    return bool(u and u.global_role == "admin")


# ════════════════════════════════════════════════════════════════════════════════
#  АДМИНКА СТАРОСТЫ (/group)
# ════════════════════════════════════════════════════════════════════════════════

async def open_group_admin(message: types.Message, state: FSMContext = None):
    if state is not None:
        await state.finish()
    user = get_user_by_telegram_id(telegram_id=message.from_user.id)
    if not user or not user.active_group_id:
        await message.answer("Сначала войди в группу. Напиши /start")
        return
    if not can_manage_group(message.from_user.id, user.active_group_id):
        await message.answer("Управление группой доступно только старосте.")
        return
    group = get_group_by_id(user.active_group_id)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔗 Ссылка-приглашение", callback_data="ga_invite"))
    kb.add(InlineKeyboardButton("👥 Участники и помощники", callback_data="ga_members"))
    await message.answer(
        f"Управление группой «{group.name}»",
        reply_markup=kb,
    )


async def group_admin_callback(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    user_id = callback_query.from_user.id
    user = get_user_by_telegram_id(telegram_id=user_id)
    if not user or not user.active_group_id or not can_manage_group(user_id, user.active_group_id):
        await callback_query.answer("Нет доступа", show_alert=True)
        return
    group_id = user.active_group_id

    if data == "ga_invite":
        existing = [i for i in list_group_invites(group_id)
                    if i.invite_type == "join_group" and i.is_active]
        invite = existing[0] if existing else create_invite(
            "join_group", group_id=group_id, created_by=user_id)
        if not invite:
            await callback_query.message.answer("Не удалось создать ссылку.")
            await callback_query.answer()
            return
        bot_un = await _bot_username(callback_query.message)
        link = _invite_link(bot_un, invite.code)
        await callback_query.message.answer(
            "Ссылка-приглашение в группу. Отправь её одногруппникам — "
            "они вступят как обычные участники.\n\n"
            f"{link}"
        )
        await callback_query.answer()
        return

    if data == "ga_members":
        await _show_members(callback_query, group_id)
        return

    if data.startswith("ga_promote_"):
        set_member_role(group_id, int(data.replace("ga_promote_", "")), "helper")
        await callback_query.answer("Назначен помощником")
        await _show_members(callback_query, group_id, edit=True)
        return

    if data.startswith("ga_demote_"):
        set_member_role(group_id, int(data.replace("ga_demote_", "")), "member")
        await callback_query.answer("Снят до участника")
        await _show_members(callback_query, group_id, edit=True)
        return

    if data.startswith("ga_kick_"):
        remove_member(group_id, int(data.replace("ga_kick_", "")))
        await callback_query.answer("Удалён из группы")
        await _show_members(callback_query, group_id, edit=True)
        return


async def _show_members(callback_query, group_id, edit=False):
    members = list_group_members(group_id)
    kb = InlineKeyboardMarkup(row_width=1)
    lines = ["Участники группы:\n"]
    for m in members:
        u = get_user_by_telegram_id(telegram_id=m.user_id)
        name = u.first_name if u else str(m.user_id)
        lines.append(f"{_role_label(m.group_role)} — {name}")
        if m.group_role == "owner":
            continue
        if m.group_role == "member":
            kb.add(InlineKeyboardButton(f"⬆️ В помощники: {name}",
                                        callback_data=f"ga_promote_{m.user_id}"))
        elif m.group_role == "helper":
            kb.add(InlineKeyboardButton(f"⬇️ Снять помощника: {name}",
                                        callback_data=f"ga_demote_{m.user_id}"))
        kb.add(InlineKeyboardButton(f"❌ Удалить: {name}",
                                    callback_data=f"ga_kick_{m.user_id}"))
    text = "\n".join(lines) if len(lines) > 1 else "В группе пока только ты."
    target = callback_query.message
    if edit:
        try:
            await target.edit_text(text, reply_markup=kb)
            await callback_query.answer()
            return
        except Exception:
            pass
    await target.answer(text, reply_markup=kb)
    await callback_query.answer()


# ════════════════════════════════════════════════════════════════════════════════
#  ГЛОБАЛЬНАЯ АДМИНКА (/admin) — полное администрирование
# ════════════════════════════════════════════════════════════════════════════════

async def open_global_admin(message: types.Message, state: FSMContext = None):
    if state is not None:
        await state.finish()
    if not _is_admin(message.from_user.id):
        await message.answer("Раздел только для администратора.")
        return
    await message.answer("Админ-панель", reply_markup=_admin_root_kb())


def _admin_root_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🏛 Заведения", callback_data="adm_inst"))
    kb.add(InlineKeyboardButton("👥 Группы", callback_data="adm_groups"))
    kb.add(InlineKeyboardButton("🧑 Пользователи", callback_data="adm_users"))
    kb.add(InlineKeyboardButton("🎓 Выдать ссылку старосте", callback_data="adm_createlink"))
    return kb


async def global_admin_callback(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    user_id = callback_query.from_user.id
    if not _is_admin(user_id):
        await callback_query.answer("Нет доступа", show_alert=True)
        return

    # ── Корень ──
    if data == "adm_root":
        await _edit(callback_query, "Админ-панель", _admin_root_kb())
        return

    # ── РАЗДЕЛ: ЗАВЕДЕНИЯ ──
    if data == "adm_inst":
        await _show_institutions(callback_query)
        return
    if data == "adm_inst_add":
        await callback_query.message.answer("Введи название нового заведения:")
        await GlobalAdmin.waiting_for_institution_name.set()
        await callback_query.answer()
        return
    if data.startswith("adm_inst_view_"):
        await _show_institution(callback_query, int(data.replace("adm_inst_view_", "")))
        return
    if data.startswith("adm_inst_del_"):
        iid = int(data.replace("adm_inst_del_", ""))
        inst = get_institution_by_id(iid)
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("✅ Да, удалить заведение и все его группы",
                                    callback_data=f"adm_inst_delok_{iid}"))
        kb.add(InlineKeyboardButton("◀️ Отмена", callback_data="adm_inst"))
        await _edit(callback_query, f"Удалить «{inst.name if inst else iid}»?\n"
                    "Вместе с ним удалятся все его группы и их ДЗ.", kb)
        return
    if data.startswith("adm_inst_delok_"):
        delete_institution(int(data.replace("adm_inst_delok_", "")))
        await callback_query.answer("Заведение удалено")
        await _show_institutions(callback_query)
        return

    # ── РАЗДЕЛ: ГРУППЫ ──
    if data == "adm_groups":
        await _show_groups_institutions(callback_query)
        return
    if data.startswith("adm_groups_inst_"):
        await _show_groups_of(callback_query, int(data.replace("adm_groups_inst_", "")))
        return
    if data.startswith("adm_group_view_"):
        await _show_group(callback_query, int(data.replace("adm_group_view_", "")))
        return
    if data.startswith("adm_group_del_"):
        gid = int(data.replace("adm_group_del_", ""))
        g = get_group_by_id(gid)
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("✅ Да, удалить группу",
                                    callback_data=f"adm_group_delok_{gid}"))
        kb.add(InlineKeyboardButton("◀️ Отмена", callback_data=f"adm_group_view_{gid}"))
        await _edit(callback_query, f"Удалить группу «{g.name if g else gid}»?\n"
                    "Удалятся её участники и все ДЗ.", kb)
        return
    if data.startswith("adm_group_delok_"):
        gid = int(data.replace("adm_group_delok_", ""))
        g = get_group_by_id(gid)
        inst_id = g.institution_id if g else None
        delete_group(gid)
        await callback_query.answer("Группа удалена")
        if inst_id:
            await _show_groups_of(callback_query, inst_id)
        else:
            await _show_groups_institutions(callback_query)
        return
    if data.startswith("adm_group_members_"):
        await _show_group_members_admin(callback_query, int(data.replace("adm_group_members_", "")))
        return

    # ── РАЗДЕЛ: ПОЛЬЗОВАТЕЛИ ──
    if data == "adm_users":
        await callback_query.message.answer("Введи имя или username для поиска:")
        await GlobalAdmin.waiting_for_user_search.set()
        await callback_query.answer()
        return
    if data.startswith("adm_user_view_"):
        await _show_user(callback_query, int(data.replace("adm_user_view_", "")))
        return
    if data.startswith("adm_user_mod_"):
        uid = int(data.replace("adm_user_mod_", ""))
        set_global_role(uid, "moderator")
        await callback_query.answer("Назначен модератором")
        await _show_user(callback_query, uid)
        return
    if data.startswith("adm_user_admin_"):
        uid = int(data.replace("adm_user_admin_", ""))
        set_global_role(uid, "admin")
        await callback_query.answer("Назначен админом")
        await _show_user(callback_query, uid)
        return
    if data.startswith("adm_user_unrole_"):
        uid = int(data.replace("adm_user_unrole_", ""))
        set_global_role(uid, "user")
        await callback_query.answer("Глобальная роль снята")
        await _show_user(callback_query, uid)
        return

    # ── Выдать create_group-ссылку ──
    if data == "adm_createlink":
        insts = list_institutions()
        kb = InlineKeyboardMarkup(row_width=1)
        for inst in insts:
            kb.add(InlineKeyboardButton(f"🏛 {inst.name}", callback_data=f"adm_link_{inst.id}"))
        kb.add(InlineKeyboardButton("Без привязки к заведению", callback_data="adm_link_0"))
        kb.add(InlineKeyboardButton("◀️ Назад", callback_data="adm_root"))
        await _edit(callback_query, "К какому заведению привязать создаваемую группу?", kb)
        return
    if data.startswith("adm_link_"):
        iid = int(data.replace("adm_link_", ""))
        inv = create_invite("create_group", institution_id=(iid or None), created_by=user_id)
        if not inv:
            await callback_query.message.answer("Не удалось создать ссылку.")
            await callback_query.answer()
            return
        bot_un = await _bot_username(callback_query.message)
        link = _invite_link(bot_un, inv.code)
        await callback_query.message.answer(
            "Одноразовая ссылка для старосты на создание группы. "
            "Отдай её старосте — он создаст группу и станет её владельцем.\n\n"
            f"{link}"
        )
        await callback_query.answer()
        return


# ── Рендеры разделов ────────────────────────────────────────────────────────────

async def _edit(cb, text, kb):
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


async def _show_institutions(cb):
    insts = list_institutions()
    kb = InlineKeyboardMarkup(row_width=1)
    for i in insts:
        kb.add(InlineKeyboardButton(f"🏛 {i.name}", callback_data=f"adm_inst_view_{i.id}"))
    kb.add(InlineKeyboardButton("➕ Добавить заведение", callback_data="adm_inst_add"))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="adm_root"))
    await _edit(cb, "Заведения:" if insts else "Заведений пока нет.", kb)


async def _show_institution(cb, iid):
    inst = get_institution_by_id(iid)
    if not inst:
        await cb.answer("Не найдено", show_alert=True)
        return
    groups = list_groups_by_institution(iid)
    text = (f"🏛 {inst.name}\n"
            f"Город: {inst.city or '—'}\n"
            f"Расписание: {inst.schedule_provider or 'нет'}\n"
            f"Групп: {len(groups)}")
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"👥 Группы заведения ({len(groups)})",
                                callback_data=f"adm_groups_inst_{iid}"))
    kb.add(InlineKeyboardButton("🗑 Удалить заведение", callback_data=f"adm_inst_del_{iid}"))
    kb.add(InlineKeyboardButton("◀️ К заведениям", callback_data="adm_inst"))
    await _edit(cb, text, kb)


async def _show_groups_institutions(cb):
    insts = list_institutions()
    kb = InlineKeyboardMarkup(row_width=1)
    for i in insts:
        kb.add(InlineKeyboardButton(f"🏛 {i.name}", callback_data=f"adm_groups_inst_{i.id}"))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="adm_root"))
    await _edit(cb, "Выбери заведение, чтобы посмотреть его группы:" if insts
                else "Заведений нет.", kb)


async def _show_groups_of(cb, iid):
    inst = get_institution_by_id(iid)
    groups = list_groups_by_institution(iid)
    kb = InlineKeyboardMarkup(row_width=1)
    for g in groups:
        n = count_group_members(g.id)
        kb.add(InlineKeyboardButton(f"{g.name} ({n} чел.)",
                                    callback_data=f"adm_group_view_{g.id}"))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="adm_groups"))
    await _edit(cb, f"Группы «{inst.name if inst else ''}»:" if groups
                else "В этом заведении нет групп.", kb)


async def _show_group(cb, gid):
    g = get_group_by_id(gid)
    if not g:
        await cb.answer("Не найдено", show_alert=True)
        return
    n = count_group_members(gid)
    owner_name = "—"
    owners = list_group_members(gid, role="owner")
    if owners:
        ou = get_user_by_telegram_id(telegram_id=owners[0].user_id)
        owner_name = ou.first_name if ou else str(owners[0].user_id)
    text = (f"Группа «{g.name}»\n"
            f"Староста: {owner_name}\n"
            f"Участников: {n}\n"
            f"ID расписания: {g.external_schedule_id or 'не задан'}")
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("👥 Участники", callback_data=f"adm_group_members_{gid}"))
    kb.add(InlineKeyboardButton("🗑 Удалить группу", callback_data=f"adm_group_del_{gid}"))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data=f"adm_groups_inst_{g.institution_id}"))
    await _edit(cb, text, kb)


async def _show_group_members_admin(cb, gid):
    members = list_group_members(gid)
    lines = ["Участники:\n"]
    for m in members:
        u = get_user_by_telegram_id(telegram_id=m.user_id)
        name = u.first_name if u else str(m.user_id)
        handle = f" (@{u.username})" if u and u.username else ""
        lines.append(f"{_role_label(m.group_role)} — {name}{handle}")
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data=f"adm_group_view_{gid}"))
    await _edit(cb, "\n".join(lines) if len(lines) > 1 else "В группе нет участников.", kb)


async def _show_user(cb, uid):
    u = get_user_by_telegram_id(telegram_id=uid)
    if not u:
        await cb.answer("Не найден", show_alert=True)
        return
    handle = f"@{u.username}" if u.username else "—"
    text = (f"Пользователь: {u.first_name}\n"
            f"Username: {handle}\n"
            f"Telegram ID: {u.user_id}\n"
            f"Глобальная роль: {u.global_role}")
    kb = InlineKeyboardMarkup(row_width=1)
    if u.global_role != "moderator":
        kb.add(InlineKeyboardButton("Назначить модератором", callback_data=f"adm_user_mod_{uid}"))
    if u.global_role != "admin":
        kb.add(InlineKeyboardButton("Назначить админом", callback_data=f"adm_user_admin_{uid}"))
    if u.global_role != "user":
        kb.add(InlineKeyboardButton("Снять глобальную роль", callback_data=f"adm_user_unrole_{uid}"))
    kb.add(InlineKeyboardButton("◀️ Закрыть", callback_data="adm_root"))
    await _edit(cb, text, kb)


# ── FSM-обработчики ввода ────────────────────────────────────────────────────────

async def process_institution_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if name.startswith("/"):
        await state.finish()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(message.from_user.id))
        return
    if len(name) < 2:
        await message.answer("Слишком короткое название. Введи ещё раз:")
        return
    await state.update_data(inst_name=name)
    await message.answer("Введи город (или напиши «-», чтобы пропустить):")
    await GlobalAdmin.waiting_for_institution_city.set()


async def process_institution_city(message: types.Message, state: FSMContext):
    city = message.text.strip()
    city = None if city in ("-", "—") else city
    await state.update_data(inst_city=city)
    await message.answer(
        "Провайдер расписания? Введи код провайдера (например omgtu) "
        "или напиши «-», если расписания нет:"
    )
    await GlobalAdmin.waiting_for_institution_provider.set()


async def process_institution_provider(message: types.Message, state: FSMContext):
    prov = message.text.strip()
    prov = None if prov in ("-", "—") else prov
    data = await state.get_data()
    inst = create_institution(name=data["inst_name"], city=data.get("inst_city"),
                              schedule_provider=prov)
    await state.finish()
    if inst:
        await message.answer(f"Заведение «{inst.name}» добавлено.",
                             reply_markup=get_main_keyboard(message.from_user.id))
    else:
        await message.answer("Не удалось добавить заведение.",
                             reply_markup=get_main_keyboard(message.from_user.id))


async def process_user_search(message: types.Message, state: FSMContext):
    q = message.text.strip()
    if q.startswith("/"):
        await state.finish()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(message.from_user.id))
        return
    await state.finish()
    found = search_users(q)
    if not found:
        await message.answer("Никого не нашёл. Попробуй /admin → Пользователи ещё раз.",
                             reply_markup=get_main_keyboard(message.from_user.id))
        return
    kb = InlineKeyboardMarkup(row_width=1)
    for u in found[:15]:
        handle = f" (@{u.username})" if u.username else ""
        kb.add(InlineKeyboardButton(f"{u.first_name}{handle}",
                                    callback_data=f"adm_user_view_{u.user_id}"))
    await message.answer(f"Найдено: {len(found)}", reply_markup=kb)
