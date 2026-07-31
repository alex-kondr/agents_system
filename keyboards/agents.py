from typing import List
import enum

from aiogram.types.inline_keyboard_markup import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData

from models import AgentModel


class AgentAction(str, enum.Enum):
    RUN_TEST = "run_test"
    DONE = "done"
    SHOW = "show"
    QC = "qc"


class AgentCallback(CallbackData, prefix="agent"):
    id: int
    action: AgentAction


def build_global_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Список агентів цього місяця 🚀")
    builder.button(text="Список агентів в роботі ⏳")
    builder.button(text="Список запущених 🏁")
    builder.button(text="Перевірити всі запущені агенти 🔍")
    builder.adjust(1)
    return builder.as_markup(
        resize_keyboard=True,       # Підганяє розмір кнопок під екран (щоб не були величезними)
        is_persistent=True,         # Меню залишається видимим навіть при згортанні/перезапуску
        input_field_placeholder="Оберіть дію з меню..."
    )


def get_agents_keyboard(agents: List[AgentModel]):
    buttons = []
    for agent in agents:
        buttons.append([
            InlineKeyboardButton(
                text=f"🤖 {agent.source_name} - {agent.status}",
                callback_data=AgentCallback(id=agent.id, action=AgentAction.SHOW).pack()
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_agent_action(agent: AgentModel) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Запустити тест",
        callback_data=AgentCallback(id=agent.id, action=AgentAction.RUN_TEST)
    )
    builder.button(
        text="Виконаний",
        callback_data=AgentCallback(id=agent.id, action=AgentAction.DONE)
    )
    builder.button(
        text="QC",
        callback_data=AgentCallback(id=agent.id, action=AgentAction.QC)
    )

    builder.adjust(3)
    return builder.as_markup()
