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
    builder.button(text="Список агентів")
    builder.button(text="Додати нового агента")
    builder.button(text="Перевірити статус")
    builder.adjust(1)
    return builder.as_markup()


def get_agents_keyboard(agents: List[AgentModel]):
    buttons = []
    for agent in agents:
        buttons.append([
            InlineKeyboardButton(
                text=f"🤖 {agent.source_name}",
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

    # Вирівнюємо кнопки: 2 в один рядок (або по одній на рядок — builder.adjust(1))
    builder.adjust(2)

    return builder.as_markup()
