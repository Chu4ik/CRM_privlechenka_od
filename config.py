import os
from dotenv import load_dotenv

# Загрузка переменных из .env
load_dotenv()

# Настройки Бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", 0))

# Настройки Базы Данных
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Строка подключения для psycopg2
DB_CONNECTION_STRING = (
    f"host='{DB_HOST}' dbname='{DB_NAME}' user='{DB_USER}' password='{DB_PASSWORD}'"
)

# Проверка, что токен и данные БД загружены
if not all([BOT_TOKEN, DB_HOST, DB_NAME, DB_USER, DB_PASSWORD]):
    raise EnvironmentError("Не все необходимые переменные окружения загружены из .env!")