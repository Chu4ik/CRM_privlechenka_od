import psycopg2
from config import DB_CONNECTION_STRING

class Database:
    """Класс для взаимодействия с базой данных PostgreSQL."""
    
    def __init__(self):
        # Автоматическое подключение
        try:
            self.conn = psycopg2.connect(DB_CONNECTION_STRING)
            print("Успешное подключение к PostgreSQL.")
        except Exception as e:
            print(f"Ошибка подключения к БД: {e}")
            self.conn = None
            
    def close(self):
        """Закрытие соединения с БД."""
        if self.conn:
            self.conn.close()
            print("Соединение с PostgreSQL закрыто.")

    def execute_query(self, query, params=None, fetch_one=False, fetch_all=False):
        """Общая функция для выполнения запросов (SELECT, INSERT, UPDATE, DELETE)."""
        if not self.conn:
            return None

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params)
                
                if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                    self.conn.commit()
                    # Возвращаем ID для INSERT или количество строк для UPDATE/DELETE
                    if query.strip().upper().startswith('INSERT') and cur.description is not None:
                         # Попытка получить ID, если это INSERT с RETURNING
                         # Это будет работать, если вы используете RETURNING id в INSERT запросе.
                         try:
                             return cur.fetchone()[0]
                         except TypeError:
                             return cur.rowcount # Если RETURNING не использовался
                    return cur.rowcount
                
                if fetch_one:
                    return cur.fetchone()
                if fetch_all:
                    # Возвращает список кортежей с результатами
                    return cur.fetchall()
                    
                return None
                
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"Ошибка выполнения SQL-запроса: {e}")
            return None

    # ------------------------------------------------------------------
    # --- Базовые Функции CRM ---
    
    def get_user_role(self, telegram_id):
        """Получение роли пользователя для авторизации."""
        query = "SELECT роль, имя FROM Пользователи WHERE telegram_id = %s"
        result = self.execute_query(query, (telegram_id,), fetch_one=True)
        
        if result:
            # Возвращает (роль, имя)
            return result
        return None, None # Если пользователь не найден

    def add_new_user(self, telegram_id, role, name, code=None):
        """Добавление нового пользователя (только для админа, но базовый метод)."""
        query = """
        INSERT INTO Пользователи (telegram_id, роль, имя, код_менеджера)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (telegram_id) DO NOTHING;
        """
        return self.execute_query(query, (telegram_id, role, name, code))
        
    # ------------------------------------------------------------------
    # --- Функции Справочников для модуля Прихода ---
    
    def get_suppliers(self):
        """Получает список всех поставщиков."""
        query = "SELECT id, название FROM Поставщики ORDER BY название"
        # Возвращает список кортежей: [(id, название), ...]
        return self.execute_query(query, fetch_all=True)

    def get_items_by_supplier(self, supplier_id):
        """Получает номенклатуру, соответствующую поставщику."""
        query = """
        SELECT id, название_товара, текущая_цена_закупки 
        FROM Номенклатура 
        WHERE поставщик_id = %s 
        ORDER BY название_товара
        """
        # Возвращает список: [(id, название_товара, цена), ...]
        return self.execute_query(query, (supplier_id,), fetch_all=True)
    
    def create_new_receipt(self, supplier_id, user_id):
        """Создание заголовка нового документа Прихода."""
        query = """
        INSERT INTO Приходы (поставщик_id, пользователь_id)
        VALUES (%s, %s)
        RETURNING id;
        """
        # Используем RETURNING id, чтобы получить ID созданного документа
        return self.execute_query(query, (supplier_id, user_id), fetch_one=True)


    def add_receipt_line(self, receipt_id, item_id, quantity, price):
        """Добавление строки в документ Прихода."""
        query = """
        INSERT INTO СтрокиПрихода (приход_id, номенклатура_id, количество, цена)
        VALUES (%s, %s, %s, %s);
        """
        return self.execute_query(query, (receipt_id, item_id, quantity, price))

    def update_inventory(self, item_id, quantity, price):
        """Обновление остатков на складе и средней цены закупки."""
        # 1. Сначала пытаемся обновить существующую запись
        update_query = """
        UPDATE ОстаткиСклада 
        SET количество = количество + %s,
            средняя_цена_закупки = ((средняя_цена_закупки * количество) + (%s * %s)) / (количество + %s)
        WHERE номенклатура_id = %s;
        """
        rows_updated = self.execute_query(update_query, (quantity, price, quantity, quantity, item_id))
        
        # 2. Если запись не была обновлена (товара нет в остатках), вставляем новую
        if rows_updated == 0:
            insert_query = """
            INSERT INTO ОстаткиСклада (номенклатура_id, количество, средняя_цена_закупки)
            VALUES (%s, %s, %s);
            """
            self.execute_query(insert_query, (item_id, quantity, price))
        
        # Если вы используете RETURNING, здесь может потребоваться дополнительная логика
        return True