import asyncio
import logging
import os
from contextlib import asynccontextmanager

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from fastapi import FastAPI, Request
import uvicorn

from routers.agents import agent_router
from routers.start import start_router

load_dotenv()
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_API")
WEBHOOK_PATH = f"/bot/{TOKEN}"
WEBHOOK_URL = os.getenv("KOYEB_EXTERNAL_URL", "") + WEBHOOK_PATH

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

dp.include_router(start_router)
dp.include_router(agent_router)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_session = aiohttp.ClientSession()
    logger.info("Глобальну aiohttp.ClientSession успішно створено.")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(url=WEBHOOK_URL)
        logger.info("Webhook успішно встановлено.")
    except Exception as e:
        logger.error(f"Помилка встановлення вебхука: {e}")

    yield

    await app.state.http_session.close()
    await bot.session.close()


app = FastAPI(lifespan=lifespan)


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