# handlers/schedule_setup.py
"""Поток привязки расписания при создании группы старостой.
Если у заведения провайдер с picker — выбор корпус→группа кнопками.
Если провайдер без picker — ручной ввод id. Если провайдера нет — пропуск.
Бот сам собирает external_schedule_id, староста не вводит технический путь."""
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states.user_states import Onboarding, UserRegistration
from handlers.start import subgroup_keyboard
from database.db_operations import (
    get_group_by_id, get_institution_by_id, update_group,
)
from providers import get_provider


async def start_schedule_binding(message: types.Message, state: FSMContext,
                                 group_id: int):
    """Точка входа после создания группы. Решает, нужен ли выбор расписания."""
    import logging
    log = logging.getLogger("schedule_setup")
    group = get_group_by_id(group_id)
    inst = get_institution_by_id(group.institution_id) if group else None
    provider_key = inst.schedule_provider if inst else None
    provider = get_provider(provider_key) if provider_key else None
    log.info(f"schedule_binding: group={group_id} inst={getattr(inst,'id',None)} "
             f"provider_key={provider_key!r} provider={'есть' if provider else 'нет'}")

    # Нет провайдера — расписания у вуза нет, сразу к подгруппе.
    if not provider:
        log.info("schedule_binding: провайдера нет — сразу к подгруппе")
        await _go_to_subgroup(message, state, created=True, group_name=group.name)
        return

    await state.update_data(sched_group_db_id=group_id, sched_provider=provider_key)

    # Провайдер с выбором (есть корпуса или список групп) — показываем корпуса.
    if getattr(provider, "supports_group_picker", False):
        campuses = provider.list_campuses()
        log.info(f"schedule_binding: picker=True, корпусов={len(campuses)}")
        if campuses:
            kb = InlineKeyboardMarkup(row_width=1)
            for c in campuses:
                kb.add(InlineKeyboardButton(c["name"], callback_data=f"sb_campus_{c['id']}"))
            await message.answer(
                f"Группа «{group.name}» создана, ты её староста.\n\n"
                "Теперь привяжем расписание. Выбери корпус:",
                reply_markup=kb,
            )
            await Onboarding.waiting_for_campus.set()
            return
        else:
            # picker без корпусов — сразу список групп (campus_id не нужен)
            await _show_groups(message, state, provider, campus_id=None,
                               group_name=group.name)
            return

    # Провайдер без picker (например ОмГТУ) — ручной ввод id.
    hint = getattr(provider, "group_id_hint", "id группы")
    await message.answer(
        f"Группа «{group.name}» создана, ты её староста.\n\n"
        f"Чтобы подтянуть расписание, введи {hint}.\n"
        "Или напиши «-», чтобы пропустить (расписание можно настроить позже):"
    )
    await Onboarding.waiting_for_sched_group.set()


async def _show_groups(message_or_cb, state, provider, campus_id, group_name):
    """Показывает список групп корпуса кнопками (или предлагает ручной ввод)."""
    groups = await provider.list_groups(campus_id) if campus_id is not None \
        else await provider.list_groups()
    target = message_or_cb.message if hasattr(message_or_cb, "message") else message_or_cb
    if not groups:
        await target.answer(
            "Не получилось загрузить список групп. Введи название своей группы вручную "
            "(например КС115):"
        )
        await state.update_data(sched_campus_id=campus_id)
        await Onboarding.waiting_for_sched_group.set()
        return
    await state.update_data(sched_campus_id=campus_id,
                            sched_groups={g["name"]: g["external_id"] for g in groups})
    kb = InlineKeyboardMarkup(row_width=2)
    btns = [InlineKeyboardButton(g["name"], callback_data=f"sb_group_{i}")
            for i, g in enumerate(groups)]
    kb.add(*btns)
    kb.add(InlineKeyboardButton("Моей группы нет в списке", callback_data="sb_group_manual"))
    await target.answer("Выбери свою группу:", reply_markup=kb)
    await Onboarding.waiting_for_sched_group.set()


async def campus_chosen(callback_query: types.CallbackQuery, state: FSMContext):
    campus_id = callback_query.data.replace("sb_campus_", "")
    data = await state.get_data()
    provider = get_provider(data.get("sched_provider"))
    await callback_query.answer("Загружаю группы…")
    await _show_groups(callback_query, state, provider, campus_id,
                       group_name=None)


async def group_chosen(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    st = await state.get_data()

    if data == "sb_group_manual":
        await callback_query.message.answer(
            "Введи название своей группы вручную (например КС115):"
        )
        await callback_query.answer()
        # остаёмся в waiting_for_sched_group — текст обработает manual-хендлер
        await state.update_data(awaiting_manual_group=True)
        return

    idx = int(data.replace("sb_group_", ""))
    groups = st.get("sched_groups", {})
    # sched_groups это {name: external_id}; восстановим по индексу
    items = list(groups.items())
    if idx >= len(items):
        await callback_query.answer("Не нашёл группу, попробуй ещё раз", show_alert=True)
        return
    name, external_id = items[idx]
    gid = st.get("sched_group_db_id")
    update_group(gid, external_schedule_id=external_id)
    await callback_query.answer(f"Группа {name} привязана")
    g = get_group_by_id(gid)
    await callback_query.message.answer(
        f"Расписание привязано: {name}.\n\nТеперь укажи свою подгруппу:",
        reply_markup=subgroup_keyboard(),
    )
    await UserRegistration.waiting_for_subgroup.set()


async def manual_or_id_input(message: types.Message, state: FSMContext):
    """Ручной ввод: либо название группы (picker-провайдер), либо id (omgtu)."""
    val = message.text.strip()
    st = await state.get_data()
    gid = st.get("sched_group_db_id")
    provider_key = st.get("sched_provider")
    provider = get_provider(provider_key)

    if val in ("-", "—"):
        # пропуск привязки
        await _go_to_subgroup(message, state, created=False)
        return

    external_id = val
    # Для picker-провайдера с корпусом и ручным вводом названия —
    # собираем путь корпус/название.
    if getattr(provider, "supports_group_picker", False):
        campus_id = st.get("sched_campus_id")
        if campus_id:
            external_id = f"{campus_id}/{val}"

    update_group(gid, external_schedule_id=external_id)
    await _go_to_subgroup(message, state, created=False)


async def _go_to_subgroup(message, state, created, group_name=None):
    await state.finish()
    if created and group_name:
        await message.answer(
            f"Группа «{group_name}» создана, ты её староста.\n\n"
            "Укажи свою подгруппу:",
            reply_markup=subgroup_keyboard(),
        )
    else:
        await message.answer("Готово. Укажи свою подгруппу:",
                             reply_markup=subgroup_keyboard())
    await UserRegistration.waiting_for_subgroup.set()
