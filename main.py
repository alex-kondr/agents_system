from dotenv import load_dotenv
import os
import asyncio

from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from fastapi import FastAPI, Request

from routers.agents import agent_router #Імпорт роутера логіки з товарами
from routers.start import start_router #Імпорт роутера логіки start


# Завантажимо дані середовища з файлу .env(За замовчуванням)
load_dotenv()

TOKEN = os.getenv("TELEGRAM_API")
WEBHOOK_PATH = f"/bot/{TOKEN}"
WEBHOOK_URL = os.getenv("KOYEB_EXTERNAL_URL") + WEBHOOK_PATH  # Render сам надає RENDER_EXTERNAL_URL

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
app = FastAPI()


# Усі обробники варто закріплювати за Router або Dispatcher
root_router = Router()
root_router.include_routers(agent_router) #Включення роутера в головний
root_router.include_routers(start_router) #Включення роутера в головний
dp.include_router(root_router)


@app.on_event("startup")
async def on_startup():
    # Реєструємо Webhook у Telegram при запуску
    await bot.set_webhook(url=WEBHOOK_URL)

@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    # Отримуємо оновлення від Telegram
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"status": "ok"}


# Головна функція пакету
# async def main() -> None:
    # Почнемо обробляти події для бота
    # await dp.start_polling(bot)


# Точка входу
# if __name__ == "__main__":
#    asyncio.run(main())