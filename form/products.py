from aiogram.fsm.state import State, StatesGroup


class ProdCreateForm(StatesGroup):
    name = State()