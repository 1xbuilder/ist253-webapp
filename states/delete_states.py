from aiogram.dispatcher.filters.state import State, StatesGroup

class DeleteHomework(StatesGroup):
    waiting_for_date_selection = State()
    waiting_for_homework_selection = State()
    waiting_for_confirmation = State()