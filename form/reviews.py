from aiogram.fsm.state import State, StatesGroup


class ReviewCreateForm(StatesGroup):
    text = State()