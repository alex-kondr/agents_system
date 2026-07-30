import asyncio
import queue
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from keyboards.agents import get_agents_keyboard, AgentCallback, AgentAction, build_agent_action
from models import AgentModel, async_session, Status
from middleware import DbSessionMiddleware
from functions.test_products_multiprocessing import Product, TestProductMultiprocessing
from functions.test_logs import LogProduct, TestLogProduct
from functions.functions import get_status_agent


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
    while not (stop_event.is_set() and log_queue.empty()):
        await asyncio.sleep(batch_interval)

        lines: list[str] = []

        # 1. Забираємо ВСІ наявні елементи з черги за один раз
        while True:
            try:
                msg = log_queue.get_nowait()
                lines.append(msg)
                log_queue.task_done()  # Повідомляємо чергу, що елемент витягнуто
            except queue.Empty:
                break

        # 2. Якщо є що відправляти
        if lines:
            text = "\n".join(lines)

            # Нарізаємо на чанки по 4000 символів
            for chunk_start in range(0, len(text), 4000):
                chunk = text[chunk_start : chunk_start + 4000]
                try:
                    await send_func(f"<pre>{chunk}</pre>")
                except Exception as e:
                    # Рекомендую хоча б логувати помилку в консоль (print),
                    # щоб бачити, якщо Telegram блокує запити (Rate Limit / 429)
                    print(f"Error sending logs to Telegram: {e}")


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
    )
    await callback.message.answer(
        "Оберіть наступну дію:",
        reply_markup=build_agent_action(agent),
    )


@agent_router.callback_query(AgentCallback.filter(F.action == AgentAction.QC))
async def agent_set_qc(callback: CallbackQuery, callback_data: AgentCallback, session: AsyncSession) -> None:
    result = await session.execute(
        select(AgentModel).filter_by(id=callback_data.id)
    )
    agent = result.scalar_one()
    agent.status = Status.qc
    await session.commit()
    await callback.message.answer(
        f"Агент <b>{agent.source_name}</b> відмічено як QC.",
    )
    await callback.message.answer(
        "Оберіть наступну дію:",
        reply_markup=build_agent_action(agent),
    )


@agent_router.message(F.text == "Перевірити статус")
async def check_all_agents(message: Message, state: FSMContext, session: AsyncSession) -> None:
    # 1. Скидаємо стан FSM, якщо користувач був у процесі введення чогось
    await state.clear()

    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        result = await session.execute(
            select(AgentModel).filter_by(status=Status.running)
        )
        agents = result.scalars().all()

        await message.answer(
            f"<b>Перевірка статусу всіх агентів</b>\n"
            f"Всього запущених агентів: <code>{len(agents)}</code>",
            parse_mode="HTML"
        )

        for agent in agents:
            # 2. КРИТИЧНО: Виконуємо синхронний запит у окремому потоці,
            # щоб не блокувати асинхронний Event Loop aiogram
            try:
                status = await asyncio.to_thread(get_status_agent, agent.agent_id)
            except Exception as e:
                status = {"error": str(e)}

            # 3. Безпечно витягуємо error через .get()
            error_text = status.get('error')
            error_display = f"<code>{error_text}</code>" if error_text else "Немає"

            text = (
                f"🤖 <b>{agent.source_name}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📅 <b>Дата:</b> <code>{status.get('end_date', '—')}</code>\n"
                f"📤 <b>Відправлено:</b> <code>{status.get('emit_count', 0)}</code>\n"
                f"⚠️ <b>Помилки:</b> <code>{status.get('errors_count', 0)}</code>\n"
                f"⏳ <b>Черга:</b> <code>{status.get('jobs_in_queue', 0)}</code>\n"
                f"📡 <b>Запити:</b> <code>{status.get('requests_count', 0)}</code>\n"
                f"❌ <b>Помилка:</b> {error_display}\n"
                f"━━━━━━━━━━━━━━━━━━"
            )

            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=build_agent_action(agent)
            )

        await message.answer("Перевірка завершена.")


