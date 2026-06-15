from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from handlers.start import get_main_keyboard, check_active_group
from datetime import datetime, timedelta, date
from database.db_operations import get_today_homework, get_tomorrow_homework, get_week_homework, get_homework_by_date
import json

async def show_homework_menu(message: types.Message):
    period_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    period_keyboard.add(KeyboardButton("Сегодня"))
    period_keyboard.add(KeyboardButton("Завтра"))
    period_keyboard.add(KeyboardButton("Выбрать дату"))
    period_keyboard.add(KeyboardButton("Назад"))
    
    await message.answer("📚 Выбери период для просмотра ДЗ:", reply_markup=period_keyboard)

async def back_to_main_menu(message: types.Message):
    await message.answer("Главное меню:", reply_markup=get_main_keyboard(message.from_user.id))

async def show_date_selection(message: types.Message):
    from handlers.calendar_handlers import show_calendar
    await show_calendar(message)

# homework.py - обновленная функция send_homework_with_files
async def send_homework_with_files(message: types.Message, homework):
    """
    Отправляет одно ДЗ с прикрепленными файлами (группирует в альбомы при возможности)
    """
    # Формируем основной текст ДЗ
    homework_text = (
        f"📅 {homework.date_for.strftime('%d.%m.%Y')}\n"
        f"📚 {homework.subject}\n"
        f"📝 {homework.task}\n"
    )
    
    # Проверяем есть ли файлы
    attachments = []
    if homework.attachment_file_id:
        try:
            attachments = json.loads(homework.attachment_file_id)
        except:
            attachments = []
    
    if not attachments:
        # Если файлов нет, просто отправляем текст
        await message.answer(homework_text)
        return
    
    # Разделяем файлы по типам для группировки
    photos = []
    documents = []
    videos = []
    audios = []
    voices = []
    
    for attachment in attachments:
        if attachment['type'] == 'photo':
            photos.append(attachment)
        elif attachment['type'] == 'document':
            documents.append(attachment)
        elif attachment['type'] == 'video':
            videos.append(attachment)
        elif attachment['type'] == 'audio':
            audios.append(attachment)
        elif attachment['type'] == 'voice':
            voices.append(attachment)
    
    # Отправляем фото альбомом (если есть фото)
    if photos:
        await send_media_group(message, photos, homework_text, homework.subject, is_first_group=True)
    else:
        # Если нет фото, отправляем текст отдельно
        await message.answer(homework_text)
    
    # Отправляем остальные файлы
    await send_remaining_files(message, documents, videos, audios, voices, homework.subject)

async def send_media_group(message: types.Message, media_list, caption, subject, is_first_group=False):
    """
    Отправляет группу медиафайлов (альбом)
    """
    from aiogram.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument
    
    # Ограничение Telegram: максимум 10 файлов в альбоме
    MAX_MEDIA_PER_GROUP = 10
    
    # Разбиваем на группы по MAX_MEDIA_PER_GROUP
    for i in range(0, len(media_list), MAX_MEDIA_PER_GROUP):
        group = media_list[i:i + MAX_MEDIA_PER_GROUP]
        media_group = []
        
        for j, attachment in enumerate(group):
            # Для первого файла в первой группе добавляем подпись
            if j == 0 and i == 0 and is_first_group:
                current_caption = caption
                # Обрезаем подпись если слишком длинная
                if len(current_caption) > 1024:
                    current_caption = current_caption[:1021] + "..."
            else:
                current_caption = attachment.get('caption', f"📚 {subject}")
                if len(current_caption) > 1024:
                    current_caption = current_caption[:1021] + "..."
            
            if attachment['type'] == 'photo':
                media_group.append(InputMediaPhoto(
                    media=attachment['file_id'],
                    caption=current_caption if j == 0 and i == 0 and is_first_group else None
                ))
            elif attachment['type'] == 'video':
                media_group.append(InputMediaVideo(
                    media=attachment['file_id'],
                    caption=current_caption if j == 0 and i == 0 and is_first_group else None
                ))
            elif attachment['type'] == 'document':
                media_group.append(InputMediaDocument(
                    media=attachment['file_id'],
                    caption=current_caption if j == 0 and i == 0 and is_first_group else None
                ))
        
        try:
            if len(media_group) == 1:
                # Если в группе только один файл, отправляем отдельно
                media = media_group[0]
                if isinstance(media, InputMediaPhoto):
                    await message.answer_photo(
                        media.media,
                        caption=media.caption
                    )
                elif isinstance(media, InputMediaVideo):
                    await message.answer_video(
                        media.media,
                        caption=media.caption
                    )
                elif isinstance(media, InputMediaDocument):
                    await message.answer_document(
                        media.media,
                        caption=media.caption
                    )
            else:
                # Отправляем альбом
                await message.answer_media_group(media_group)
                
        except Exception as e:
            print(f"Ошибка при отправке медиагруппы: {e}")
            # Если не удалось отправить альбом, отправляем по одному
            for media in media_group:
                try:
                    if isinstance(media, InputMediaPhoto):
                        await message.answer_photo(
                            media.media,
                            caption=media.caption
                        )
                    elif isinstance(media, InputMediaVideo):
                        await message.answer_video(
                            media.media,
                            caption=media.caption
                        )
                    elif isinstance(media, InputMediaDocument):
                        await message.answer_document(
                            media.media,
                            caption=media.caption
                        )
                except Exception as e2:
                    print(f"Ошибка при отправке отдельного файла: {e2}")

async def send_remaining_files(message, documents, videos, audios, voices, subject):
    """
    Отправляет файлы, которые не вошли в альбомы
    """
    # Отправляем документы (не группируются в альбомы с фото/видео)
    for attachment in documents:
        try:
            caption = attachment.get('caption', f"📚 {subject}")
            if len(caption) > 1024:
                caption = caption[:1021] + "..."
            await message.answer_document(
                attachment['file_id'],
                caption=caption
            )
        except Exception as e:
            print(f"Ошибка при отправке документа: {e}")
    
    # Отправляем видео (если остались после альбомов)
    for attachment in videos:
        try:
            caption = attachment.get('caption', f"📚 {subject}")
            if len(caption) > 1024:
                caption = caption[:1021] + "..."
            await message.answer_video(
                attachment['file_id'],
                caption=caption
            )
        except Exception as e:
            print(f"Ошибка при отправке видео: {e}")
    
    # Отправляем аудио
    for attachment in audios:
        try:
            caption = attachment.get('caption', f"📚 {subject}")
            if len(caption) > 1024:
                caption = caption[:1021] + "..."
            await message.answer_audio(
                attachment['file_id'],
                caption=caption
            )
        except Exception as e:
            print(f"Ошибка при отправке аудио: {e}")
    
    # Отправляем голосовые сообщения
    for attachment in voices:
        try:
            await message.answer_voice(attachment['file_id'])
        except Exception as e:
            print(f"Ошибка при отправке голосового сообщения: {e}")

# Функция для показа ДЗ на сегодня
async def show_today_homework(message: types.Message):
    try:
        group_id = await check_active_group(message)
        if not group_id:
            return
        homeworks = get_today_homework(group_id=group_id)
        
        if not homeworks:
            await message.answer("📝 На сегодня домашних заданий нет!", 
                               reply_markup=get_main_keyboard(message.from_user.id))
            return
        
        await message.answer(f"📚 Домашние задания на сегодня ({datetime.now().strftime('%d.%m.%Y')}):")
        
        for homework in homeworks:
            await send_homework_with_files(message, homework)
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении ДЗ: {str(e)}")
# Функция для показа ДЗ на завтра
async def show_tomorrow_homework(message: types.Message):
    try:
        group_id = await check_active_group(message)
        if not group_id:
            return
        homeworks = get_tomorrow_homework(group_id=group_id)
        
        if not homeworks:
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
            await message.answer(f"📝 На завтра ({tomorrow}) домашних заданий нет!", 
                               reply_markup=get_main_keyboard(message.from_user.id))
            return
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
        await message.answer(f"📚 Домашние задания на завтра ({tomorrow}):")
        
        for homework in homeworks:
            await send_homework_with_files(message, homework)
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении ДЗ: {str(e)}")
# Функция для показа ДЗ на неделю
async def show_week_homework(message: types.Message):
    try:
        group_id = await check_active_group(message)
        if not group_id:
            return
        homeworks = get_week_homework(group_id=group_id)
        
        if not homeworks:
            await message.answer("📝 На эту неделю домашних заданий нет!", 
                               reply_markup=get_main_keyboard(message.from_user.id))
            return
        
        await message.answer("📚 Домашние задания на неделю:")
        
        # Группируем ДЗ по датам
        homework_by_date = {}
        for homework in homeworks:
            date_str = homework.date_for.strftime('%d.%m.%Y')
            if date_str not in homework_by_date:
                homework_by_date[date_str] = []
            homework_by_date[date_str].append(homework)
        
        # Отправляем ДЗ по датам
        for date_str, homeworks_list in homework_by_date.items():
            await message.answer(f"\n📅 {date_str}:")
            for homework in homeworks_list:
                await send_homework_with_files(message, homework)
                
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении ДЗ: {str(e)}")
