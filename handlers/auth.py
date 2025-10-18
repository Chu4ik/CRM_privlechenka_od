import logging
from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from database import Database # Пока импортируем явно, потом будем брать из dp

# Инициализация роутера для этого модуля
router = Router()

# --- Вспомогательные функции ---

def get_main_menu(role):
    """Генерирует главное меню в зависимости от роли."""
    # (КОД ФУНКЦИИ get_main_menu ИЗ bot.py ПЕРЕНОСИМ СЮДА)
    # ... (Оставьте ту же реализацию ReplyKeyboardMarkup)
    buttons = []
    
    if role == 'админ':
        buttons = [
            [types.KeyboardButton(text="📊 Отчеты"), types.KeyboardButton(text="⚙️ Управление Справочниками")],
            [types.KeyboardButton(text="⚠️ Неподтвержденные Заказы"), types.KeyboardButton(text="📦 Склад/Приход")],
            [types.KeyboardButton(text="💰 Расчеты"), types.KeyboardButton(text="🛠️ Корректировки")]
        ]
    # ... (Добавьте логику для других ролей)
    elif role == 'завсклада':
        buttons = [
            [types.KeyboardButton(text="📦 Приемка Товара"), types.KeyboardButton(text="🛠️ Корректировки Остатков")]
        ]
    
    menu = types.ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие из меню"
    )
    return menu

# --- Обработчики ---

@router.message(CommandStart())
async def send_welcome(message: types.Message, state: FSMContext, db: Database = None):
    """Обработчик команды /start и авторизация."""
    
    # Очищаем все текущие состояния FSM при старте
    await state.clear()
    
    # Получаем объект БД из контекста Dispatcher
    if db is None:
        db = message.bot.get('db') 
        if not db:
             # Это на случай, если db не передана через dp
             from database import Database
             db = Database()
             
    telegram_id = message.from_user.id
    
    # 1. Проверка роли пользователя в БД
    role, name = db.get_user_role(telegram_id)
    
    if role:
        # Пользователь авторизован
        menu = get_main_menu(role)
        await message.reply(
            f"Привет, {name}! Ваша роль: **{role}**.\nВыберите действие:",
            reply_markup=menu,
            parse_mode="Markdown"
        )
    # ... (логика для неавторизованного пользователя)
    else:
        await message.reply("У вас нет доступа. Обратитесь к администратору.")


@router.message(F.text == "Назад в меню" or F.text == "Отмена")
async def handle_cancel(message: types.Message, state: FSMContext, db: Database = None):
    """Обработчик для отмены любого текущего процесса."""
    await state.clear()
    
    if db is None:
        db = message.bot.get('db')
    
    role, _ = db.get_user_role(message.from_user.id)
    
    await message.reply("Действие отменено.", reply_markup=get_main_menu(role))