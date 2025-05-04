import psycopg2
import os
from dotenv import load_dotenv

# 📦 Загружаем переменные из .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# 🔌 Подключение к базе
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    return conn, cursor

# 📌 Создание таблицы
def create_tables():
    conn, cursor = get_db_connection()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS meals (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        date TEXT,
        time TEXT,
        description TEXT,
        calories INTEGER,
        proteins REAL,
        fats REAL,
        carbs REAL
    );
    ''')

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Таблица 'meals' успешно создана!")

# 📌 Сохранение записи в базу
def save_to_db(user_id, date, time, description, calories=None, proteins=None, fats=None, carbs=None):
    print("📝 Пытаемся сохранить в БД:", user_id, date, time, description, calories, proteins, fats, carbs)
    try:
        conn, cursor = get_db_connection()
        cursor.execute('''
            INSERT INTO meals (user_id, date, time, description, calories, proteins, fats, carbs)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (user_id, date, time, description, calories, proteins, fats, carbs))
        conn.commit()
        print("✅ Успешно записано в базу!")
    except Exception as e:
        print("❌ Ошибка при сохранении в БД:", e)
    finally:
        cursor.close()
        conn.close()


# 📌 Получение записей за период
def get_meals(user_id, period="day"):
    conn, cursor = get_db_connection()

    if period == "day":
        time_filter = "date = CURRENT_DATE"
    elif period == "week":
        time_filter = "date >= CURRENT_DATE - INTERVAL '7 days'"
    elif period == "month":
        time_filter = "date >= CURRENT_DATE - INTERVAL '30 days'"
    else:
        time_filter = "TRUE"  # Получить всё

    cursor.execute(f'''
        SELECT date, time, description, calories, proteins, fats, carbs
        FROM meals
        WHERE user_id = %s AND {time_filter}
        ORDER BY date DESC, time DESC
    ''', (user_id,))

    meals = cursor.fetchall()
    cursor.close()
    conn.close()
    return meals

# 📌 Удаление записи по ID
def delete_meal(meal_id):
    conn, cursor = get_db_connection()

    cursor.execute("DELETE FROM meals WHERE id = %s", (meal_id,))
    conn.commit()
    cursor.close()
    conn.close()

# 🚀 Только один раз запускается для создания таблицы
if __name__ == "__main__":
    create_tables()
