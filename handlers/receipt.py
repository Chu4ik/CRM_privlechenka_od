import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database
from .auth import get_main_menu # Для возврата в меню

# Определяем состояния для процесса оприходования
class ReceiptStates(StatesGroup):
    waiting_for_supplier = State()
    waiting_for_item_name = State()
    waiting_for_quantity = State()
    waiting_for_price = State()
    confirm_receipt = State()

router = Router()

# --- Начало процесса (Обновленный обработчик) ---

@router.message(F.text == "📦 Склад/Приход" or F.text == "📦 Приемка Товара")
async def handle_start_receipt(message: types.Message, state: FSMContext, db):
    
    # Теперь объект db (который является экземпляром класса Database) 
    # будет гарантированно передан сюда из контекста Dispatcher.
    
    telegram_id = message.from_user.id
    # Используем метод get_user_role, который находится в database.py
    role, _ = db.get_user_role(telegram_id) 

    if role not in ['админ', 'завсклада']:
        await message.reply("У вас нет прав для доступа к этому модулю.")
        return
        
    suppliers = db.get_suppliers()
        
    if not suppliers:
        await message.reply("В системе нет зарегистрированных поставщиков. Сначала добавьте их через модуль 'Управление Справочниками'.")
        return

    # 1. Формируем клавиатуру с поставщиками
    supplier_buttons = [types.KeyboardButton(text=name) for id, name in suppliers]
    keyboard_rows = [supplier_buttons[i:i + 2] for i in range(0, len(supplier_buttons), 2)]
    keyboard_rows.append([types.KeyboardButton(text="Отмена")]) # Кнопка отмены
    
    menu = types.ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True,
        input_field_placeholder="Выберите поставщика"
    )
    
    # 2. Сохраняем справочник поставщиков
    supplier_map = {name: id for id, name in suppliers}
    await state.update_data(supplier_map=supplier_map)
    
    # 3. Переход в первое состояние
    await state.set_state(ReceiptStates.waiting_for_supplier)
    await message.reply("Вы начали процесс **Оприходования Товара**.\nПожалуйста, выберите поставщика:", 
                        reply_markup=menu, 
                        parse_mode="Markdown")

# --- Шаг 2: Выбор Поставщика ---

@router.message(ReceiptStates.waiting_for_supplier)
async def process_supplier(message: types.Message, state: FSMContext, db: Database = None):
    
    if db is None: db = message.bot.get('db') 
        
    data = await state.get_data()
    supplier_map = data.get('supplier_map')
    supplier_name = message.text
    
    if supplier_name not in supplier_map:
        await message.reply("Пожалуйста, выберите поставщика из предложенных кнопок или нажмите 'Отмена'.")
        return
        
    supplier_id = supplier_map[supplier_name]
    
    # 2. Получаем номенклатуру по выбранному поставщику (нужна новая функция в database.py для этого)
    items = db.get_items_by_supplier(supplier_id) 
    
    # ... (Остальная логика для перехода к выбору товара, как было в предыдущем ответе)
    # ...
    
    # 4. Формируем клавиатуру с товарами и переходим в ReceiptStates.waiting_for_item_name
    await state.update_data(
        current_receipt_supplier_id=supplier_id,
        current_receipt_supplier_name=supplier_name,
        current_items_map={item[1]: (item[0], item[2]) for item in items} # {Название: (ID, Цена)}
    )

    # 4. Формируем клавиатуру с товарами (нужна кнопка "Назад")
    item_buttons = [types.KeyboardButton(text=item[1]) for item in items]
    keyboard_rows = [item_buttons[i:i + 2] for i in range(0, len(item_buttons), 2)]
    keyboard_rows.append([types.KeyboardButton(text="Отмена")])
    
    menu = types.ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True,
        input_field_placeholder=f"Выберите товар от {supplier_name}"
    )

    await state.set_state(ReceiptStates.waiting_for_item_name)
    await message.reply(f"Поставщик: **{supplier_name}**.\nТеперь выберите товар из списка:", 
                        reply_markup=menu, 
                        parse_mode="Markdown")
    
    # --- Шаг 3: Ожидание количества товара ---
@router.message(ReceiptStates.waiting_for_item_name)
async def process_item_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    item_map = data.get('current_items_map')
    item_name = message.text

    if item_name not in item_map:
        await message.reply("Пожалуйста, выберите товар из предложенных кнопок.")
        return

    item_id, default_price = item_map[item_name]
    
    # Сохраняем ID и имя товара в контекст
    await state.update_data(
        current_item_id=item_id,
        current_item_name=item_name
    )

    await state.set_state(ReceiptStates.waiting_for_quantity)
    
    # Убираем клавиатуру с товарами и просим ввести число
    menu = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Отмена")]],
        resize_keyboard=True
    )
    await message.reply(f"Товар: **{item_name}**.\nВведите количество (например, 10.5):",
                        reply_markup=menu,
                        parse_mode="Markdown")

# --- Шаг 4: Ожидание цены закупки ---
@router.message(ReceiptStates.waiting_for_quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    try:
        quantity = float(message.text.replace(',', '.'))
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await message.reply("Неверный формат. Введите количество числом (например, 10 или 5.5):")
        return

    await state.update_data(current_quantity=quantity)
    await state.set_state(ReceiptStates.waiting_for_price)

    await message.reply("Введите цену за единицу товара (например, 50.00):")

# --- Шаг 5: Подтверждение и запись в БД ---
@router.message(ReceiptStates.waiting_for_price)
async def process_price_and_confirm(message: types.Message, state: FSMContext, db):
    try:
        price = float(message.text.replace(',', '.'))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.reply("Неверный формат. Введите цену числом (например, 50.00):")
        return

    data = await state.get_data()
    supplier_id = data['current_receipt_supplier_id']
    item_id = data['current_item_id']
    quantity = data['current_quantity']
    
    # Вычисляем общую сумму
    total_amount = round(quantity * price, 2)
    
    # 1. Создаем заголовок прихода
    # Мы ожидаем, что execute_query вернет ID нового прихода
    new_receipt_id = db.create_new_receipt(
        supplier_id=supplier_id,
        user_id=message.from_user.id
    )

    if not new_receipt_id:
        await message.reply("Ошибка при создании документа прихода. Операция отменена.", 
                            reply_markup=get_main_menu('админ'))
        await state.clear()
        return

    # 2. Создаем строку прихода
    db.add_receipt_line(
        receipt_id=new_receipt_id,
        item_id=item_id,
        quantity=quantity,
        price=price
    )
    
    # 3. Обновляем остатки на складе
    db.update_inventory(
        item_id=item_id,
        quantity=quantity,
        price=price # Опционально: для обновления средней цены закупки
    )
    
    summary = (
        f"✅ **Приход успешно оформлен!**\n"
        f"Документ №: {new_receipt_id}\n"
        f"Товар: {data['current_item_name']}\n"
        f"Количество: {quantity}\n"
        f"Цена закупки: {price} за ед.\n"
        f"**Общая сумма: {total_amount}**"
    )

    await message.reply(summary, 
                        reply_markup=get_main_menu(db.get_user_role(message.from_user.id)[0]), 
                        parse_mode="Markdown")
    await state.clear()