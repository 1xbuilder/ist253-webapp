import aiohttp
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ContentType
from states.homework_states import AddHomework
from handlers.start import get_main_keyboard, check_active_group
from database.db_operations import (
    add_homework_to_db, get_user_by_telegram_id,
    get_group_by_id, get_institution_by_id, can_edit_homework,
)
from datetime import datetime, timedelta
import json


# ── Загрузка расписания на дату ────────────────────────────────
# Раньше тут был зашит GROUP_ID = 427 (одна группа ОмГТУ).
# Теперь ID группы берётся из external_schedule_id активной группы,
# а провайдер — из заведения. Нет провайдера/ID -> расписания нет, ручной ввод.

async def fetch_lessons_for_date(date_obj, provider, external_id) -> list:
    """Запрашивает расписание на конкретный день у провайдера заведения."""
    if not provider or not external_id:
        return []
    if provider == "omgtu":
        date_str = date_obj.strftime("%Y.%m.%d")
        url = (f"https://rasp.omgtu.ru/api/schedule/group/{external_id}"
               f"?start={date_str}&finish={date_str}&lng=1")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 200:
                        data = await r.json(content_type=None)
                        return data if isinstance(data, list) else []
        except Exception as e:
            print(f"Ошибка загрузки расписания (omgtu): {e}")
        return []
    # Другие провайдеры можно добавить здесь.
    return []


def get_subjects_for_subgroup(lessons: list, subgroup: str):
    """Делит предметы на: мои (my) и другой подгруппы (other)."""
    other_sub = "2" if subgroup == "1" else "1"
    my, other = [], []
    seen_my, seen_other = set(), set()
    for l in lessons:
        disc = l.get('discipline', '')
        if not disc:
            continue
        if f'/{other_sub}' in disc:
            if disc not in seen_other:
                other.append(l); seen_other.add(disc)
        else:
            if disc not in seen_my:
                my.append(l); seen_my.add(disc)
    return my, other


def subjects_keyboard(my_lessons, other_lessons):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for l in my_lessons:
        kb.add(KeyboardButton(l['discipline']))
    if other_lessons:
        kb.add(KeyboardButton("── Другая подгруппа ──"))
        for l in other_lessons:
            kb.add(KeyboardButton(l['discipline']))
    kb.add(KeyboardButton("✏️ Ввести вручную"))
    kb.add(KeyboardButton("Отмена"))
    return kb


def manual_only_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("✏️ Ввести вручную"))
    kb.add(KeyboardButton("Отмена"))
    return kb


# ── Начало добавления ДЗ ──────────────────────────────────────
async def start_add_homework(message: types.Message, state: FSMContext):
    group_id = await check_active_group(message)
    if not group_id:
        return
    # Проверка прав: добавлять могут owner/helper или глобальные admin/moderator.
    if not can_edit_homework(message.from_user.id, group_id):
        await message.answer(
            "🔒 Добавлять ДЗ могут только староста и его помощники.\n"
            "Если тебе нужны такие права — попроси старосту твоей группы."
        )
        return
    await state.finish()
    await message.answer(
        "📝 Добавляем ДЗ!\n\n"
        "На какую дату?\nФормат: ДД.ММ.ГГГГ\nили: завтра, послезавтра, через 2 дня",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("Отмена"))
    )
    await AddHomework.waiting_for_date.set()


# ── Ввод даты ─────────────────────────────────────────────────
async def process_date(message: types.Message, state: FSMContext):
    date_text = message.text.lower().strip()
    offsets = {
        "завтра": 1, "послезавтра": 2,
        "через 2 дня": 2, "через 3 дня": 3, "через 4 дня": 4,
        "через 5 дней": 5, "через 6 дней": 6, "через 7 дней": 7,
    }
    if date_text in offsets:
        selected_date = datetime.now() + timedelta(days=offsets[date_text])
    else:
        try:
            selected_date = datetime.strptime(date_text, "%d.%m.%Y")
        except ValueError:
            await message.answer("❌ Неверный формат. Попробуй ДД.ММ.ГГГГ или 'завтра'")
            return

    await state.update_data(date_for=selected_date.strftime("%Y-%m-%d"))
    await message.answer(f"✅ Дата: {selected_date.strftime('%d.%m.%Y')}\n⏳ Загружаю предметы...")

    user = get_user_by_telegram_id(telegram_id=message.from_user.id)
    subgroup = user.subgroup if user else "1"
    group = get_group_by_id(user.active_group_id) if user and user.active_group_id else None

    # Определяем провайдера расписания через заведение группы.
    provider, external_id = None, None
    if group:
        external_id = group.external_schedule_id
        inst = get_institution_by_id(group.institution_id) if group.institution_id else None
        provider = inst.schedule_provider if inst else None

    lessons = await fetch_lessons_for_date(selected_date, provider, external_id)

    if lessons:
        my, other = get_subjects_for_subgroup(lessons, subgroup)
        kb = subjects_keyboard(my, other)
        text = f"📚 Выбери предмет на {selected_date.strftime('%d.%m.%Y')}:\n(подгруппа {subgroup})"
    else:
        kb = manual_only_keyboard()
        if provider and external_id:
            text = "⚠️ Не удалось загрузить расписание на эту дату.\nВведи название предмета вручную:"
        else:
            text = "📚 Для твоей группы расписание не подключено.\nВведи название предмета вручную:"

    all_discs = [l['discipline'] for l in lessons]
    await state.update_data(available_subjects=all_discs, manual_input=not bool(lessons))
    await message.answer(text, reply_markup=kb)
    await AddHomework.waiting_for_subject.set()


# ── Выбор предмета ────────────────────────────────────────────
async def process_subject(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if text == "── Другая подгруппа ──":
        await message.answer("👆 Выбери предмет из списка выше или введи вручную")
        return
    if text == "✏️ Ввести вручную":
        kb = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("Отмена"))
        await message.answer("✏️ Введи название предмета:", reply_markup=kb)
        await state.update_data(manual_input=True)
        return
    await state.update_data(subject=text)
    await message.answer(
        f"📚 Предмет: {text}\n\n📝 Введи текст домашнего задания:",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("Отмена"))
    )
    await AddHomework.waiting_for_task.set()


# ── Ввод задания ──────────────────────────────────────────────
async def process_task(message: types.Message, state: FSMContext):
    await state.update_data(task=message.text.strip(), attachments=[])
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Пропустить"))
    kb.add(KeyboardButton("Отмена"))
    await message.answer(
        "📎 Прикрепи файлы или фото (можно несколько).\nИли нажми Пропустить:",
        reply_markup=kb
    )
    await AddHomework.waiting_for_attachment.set()


# ── Текстовые команды при вложениях ──────────────────────────
async def process_attachment_text(message: types.Message, state: FSMContext):
    if message.text in ("Пропустить", "Завершить добавление файлов"):
        await show_preview(message, state)


# ── Медиафайлы ────────────────────────────────────────────────
async def process_attachment_media(message: types.Message, state: FSMContext):
    try:
        if message.photo:
            file_data = {"type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption or ""}
        elif message.document:
            file_data = {"type": "document", "file_id": message.document.file_id, "file_name": message.document.file_name or "файл", "caption": message.caption or ""}
        elif message.video:
            file_data = {"type": "video", "file_id": message.video.file_id, "caption": message.caption or ""}
        elif message.audio:
            file_data = {"type": "audio", "file_id": message.audio.file_id, "caption": message.caption or ""}
        elif message.voice:
            file_data = {"type": "voice", "file_id": message.voice.file_id}
        else:
            await message.answer("❌ Неподдерживаемый тип файла")
            return

        data = await state.get_data()
        attachments = data.get("attachments", [])
        attachments.append(file_data)
        await state.update_data(attachments=attachments)

        emoji = {"photo": "📷", "document": "📄", "video": "🎥", "audio": "🎵", "voice": "🎤"}
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(KeyboardButton("Завершить добавление файлов"))
        kb.add(KeyboardButton("Отмена"))
        await message.answer(
            f"✅ {emoji.get(file_data['type'], '📎')} Файл добавлен! Всего: {len(attachments)}\n\nОтправь ещё или нажми Завершить:",
            reply_markup=kb
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка при сохранении файла: {e}")


# ── Превью ────────────────────────────────────────────────────
async def show_preview(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        attachments = data.get("attachments", [])
        names = {"photo": "Фото", "document": "Документ", "video": "Видео", "audio": "Аудио", "voice": "Голосовое"}
        if attachments:
            att_info = f"📎 Вложений: {len(attachments)}\n"
            att_info += "".join(f"  {i+1}. {names.get(f['type'], f['type'])}\n" for i, f in enumerate(attachments))
        else:
            att_info = "📎 Вложений: нет\n"
        preview = (
            "📋 Предпросмотр ДЗ:\n\n"
            f"📅 Дата: {datetime.strptime(data['date_for'], '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
            f"📚 Предмет: {data['subject']}\n"
            f"📝 Задание: {data['task']}\n"
            f"{att_info}\n"
            "Всё верно?"
        )
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(KeyboardButton("✅ Да, добавить"))
        kb.add(KeyboardButton("❌ Нет, отменить"))
        await message.answer(preview, reply_markup=kb)
        await AddHomework.waiting_for_confirmation.set()
    except KeyError as e:
        await message.answer(f"❌ Потерялись данные ({e}). Начни заново — нажми '➕ Добавить ДЗ'",
                             reply_markup=get_main_keyboard(message.from_user.id))
        await state.finish()
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}. Начни заново.",
                             reply_markup=get_main_keyboard(message.from_user.id))
        await state.finish()


# ── Подтверждение ─────────────────────────────────────────────
async def confirm_add_homework(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text == "✅ Да, добавить":
        try:
            data = await state.get_data()
            user = get_user_by_telegram_id(telegram_id=user_id)
            if not user or not user.active_group_id:
                await message.answer("⚠️ Ты не в группе. Напиши /start",
                                     reply_markup=get_main_keyboard(user_id))
                await state.finish()
                return

            # Повторная проверка прав на момент сохранения.
            if not can_edit_homework(user_id, user.active_group_id):
                await message.answer("🔒 У тебя больше нет прав на добавление ДЗ.",
                                     reply_markup=get_main_keyboard(user_id))
                await state.finish()
                return

            date_for = datetime.strptime(data['date_for'], "%Y-%m-%d").date()
            attachments = data.get("attachments", [])
            attachment_data = json.dumps(attachments, ensure_ascii=False) if attachments else None

            homework = add_homework_to_db(
                group_id=user.active_group_id,
                subject=data['subject'],
                task=data['task'],
                date_for=date_for,
                subgroup=user.subgroup,
                attachment_file_id=attachment_data,
                created_by=user_id,
            )
            if homework:
                text = "✅ ДЗ успешно добавлено!"
                if attachments:
                    text += f"\n📎 Файлов: {len(attachments)}"
                await message.answer(text, reply_markup=get_main_keyboard(user_id))
            else:
                await message.answer("❌ Ошибка при сохранении. Попробуй ещё раз.",
                                     reply_markup=get_main_keyboard(user_id))
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}", reply_markup=get_main_keyboard(user_id))
    else:
        await message.answer("❌ Добавление отменено", reply_markup=get_main_keyboard(user_id))
    await state.finish()


# ── Отмена ────────────────────────────────────────────────────
async def cancel_add_homework(message: types.Message, state: FSMContext):
    await message.answer("❌ Добавление ДЗ отменено", reply_markup=get_main_keyboard(message.from_user.id))
    await state.finish()
