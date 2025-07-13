from flask import Flask, request
import telebot
from datetime import datetime
import os
import json
from openai import OpenAI
from create_db import save_to_db  # подключение функции сохранения в базу

# 📌 Настройки
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "mysecret")  # секрет для безопасности

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

# 📌 Команды старт и помощь
@bot.message_handler(commands=['start'])  # ← Обработчик команды /start
def send_start(message):
    user_id = message.from_user.id
    bot.send_message(
        user_id,
        "Я — Sola, твой бот-дневник питания.\n"
        "Просто отправляй фото или пиши, что ела.\n"
        "Я всё посчитаю: калории, белки, жиры, углеводы и клетчатку 📊\n\n"
        "Маленькие шаги каждый день, и ты ближе к себе 🌿\n"
    )



# 📌 Обработка текстовых сообщений
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text_message(message):
    user_id = message.from_user.id
    text = message.text
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M")

    try:
        bot.send_message(user_id, "⏳ Определяю калорийность...")

        prompt = f"""
        Определи калорийность и БЖУ (белки, жиры, углеводы) для: {text}. 
        Ответь строго JSON-объектом, без пояснений, без форматирования, без других символов.
        Если JSON неверный, сам исправь и отправь только правильный объект:
        {{"calories": 0, "proteins": 0, "fats": 0, "carbs": 0}}
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )

        print(f"📸 Ответ от GPT по фото:\n{response.choices[0].message.content!r}")

        result_text = response.choices[0].message.content or ""
        print(f"📩 Ответ от GPT: {result_text!r}")

        if not result_text.strip():
            raise ValueError("Ответ от GPT пустой или None")

        if "{" not in result_text:
            raise ValueError("В ответе нет JSON-объекта")

        result_text = result_text[result_text.find("{"):].strip()

        try:
            nutrition = json.loads(result_text)
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка при парсинге JSON: {e}")
            raise ValueError("GPT вернул некорректный JSON")

        save_to_db(
            user_id,
            date,
            time,
            text,
            nutrition.get("calories"),
            nutrition.get("proteins"),
            nutrition.get("fats"),
            nutrition.get("carbs")
        )

        bot.reply_to(
            message,
            f"✅ Записано:\n📅 {date} ⏰ {time}\n🍽️ {text}\n"
            f"🔥 Калории: {nutrition.get('calories', '-')} ккал\n"
            f"💪 Белки: {nutrition.get('proteins', '-')} г\n"
            f"🥑 Жиры: {nutrition.get('fats', '-')} г\n"
            f"🍞 Углеводы: {nutrition.get('carbs', '-')} г"
        )

    except Exception as e:
        bot.send_message(user_id, f"❌ Ошибка: {e}")
        print(f"❌ Ошибка в обработке текста: {e}")

# 📸 Обработка фото
# 📸 Этап 1 — Распознаём продукты и их количество
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    photo = message.photo[-1]

    try:
        file_info = bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"

        bot.send_message(user_id, "📸 Обрабатываю фото...")

        # 📸 Этап 1 — Распознавание продуктов
        response_1 = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Посмотри на это фото и перечисли все продукты, которые ты видишь. 
Укажи примерный вес каждого продукта в граммах. Ответь строго JSON-объектом без пояснений. 
Пример: {"products": [{"name": "лосось", "grams": 80}, {"name": "вермишель", "grams": 100}]}"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": file_url
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )

        result_text_1 = response_1.choices[0].message.content or ""
        print(f"📩 Ответ от GPT (распознавание): {result_text_1!r}")

        if not result_text_1.strip():
            raise ValueError("GPT (распознавание) вернул пустой ответ")
        if "{" not in result_text_1:
            raise ValueError("В ответе GPT (распознавание) нет JSON")

        result_text_1 = result_text_1[result_text_1.find("{"):].strip()
        products_json = json.loads(result_text_1)
        products_list = products_json.get("products", [])

        if not products_list:
            raise ValueError("GPT не распознал ни одного продукта")

        # 📸 Этап 2 — Расчёт КБЖУ
        product_description = ", ".join([f"{item['grams']} г {item['name']}" for item in products_list])

        prompt_2 = f"""
Для следующих продуктов определи суммарную калорийность и БЖУ (белки, жиры, углеводы).
Укажи только финальный результат одним JSON-объектом. Пример:
{{"description": "{product_description}", "calories": 0, "proteins": 0, "fats": 0, "carbs": 0}}

Продукты: {product_description}
"""

        response_2 = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt_2}],
            max_tokens=200
        )

        result_text_2 = response_2.choices[0].message.content or ""
        print(f"📩 Ответ от GPT (КБЖУ): {result_text_2!r}")

        if not result_text_2.strip():
            raise ValueError("GPT (КБЖУ) вернул пустой ответ")
        if "{" not in result_text_2:
            raise ValueError("В ответе GPT (КБЖУ) нет JSON")

        result_text_2 = result_text_2[result_text_2.find("{"):].strip()
        nutrition = json.loads(result_text_2)

        # Сохраняем в базу
        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")

        save_to_db(
            user_id,
            date,
            time_str,
            nutrition.get("description", "[неизвестно]"),
            nutrition.get("calories"),
            nutrition.get("proteins"),
            nutrition.get("fats"),
            nutrition.get("carbs")
        )

        # Отправка результата пользователю
        bot.send_message(
            user_id,
            f"✅ Записано по фото:\n📅 {date} ⏰ {time_str}\n🍽️ {nutrition.get('description', '-')}\n"
            f"🔥 Калории: {nutrition.get('calories', '-')} ккал\n"
            f"💪 Белки: {nutrition.get('proteins', '-')} г\n"
            f"🥑 Жиры: {nutrition.get('fats', '-')} г\n"
            f"🍞 Углеводы: {nutrition.get('carbs', '-')} г"
        )

    except Exception as e:
        bot.send_message(user_id, f"❌ Ошибка при обработке фото: {e}")
        print(f"❌ Ошибка в обработке фото: {e}")


# 📌 Webhook для Telegram
@app.route(f"/{WEBHOOK_SECRET}", methods=['POST'])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

# 📌 Health check
@app.route("/", methods=["GET"])
def index():
    return "Бот работает 🟢", 200

# 📌 Запуск
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
