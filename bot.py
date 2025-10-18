import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import Database
# Импорт функции регистрации роутеров
from handlers import register_all_routers 

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и БД
bot = Bot(token=BOT_TOKEN)
db = Database()
# Инициализация хранилища FSM (используем MemoryStorage для начала)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- Регистрация модулей ---

async def main():
    """Главная функция для запуска бота."""
    
    # Регистрация всех роутеров из папки handlers
    register_all_routers(dp)
    
    # Передача объекта БД во все хэндлеры через контекст Dispatcher
    dp['db'] = db 
    
    try:
        print("INFO:aiogram.dispatcher:Start polling")
        await dp.start_polling(bot) 
    finally:
        db.close()
        await bot.session.close() # Закрываем сессию бота

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")