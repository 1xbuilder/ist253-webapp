# utils/file_handlers.py
from aiogram.types import Message, PhotoSize, Document, Video, Audio

def get_file_info(message: Message):
    """Извлекает информацию о файле из сообщения"""
    file_info = {}
    
    if message.photo:
        # Фото - берем самое высокое качество
        file = message.photo[-1]
        file_info = {
            'file_id': file.file_id,
            'file_type': 'photo',
            'file_size': file.file_size
        }
    elif message.document:
        # Документ
        file = message.document
        file_info = {
            'file_id': file.file_id,
            'file_type': 'document',
            'file_name': file.file_name,
            'file_size': file.file_size,
            'mime_type': file.mime_type
        }
    elif message.video:
        # Видео
        file = message.video
        file_info = {
            'file_id': file.file_id,
            'file_type': 'video',
            'file_size': file.file_size,
            'mime_type': file.mime_type
        }
    elif message.audio:
        # Аудио
        file = message.audio
        file_info = {
            'file_id': file.file_id,
            'file_type': 'audio',
            'file_name': getattr(file, 'file_name', 'audio'),
            'file_size': file.file_size,
            'mime_type': file.mime_type
        }
    
    return file_info if file_info else None