from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.utils.chat_action import ChatActionSender
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import asyncio
import queue
import logging

from keyboards.agents import get_agents_keyboard, AgentCallback, AgentAction, build_agent_action
from models import AgentModel, async_session, Status
from middleware import DbSessionMiddleware
from functions.test_products_multiprocessing import Product, TestProductMultiprocessing
from functions.test_logs import LogProduct, TestLogProduct


agent_router = Router()
agent_router.message.middleware(DbSessionMiddleware(session_pool=async_session))
agent_router.callback_query.middleware(DbSessionMiddleware(session_pool=async_session))


# ---------- Telegram log streaming ----------

class TelegramLogHandler(logging.Handler):
    """Logging handler that puts formatted messages into a thread-safe queue."""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put(msg)
        except Exception:
            self.handleError(record)


async def _consume_log_queue(
    log_queue: queue.Queue,
    send_func,
    stop_event: asyncio.Event,
    batch_interval: float = 2.0,
):
    """Background task: reads log queue and sends batched messages to Telegram."""
    while True:
        await asyncio.sleep(batch_interval)
        lines: list[str] = []
        while not log_queue.empty():
            try:
                lines.append(log_queue.get_nowait())
            except queue.Empty:
                break
        if lines:
            text = "\n".join(lines)
            # Telegram message limit is 4096 chars
            for chunk_start in range(0, len(text), 4000):
                chunk = text[chunk_start : chunk_start + 4000]
                try:
                    await send_func(f"<pre>{chunk}</pre>")
                except Exception:
                    pass
        if stop_event.is_set() and log_queue.empty():
            break


# ---------- Handlers ----------

@agent_router.message(F.text == "Список агентів")
async def show_all_agents(message: Message, state: FSMContext, session: AsyncSession) -> None:
    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        result = await session.execute(
            select(AgentModel).filter_by(status=Status.running)
        )
        agents = result.scalars().all()
        keyboard = get_agents_keyboard(agents)
        await message.answer(
            "Список агентів",
            reply_markup=keyboard
        )


@agent_router.callback_query(AgentCallback.filter(F.action == AgentAction.SHOW))
async def show_agent_action(callback: CallbackQuery, callback_data: AgentCallback, session: AsyncSession) -> None:
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    async with ChatActionSender.typing(bot=callback.bot, chat_id=callback.message.chat.id):
        result = await session.execute(select(AgentModel).filter_by(id=callback_data.id))
        agent = result.scalar_one()
        await callback.message.answer(
            f"{agent.source_name}-{agent.status.name}",
            reply_markup=ReplyKeyboardRemove()  # Прибере звичайні кнопки
        )
        await callback.message.answer(
            "Оберіть дію:",
            reply_markup=build_agent_action(agent),
        )


@agent_router.callback_query(AgentCallback.filter(F.action == AgentAction.RUN_TEST))
async def agent_run_action(callback: CallbackQuery, callback_data: AgentCallback, session: AsyncSession) -> None:
    # Відповідаємо телеграму відразу при натисканні, щоб кнопка не зависала і не виникав timeout (30s)
    try:
        await callback.answer("Тестування розпочато...")
    except TelegramBadRequest:
        pass

    async with ChatActionSender.typing(bot=callback.bot, chat_id=callback.message.chat.id):
        result = await session.execute(select(AgentModel).filter_by(id=callback_data.id))
        agent = result.scalar_one()

        # --- Налаштовуємо стрімінг логів у Telegram ---
        log_queue: queue.Queue = queue.Queue()
        tg_handler = TelegramLogHandler(log_queue)
        tg_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"))

        # Підключаємо handler до обох логерів
        loggers = [
            logging.getLogger("ProductTestMulti"),
            logging.getLogger("LogTest"),
        ]
        for lgr in loggers:
            lgr.addHandler(tg_handler)

        stop_event = asyncio.Event()
        consumer_task = asyncio.create_task(
            _consume_log_queue(log_queue, callback.message.answer, stop_event)
        )

        try:
            # --- Завантаження продукту (у потоці, щоб не блокувати event loop) ---
            product = await asyncio.to_thread(Product, agent.agent_id)
            await callback.message.answer(str(product.result))

            # --- Тест товарів ---
            test = TestProductMultiprocessing(product)
            test_result = await asyncio.to_thread(test.run)
            await callback.message.answer(
                f"<b>📊 Результати тестування товарів:</b>\n<pre>{test_result}</pre>"
            )

            # --- Тест логів ---
            log = await asyncio.to_thread(LogProduct, agent.agent_id)
            test_log = TestLogProduct(log)
            test_log_result = await asyncio.to_thread(test_log.test_log)
            await callback.message.answer(
                f"<b>📋 Результати аналізу логів:</b>\n<pre>{test_log_result}</pre>"
            )

            agent.count_emit = product.result.emitted
            await session.commit()
        except ValueError as e:
            # get_end_date_agent кидає ValueError коли дата == 'None' (агент ще не завершив роботу)
            # Відправляємо помилку в Telegram і зупиняємо тест, але сервіс продовжує працювати
            await callback.message.answer(
                f"⚠️ <b>Тест зупинено:</b>\n<pre>{e}</pre>"
            )
            return
        finally:
            # --- Прибираємо handler та зупиняємо consumer ---
            stop_event.set()
            await consumer_task
            for lgr in loggers:
                lgr.removeHandler(tg_handler)

        await callback.message.answer(
            f"Тести завершено.\n{agent.source_name}-{agent.status.name}",
            reply_markup=ReplyKeyboardRemove()
        )
        await callback.message.answer(
            "Оберіть наступну дію:",
            reply_markup=build_agent_action(agent),
        )


@agent_router.callback_query(AgentCallback.filter(F.action == AgentAction.DONE))
async def agent_set_done(callback: CallbackQuery, callback_data: AgentCallback, session: AsyncSession) -> None:
    result = await session.execute(
        select(AgentModel).filter_by(id=callback_data.id)
    )
    agent = result.scalar_one()
    agent.done = True
    await session.commit()
    await callback.message.answer(
        f"Агент <b>{agent.source_name}</b> відмічено як виконаний.",
        reply_markup=ReplyKeyboardRemove()
    )
    await callback.message.answer(
        "Оберіть наступну дію:",
        reply_markup=build_agent_action(agent),
    )