from aiogram.dispatcher.filters.state import State, StatesGroup

class AddHomework(StatesGroup):
    waiting_for_date        = State()
    waiting_for_subject     = State()  # теперь принимает и кнопки и текст
    waiting_for_task        = State()
    waiting_for_attachment  = State()
    waiting_for_confirmation= State()
