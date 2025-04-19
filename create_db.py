import sqlite3

DB_NAME = "food_diary.db"

# 📌 Функция для создания таблицы, если её нет
def create_tables():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS meals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        time TEXT,
        description TEXT,
        calories INTEGER,
        proteins REAL,
        fats REAL,
        carbs REAL
    )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Таблица 'meals' успешно создана!")

# 📌 Функция для сохранения записи в БД (исправленная)
def save_to_db(user_id, date, time, description, calories=None, proteins=None, fats=None, carbs=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO meals (user_id, date, time, description, calories, proteins, fats, carbs)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, date, time, description, calories, proteins, fats, carbs))
    
    conn.commit()
    conn.close()

# 📌 Функция для получения записей за определённый период
def get_meals(user_id, period="day"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if period == "day":
        time_filter = "date = date('now')"
    elif period == "week":
        time_filter = "date >= date('now', '-7 days')"
    elif period == "month":
        time_filter = "date >= date('now', '-30 days')"
    else:
        time_filter = "1=1"  # Получить все записи

    cursor.execute(f"SELECT date, time, description, calories, proteins, fats, carbs FROM meals WHERE user_id = ? AND {time_filter} ORDER BY date DESC, time DESC", (user_id,))
    meals = cursor.fetchall()
    conn.close()

    return meals

# 📌 Функция для удаления записи по ID
def delete_meal(meal_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
    conn.commit()
    conn.close()

# 📌 Запускаем создание таблицы при старте
create_tables()