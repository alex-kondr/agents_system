import asyncio
import ctypes
import gc
import logging
import os
from contextlib import asynccontextmanager

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
from dotenv import load_dotenv
from fastapi import FastAPI, Request
import uvicorn

from routers.agents import agent_router
from routers.start import start_router

load_dotenv()
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_API")
WEBHOOK_PATH = f"/bot/{TOKEN}"

# Автоматично перевіряємо наявність протоколу https:// у BASE_URL
raw_url = os.getenv("KOYEB_EXTERNAL_URL", "").strip()
if raw_url and not raw_url.startswith("http"):
    raw_url = f"https://{raw_url}"

WEBHOOK_URL = f"{raw_url.rstrip('/')}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

dp.include_router(start_router)
dp.include_router(agent_router)


async def memory_cleaner_task():
    while True:
        await asyncio.sleep(900)  # кожні 15 хвилин
        gc.collect()
        try:
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_session = aiohttp.ClientSession()
    logger.info("Глобальну aiohttp.ClientSession успішно створено.")
    cleaner_task = asyncio.create_task(memory_cleaner_task())

    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 1. Перевіряємо поточні налаштування вебхука
            webhook_info = await bot.get_webhook_info()

            # Якщо URL вже встановлено коректно — повторно set_webhook викликати не потрібно
            if webhook_info.url == WEBHOOK_URL:
                logger.info(f"Webhook вже активний і вказує на {WEBHOOK_URL}")
                break

            # 2. Якщо URL змінився або відсутній — встановлюємо новий
            await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=False)
            logger.info(f"Webhook успішно встановлено на {WEBHOOK_URL}")
            break  # Виходимо з циклу ретраїв, щоб перейти до yield

        except TelegramRetryAfter as e:
            # 3. Використовуємо точний час очікування e.retry_after від Telegram API
            wait = e.retry_after + 1
            logger.warning(
                f"Telegram flood limit (спроба {attempt + 1}/{max_retries}): чекаємо {wait} сек..."
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(wait)
            else:
                logger.error("Вичерпано ліміт спроб встановлення webhook.")

        except Exception as e:
            logger.error(f"Не вдалося встановити Webhook при старті: {e}")
            break

    # Точка запуску прийому запитів додатком (генератор повертає управління FastAPI)
    yield

    # Завершення роботи
    cleaner_task.cancel()
    await app.state.http_session.close()
    await bot.session.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    data = await request.json()
    update = types.Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update, http_session=app.state.http_session)
    return {"status": "ok"}


# async def main():
#         # Видаляємо вебхук перед запуском полінгу, щоб не було конфліктів
#         await bot.delete_webhook(drop_pending_updates=True)
#         logger.info("Запуск бота у режимі Long Polling (Локально)...")
#         await dp.start_polling(bot, http_session=aiohttp.ClientSession())

# if __name__ == "__main__":
#     asyncio.run(main())