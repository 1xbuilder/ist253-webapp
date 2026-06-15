# handlers/profile.py
"""Профиль пользователя: имя, переключение между группами, выход из группы."""
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from handlers.start import get_main_keyboard
from states.user_states import Profile
from database.db_operations import (
    get_user_by_telegram_id, get_group_by_id,
    list_user_groups_detailed, set_active_group,
    update_user_name, leave_group, get_membership,
)


def _role_label(role: str) -> str:
    return {"owner": "👑 староста", "helper": "🛠 помощник", "member": "участник"}.get(role, role)


async def open_profile(message: types.Message, state: FSMContext = None):
    if state is not None:
        await state.finish()
    await _render_profile(message.from_user.id, message)


async def _render_profile(user_id, message_or_cb, edit=False):
    user = get_user_by_telegram_id(telegram_id=user_id)
    if not user:
        target = message_or_cb.message if hasattr(message_or_cb, "message") else message_or_cb
        await target.answer("Сначала напиши /start")
        return

    groups = list_user_groups_detailed(user_id)
    lines = [f"👤 <b>{user.first_name}</b>"]
    if user.username:
        lines.append(f"@{user.username}")
    lines.append("")

    kb = InlineKeyboardMarkup(row_width=1)
    if groups:
        lines.append("Твои группы:")
        for m, g in groups:
            mark = "✅ " if g.id == user.active_group_id else ""
            lines.append(f"{mark}• {g.name} — {_role_label(m.group_role)}")
            # Кнопка переключения только для неактивных
            if g.id != user.active_group_id:
                kb.add(InlineKeyboardButton(f"🔄 Сделать активной: {g.name}",
                                            callback_data=f"pf_switch_{g.id}"))
        lines.append("")
    else:
        lines.append("Ты пока не состоишь ни в одной группе.")

    kb.add(InlineKeyboardButton("✏️ Сменить имя", callback_data="pf_rename"))
    if groups:
        kb.add(InlineKeyboardButton("🚪 Покинуть активную группу", callback_data="pf_leave"))

    text = "\n".join(lines)
    target = message_or_cb.message if hasattr(message_or_cb, "message") else message_or_cb
    if edit and hasattr(message_or_cb, "message"):
        try:
            await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    await target.answer(text, reply_markup=kb, parse_mode="HTML")


async def profile_callback(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data.startswith("pf_switch_"):
        gid = int(data.replace("pf_switch_", ""))
        # Проверяем, что пользователь реально в этой группе
        if not get_membership(gid, user_id):
            await callback_query.answer("Ты не в этой группе", show_alert=True)
            return
        set_active_group(user_id, gid)
        g = get_group_by_id(gid)
        await callback_query.answer(f"Активная группа: {g.name if g else gid} ✅")
        await _render_profile(user_id, callback_query, edit=True)
        # Обновим нижнее меню под новую активную группу
        await callback_query.message.answer(
            "Готово, переключил.", reply_markup=get_main_keyboard(user_id)
        )
        return

    if data == "pf_rename":
        await callback_query.message.answer("✏️ Введи новое имя:")
        await Profile.waiting_for_new_name.set()
        await callback_query.answer()
        return

    if data == "pf_leave":
        user = get_user_by_telegram_id(telegram_id=user_id)
        if not user or not user.active_group_id:
            await callback_query.answer("Нет активной группы", show_alert=True)
            return
        g = get_group_by_id(user.active_group_id)
        m = get_membership(user.active_group_id, user_id)
        warn = ""
        if m and m.group_role == "owner":
            warn = "\n\n⚠️ Ты староста этой группы. После выхода она останется без владельца."
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton(f"✅ Да, покинуть «{g.name if g else ''}»",
                                    callback_data=f"pf_leaveok_{user.active_group_id}"))
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="pf_back"))
        await callback_query.message.answer(
            f"Покинуть группу «{g.name if g else ''}»?{warn}", reply_markup=kb
        )
        await callback_query.answer()
        return

    if data.startswith("pf_leaveok_"):
        gid = int(data.replace("pf_leaveok_", ""))
        ok, new_active = leave_group(user_id, gid)
        if ok:
            await callback_query.answer("Группа покинута ✅")
            if new_active:
                ng = get_group_by_id(new_active)
                await callback_query.message.answer(
                    f"Готово. Активная группа теперь: {ng.name if ng else new_active}.",
                    reply_markup=get_main_keyboard(user_id)
                )
            else:
                await callback_query.message.answer(
                    "Готово. Ты больше не в группах. Введи код приглашения или напиши /start."
                )
        else:
            await callback_query.answer("Не удалось выйти", show_alert=True)
        return

    if data == "pf_back":
        await callback_query.answer()
        await _render_profile(user_id, callback_query, edit=True)
        return


async def process_new_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if name.startswith("/"):
        await state.finish()
        await message.answer("Отменено.", reply_markup=get_main_keyboard(message.from_user.id))
        return
    if len(name) < 2:
        await message.answer("❌ Слишком короткое имя. Введи ещё раз:")
        return
    update_user_name(message.from_user.id, name)
    await state.finish()
    await message.answer(f"✅ Имя изменено на «{name}».",
                         reply_markup=get_main_keyboard(message.from_user.id))
