from dotenv import load_dotenv
from os import getenv
import asyncio

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from log.log import bot_log
from routers.agents import product_router #Імпорт роутера логіки з товарами
from routers.start import start_router #Імпорт роутера логіки start


# Завантажимо дані середовища з файлу .env(За замовчуванням)
load_dotenv()


# Усі обробники варто закріплювати за Router або Dispatcher
root_router = Router()
root_router.include_routers(product_router) #Включення роутера в головний
root_router.include_routers(start_router) #Включення роутера в головний


# Головна функція пакету
async def main() -> None:
   # Дістанемо токен бота з середовища
   TOKEN = getenv("TELEGRAM_API")
   # Створимо об'єкт Bot
   bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

   dp = Dispatcher()
   dp.include_router(root_router)
   # Почнемо обробляти події для бота
   await dp.start_polling(bot)


# Точка входу
if __name__ == "__main__":
   # bot_log()
   asyncio.run(main())