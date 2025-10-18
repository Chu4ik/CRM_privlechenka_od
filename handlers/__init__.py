import logging  # <-- ДОБАВЬТЕ ЭТУ СТРОКУ

from aiogram import Dispatcher, Router

# Импортируем модули 
from . import auth
from . import receipt
# from . import order
# from . import admin
# from . import finance

def register_all_routers(dp: Dispatcher):
    """Функция для регистрации всех роутеров в Диспетчере."""
    
    # Регистрация модулей. Порядок важен (auth должна быть первой)
    dp.include_router(auth.router)
    dp.include_router(receipt.router)
    
    # TODO: Раскомментировать по мере создания модулей
    # dp.include_router(order.router)
    # dp.include_router(admin.router)
    # dp.include_router(finance.router)
    
    logging.info("All handlers successfully registered.")