import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import Database  # Для анотації типів
from .auth import get_main_menu  # Для повернення в головне меню

router = Router()

# ----------------------------------------------------------------------
# FSM СТАНЫ
# ----------------------------------------------------------------------

class ReceiptStates(StatesGroup):
    waiting_for_supplier = State()
    waiting_for_item_name = State()
    waiting_for_quantity = State()
    waiting_for_price = State()
    # Стан adding_more_items видалено, оскільки його логіка інтегрована в waiting_for_item_name

# ----------------------------------------------------------------------
# КЛАВІАТУРИ (Залишаємо для обробки меню)
# ----------------------------------------------------------------------

def get_receipt_menu():
    """Клавіатура для процесу приходу: завершення або скасування."""
    # Примітка: Ця функція більше не використовується для виводу,
    # але залишена, якщо потрібна для інших цілей.
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="✅ Завершити Прихід")],
            [types.KeyboardButton(text="❌ Скасувати Прихід")]
        ],
        resize_keyboard=True
    )

# ----------------------------------------------------------------------
# ОСНОВНИЙ ЦИКЛ ПРИЙМАННЯ ТОВАРУ
# ----------------------------------------------------------------------

@router.message(F.text == "📦 Склад/Приход" or F.text == "📦 Приемка Товара")
async def handle_start_receipt(message: types.Message, state: FSMContext, db: Database):
    telegram_id = message.from_user.id
    role, _ = db.get_user_role(telegram_id) 

    if role not in ['админ', 'завсклада']:
        await message.reply("У вас немає прав для доступу до цього модуля.")
        return

    # 1. Отримання списку постачальників
    suppliers = db.get_suppliers() 

    if not suppliers:
        await message.reply("В системі немає зареєстрованих постачальників. Операція скасована.")
        await state.clear()
        return

    # 2. Формування клавіатури постачальників
    supplier_map = {name: id for id, name in suppliers}
    
    await state.set_data({'supplier_map': supplier_map})

    buttons = [types.KeyboardButton(text=name) for name in supplier_map.keys()]
    keyboard_rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard_rows.append([types.KeyboardButton(text="❌ Скасувати Прихід")])
    
    menu = types.ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True,
        input_field_placeholder="Оберіть постачальника"
    )

    await state.set_state(ReceiptStates.waiting_for_supplier)
    await message.reply("Почнімо приймання товару. Оберіть постачальника:", reply_markup=menu)


@router.message(ReceiptStates.waiting_for_supplier)
async def process_supplier(message: types.Message, state: FSMContext, db: Database):
    supplier_name = message.text
    data = await state.get_data()
    supplier_map = data.get('supplier_map')
    
    if supplier_name == "❌ Скасувати Прихід":
        await state.clear()
        await message.reply("Приймання товару скасовано.", reply_markup=get_main_menu(db.get_user_role(message.from_user.id)[0]))
        return

    if supplier_name not in supplier_map:
        await message.reply("Будь ласка, оберіть постачальника зі списку кнопок.")
        return

    supplier_id = supplier_map[supplier_name]
    
    # 1. Отримання номенклатури постачальника
    items = db.get_items_by_supplier(supplier_id)
    
    if not items:
        await message.reply(f"У постачальника **{supplier_name}** немає зареєстрованої номенклатури. Оберіть іншого або скасуйте.", parse_mode="Markdown")
        return

    # item_map: {назва: (id, ціна)}
    item_map = {name: (id, price) for id, name, price in items}
    
    # 2. Зберігання даних про постачальника і номенклатуру
    await state.update_data(
        current_receipt_supplier_id=supplier_id,
        current_receipt_supplier_name=supplier_name,
        current_items_map=item_map,
        current_receipt_id=None
    )
    
    # 3. Формування клавіатури товарів (+ завершення/скасування)
    item_buttons = [types.KeyboardButton(text=name) for name in item_map.keys()]
    keyboard_rows = [item_buttons[i:i + 2] for i in range(0, len(item_buttons), 2)]
    keyboard_rows.append([types.KeyboardButton(text="✅ Завершити Прихід"), types.KeyboardButton(text="❌ Скасувати Прихід")])
    
    menu = types.ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True,
        input_field_placeholder=f"Оберіть товар від {supplier_name}"
    )

    await state.set_state(ReceiptStates.waiting_for_item_name)
    await message.reply(f"Ви обрали **{supplier_name}**. Оберіть товар для оприбуткування:", reply_markup=menu, parse_mode="Markdown")

# ----------------------------------------------------------------------
# ПРІОРИТЕТНІ ОБРОБНИКИ ДЛЯ waiting_for_item_name (ЗАВЕРШЕННЯ/СКАСУВАННЯ)
# ----------------------------------------------------------------------

@router.message(ReceiptStates.waiting_for_item_name, F.text == "✅ Завершити Прихід")
async def handle_finish_receipt(message: types.Message, state: FSMContext, db: Database):
    data = await state.get_data()
    receipt_id = data.get('current_receipt_id')
    
    role, _ = db.get_user_role(message.from_user.id)
    
    await message.reply(
        f"🎉 **Прихід №{receipt_id} успішно завершено!**\nДані записані, залишки оновлено.",
        reply_markup=get_main_menu(role),
        parse_mode="Markdown"
    )
    await state.clear() 

@router.message(ReceiptStates.waiting_for_item_name, F.text == "❌ Скасувати Прихід")
async def handle_cancel_receipt_item_name_state(message: types.Message, state: FSMContext, db: Database):
    await state.clear()
    await message.reply("Приймання товару скасовано.", reply_markup=get_main_menu(db.get_user_role(message.from_user.id)[0]))

# ----------------------------------------------------------------------
# ОСНОВНИЙ ОБРОБНИК ВИБОРУ ТОВАРУ
# ----------------------------------------------------------------------

@router.message(ReceiptStates.waiting_for_item_name)
async def process_item_name(message: types.Message, state: FSMContext, db: Database):
    item_name = message.text
    
    # Пріоритетні кнопки оброблені вище, тут лише перевіряємо, чи це назва товару
    
    data = await state.get_data()
    item_map = data.get('current_items_map')

    if item_name not in item_map:
        # Повторно надсилаємо клавіатуру, якщо користувач ввів невідомий текст
        supplier_name = data.get('current_receipt_supplier_name')
        
        item_buttons = [types.KeyboardButton(text=name) for name in item_map.keys()]
        keyboard_rows = [item_buttons[i:i + 2] for i in range(0, len(item_buttons), 2)]
        keyboard_rows.append([types.KeyboardButton(text="✅ Завершити Прихід"), types.KeyboardButton(text="❌ Скасувати Прихід")])
        
        menu = types.ReplyKeyboardMarkup(
            keyboard=keyboard_rows,
            resize_keyboard=True,
            input_field_placeholder=f"Додайте наступний товар від {supplier_name}"
        )
        
        await message.reply("Пожалуйста, выберите товар из предложенных кнопок.", reply_markup=menu)
        return

    item_id, default_price = item_map[item_name]
    
    # Зберігаємо ID та ім'я товару в контекст
    await state.update_data(
        current_item_id=item_id,
        current_item_name=item_name,
        current_price=default_price # Може бути використана як підказка при редагуванні
    )

    await state.set_state(ReceiptStates.waiting_for_quantity)
    
    # Виводимо клавіатуру скасування
    menu = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="❌ Скасувати Прихід")]],
        resize_keyboard=True
    )
    await message.reply(f"Товар: **{item_name}**.\nВведіть кількість (наприклад, 10.5):",
                        reply_markup=menu,
                        parse_mode="Markdown")

# ----------------------------------------------------------------------
# ОБРОБНИКИ КІЛЬКОСТІ ТА ЦІНИ
# ----------------------------------------------------------------------

@router.message(ReceiptStates.waiting_for_quantity)
async def process_quantity(message: types.Message, state: FSMContext, db: Database):
    try:
        quantity = float(message.text.replace(',', '.'))
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await message.reply("Невірний формат. Введіть кількість числом (наприклад, 10 або 5.5):")
        return

    if message.text == "❌ Скасувати Прихід":
        await state.clear()
        await message.reply("Приймання товару скасовано.", reply_markup=get_main_menu(db.get_user_role(message.from_user.id)[0]))
        return

    await state.update_data(current_quantity=quantity)
    
    # --- ЕТАП ПІДТВЕРДЖЕННЯ КІЛЬКОСТІ ---
    data = await state.get_data()
    item_name = data['current_item_name']
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Продовжити (Ввести ціну)", callback_data="receipt_confirm_quantity")],
        [types.InlineKeyboardButton(text="✏️ Змінити кількість", callback_data="receipt_edit_quantity")]
    ])
    
    await message.reply(
        f"Товар **{item_name}**:\nВведена кількість: **{quantity}**.\nВсе вірно?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@router.message(ReceiptStates.waiting_for_price)
async def process_price_and_save_line(message: types.Message, state: FSMContext, db: Database):
    try:
        price = float(message.text.replace(',', '.'))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.reply("Невірний формат. Введіть ціну числом (наприклад, 50.00):")
        return

    if message.text == "❌ Скасувати Прихід":
        await state.clear()
        await message.reply("Приймання товару скасовано.", reply_markup=get_main_menu(db.get_user_role(message.from_user.id)[0]))
        return

    await state.update_data(current_price=price)
    
    # --- ЕТАП ПІДТВЕРДЖЕННЯ ЦІНИ ТА ЗАПИСУ ---
    data = await state.get_data()
    item_name = data['current_item_name']
    quantity = data['current_quantity']
    total_amount = round(quantity * price, 2)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Зберегти та додати", callback_data="receipt_save_line")],
        [types.InlineKeyboardButton(text="✏️ Змінити кількість", callback_data="receipt_edit_quantity")],
        [types.InlineKeyboardButton(text="✏️ Змінити ціну", callback_data="receipt_edit_price")]
    ])
    
    await message.reply(
        f"**Перевірте дані перед записом:**\n"
        f"Товар: {item_name}\n"
        f"Кількість: {quantity}\n"
        f"Ціна: {price} за од.\n"
        f"Сума: {total_amount}",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


# ----------------------------------------------------------------------
# ОБРОБНИКИ INLINE-КНОПОК (РЕДАГУВАННЯ ТА ЗБЕРЕЖЕННЯ)
# ----------------------------------------------------------------------

@router.callback_query(F.data == "receipt_confirm_quantity", ReceiptStates.waiting_for_quantity)
async def handle_confirm_quantity(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ReceiptStates.waiting_for_price)
    await callback.message.edit_text("Кількість підтверджено. Введіть ціну за одиницю товару:")
    await callback.answer()


@router.callback_query(F.data == "receipt_edit_quantity")
async def handle_edit_quantity(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ReceiptStates.waiting_for_quantity)
    
    # 1. Редагуємо старе повідомлення, прибираючи Inline-клавіатуру
    await callback.message.edit_text(
        "✏️ Ви обрали **редагування кількості**.",
        parse_mode="Markdown",
        reply_markup=None # <--- Важливо: прибираємо клавіатуру!
    )
    
    # 2. Надсилаємо нове повідомлення з Reply-клавіатурою
    menu = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="❌ Скасувати Прихід")]],
        resize_keyboard=True
    )
    await callback.message.answer(
        "**Введіть нове значення кількості** (наприклад, 10.5):",
        reply_markup=menu,
        parse_mode="Markdown"
    )
    await callback.answer("Ви перейшли до редагування кількості.")


@router.callback_query(F.data == "receipt_edit_price")
async def handle_edit_price(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ReceiptStates.waiting_for_price)
    
    # 1. Редагуємо старе повідомлення, прибираючи Inline-клавіатуру
    await callback.message.edit_text(
        "✏️ Ви обрали **редагування ціни**.",
        parse_mode="Markdown",
        reply_markup=None # <--- Важливо: прибираємо клавіатуру!
    )

    # 2. Надсилаємо нове повідомлення з Reply-клавіатурою
    menu = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="❌ Скасувати Прихід")]],
        resize_keyboard=True
    )
    await callback.message.answer(
        "**Введіть нове значення ціни** за одиницю (наприклад, 50.00):",
        reply_markup=menu,
        parse_mode="Markdown"
    )
    await callback.answer("Ви перейшли до редагування ціни.")



@router.callback_query(F.data == "receipt_save_line", ReceiptStates.waiting_for_price)
async def handle_save_line(callback: types.CallbackQuery, state: FSMContext, db: Database):
    
    # ----------------------------------------------------
    # 1. ЗАХИСТ ВІД ПОДВІЙНОГО НАТИСКАННЯ ТА ВИДАЛЕННЯ КНОПКИ
    # ----------------------------------------------------
    
    # Негайно відповідаємо на callback, щоб запобігти повторному надсиланню
    await callback.answer("Рядок успішно збережено!") 
    
    # Редагуємо повідомлення, прибираючи кнопку "Зберегти" перед записом у БД
    await callback.message.edit_text(
        "📝 **Виконується запис...**",
        parse_mode="Markdown",
        reply_markup=None 
    )

    data = await state.get_data()
    price = data['current_price']
    quantity = data['current_quantity']
    item_id = data['current_item_id']
    item_name = data['current_item_name']
    
    # Розрахунок суми для рядка
    line_total = round(quantity * price, 2)
    
    receipt_id = data.get('current_receipt_id')
    
    # ----------------------------------------------------
    # 2. СТВОРЕННЯ ЗАГОЛОВКА ТА ОБЛІК ЗАБОРГОВАНОСТІ
    # ----------------------------------------------------
    if not receipt_id:
        supplier_id = data['current_receipt_supplier_id']
        
        # Створення документа приходу (повертає ID або None)
        receipt_id = db.create_new_receipt(
            supplier_id=supplier_id,
            user_id=callback.from_user.id
        )
        
        if not receipt_id:
             await callback.message.answer("Помилка при створенні документа приходу. Операція скасована.")
             await state.clear()
             return
             
        # РЕЄСТРАЦІЯ ПОЧАТКОВОГО БОРГУ: статус 'не оплачено' (вирішення CHECK constraint)
        db.register_initial_debt(receipt_id) 
        
        await state.update_data(current_receipt_id=receipt_id)

    # 3. Додаємо рядок приходу та оновлюємо залишки
    db.add_receipt_line(
        receipt_id=receipt_id,
        item_id=item_id,
        quantity=quantity,
        price=price
    )
    db.update_inventory(
        item_id=item_id,
        quantity=quantity,
        price=price
    )

    # 4. ОНОВЛЕННЯ СУМИ БОРГУ НА СУМУ НОВОГО РЯДКА
    db.update_debt_amount(receipt_id, line_total)
    
    # ----------------------------------------------------
    # 5. ПЕРЕХІД ДО ДОДАВАННЯ НАСТУПНОГО ТОВАРУ
    # ----------------------------------------------------
    supplier_name = data.get('current_receipt_supplier_name')
    item_map = data['current_items_map']

    # Формування клавіатури товарів + кнопки завершення/скасування
    item_buttons = [types.KeyboardButton(text=name) for name in item_map.keys()]
    keyboard_rows = [item_buttons[i:i + 2] for i in range(0, len(item_buttons), 2)]
    keyboard_rows.append([types.KeyboardButton(text="✅ Завершити Прихід"), types.KeyboardButton(text="❌ Скасувати Прихід")])
    
    menu_for_next_item = types.ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True,
        input_field_placeholder=f"Додайте наступний товар від {supplier_name}"
    )

    # Встановлення FSM-стану для очікування наступного товару
    await state.set_state(ReceiptStates.waiting_for_item_name) 
    
    # Надсилаємо НОВЕ повідомлення з Reply-клавіатурою (з товарами)
    await callback.message.answer(
        f"✅ Товар **{item_name}** додано до приходу №{receipt_id}. Облік оновлено. (Сума: **{line_total}**)\n"
        f"Продовжуємо. Оберіть наступний товар від **{supplier_name}**:", 
        reply_markup=menu_for_next_item, 
        parse_mode="Markdown"
    )

# ----------------------------------------------------------------------
# СКАСУВАННЯ В ІНШИХ СТАНАХ (НЕ waiting_for_item_name)
# ----------------------------------------------------------------------

@router.message(F.text == "❌ Скасувати Прихід")
async def handle_cancel_anywhere(message: types.Message, state: FSMContext, db: Database):
    await state.clear()
    await message.reply("Приймання товару скасовано.", reply_markup=get_main_menu(db.get_user_role(message.from_user.id)[0]))