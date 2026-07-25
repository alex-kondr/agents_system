from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from keyboards.agents import get_agents_keyboard, AgentCallback, AgentAction, build_agent_action
from models import AgentModel, async_session, Status
from middleware import DbSessionMiddleware
from functions.test_products_multiprocessing import Product, TestProductMultiprocessing
from functions.test_logs import LogProduct, TestLogProduct


agent_router = Router()
agent_router.callback_query.middleware(DbSessionMiddleware(session_pool=async_session))


@agent_router.message(F.text == "Список агентів")
async def show_all_agents(message: Message, state: FSMContext, session: AsyncSession) -> None:
    result = await session.execute(
        select(AgentModel).filter_by(status=Status.in_progress)
    )
    agents = result.scalars().all()
    keyboard = get_agents_keyboard(agents)
    await message.answer(
        "Список агентів",
        reply_markup=keyboard
    )


@agent_router.callback_query(AgentCallback.filter(F.action == AgentAction.SHOW))
async def show_agent_action(message: Message, callback_data: AgentCallback, session: AsyncSession) -> None:
    result = await session.execute(select(AgentModel).filter_by(id=callback_data.id))
    agent = result.scalar_one()
    await message.answer(
        f"{agent.source_name}-{agent.status.name}",
        reply_markup=ReplyKeyboardRemove()  # Прибере звичайні кнопки
    )
    await message.answer(
        "Оберіть дію:",
        reply_markup=build_agent_action(agent),
    )


@agent_router.callback_query(AgentCallback.filter(F.action == AgentAction.RUN_TEST))
async def agent_run_action(message: Message, callback_data: AgentCallback, session: AsyncSession) -> None:
    result = await session.execute(select(AgentModel).filter_by(id=callback_data.id))
    agent = result.scalar_one()

    product = Product(agent.id)
    await message.answer(
        product.result
    )

    test = TestProductMultiprocessing(product)
    test.run()

    log = LogProduct(agent.id)
    test_log = TestLogProduct(log)
    test_log.test_log()

    await message.answer(
        f"{agent.source_name}-{agent.status.name}",
        reply_markup=ReplyKeyboardRemove()  # Прибере звичайні кнопки
    )
    await message.answer(
        "Оберіть дію:",
        reply_markup=build_agent_action(agent),
    )