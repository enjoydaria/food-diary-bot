from flask import Flask, request
import telebot
from datetime import datetime
import os
import json
##from dotenv import load_dotenv
from openai import OpenAI

from create_db import save_to_db  # база остаётся прежней

# 📌 Загрузка .env
#load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "mysecret")  # для безопасности

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

# 📌 Обработка текстовых сообщений
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 Привет! Я твой дневник питания.\n\n"
                          "📌 Напиши, что ты съел — я определю КБЖУ и сохраню это!")

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

        result_text = response.choices[0].message.content.strip()
        if not result_text.startswith("{"):
            result_text = result_text[result_text.find("{"):]

        try:
            nutrition = json.loads(result_text)
        except json.JSONDecodeError:
            nutrition = {"calories": None, "proteins": None, "fats": None, "carbs": None}

        save_to_db(user_id, date, time, text,
                   nutrition["calories"], nutrition["proteins"], nutrition["fats"], nutrition["carbs"])

        bot.reply_to(message, f"✅ Записано:\n📅 {date} ⏰ {time}\n🍽️ {text}\n🔥 Калории: {nutrition['calories']} ккал\n💪 Белки: {nutrition['proteins']} г\n🥑 Жиры: {nutrition['fats']} г\n🍞 Углеводы: {nutrition['carbs']} г")
    except Exception as e:
        bot.send_message(user_id, f"❌ Ошибка: {e}")

# 📸 Обработка фото
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    photo = message.photo[-1]  # фото самого высокого качества

    try:
        file_info = bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"

        bot.send_message(user_id, "📸 Обрабатываю фото...")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Определи, что изображено на фото, и посчитай калорийность и БЖУ (белки, жиры, углеводы).
Верни строго JSON вида:
{"description": "...", "calories": 0, "proteins": 0, "fats": 0, "carbs": 0}

Никаких пояснений, только корректный JSON-объект."""
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
            max_tokens=200
        )

        result_text = response.choices[0].message.content.strip()
        if not result_text.startswith("{"):
            result_text = result_text[result_text.find("{"):]

        nutrition = json.loads(result_text)

        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")

        save_to_db(
            user_id,
            date,
            time_str,
            nutrition["description"],
            nutrition["calories"],
            nutrition["proteins"],
            nutrition["fats"],
            nutrition["carbs"]
        )

        bot.send_message(
            user_id,
            f"✅ Записано по фото:\n📅 {date} ⏰ {time_str}\n🍽️ {nutrition['description']}\n"
            f"🔥 Калории: {nutrition['calories']} ккал\n"
            f"💪 Белки: {nutrition['proteins']} г\n"
            f"🥑 Жиры: {nutrition['fats']} г\n"
            f"🍞 Углеводы: {nutrition['carbs']} г"
        )

    except Exception as e:
        bot.send_message(user_id, f"❌ Ошибка при обработке фото: {e}")

# 📌 Webhook endpoint
@app.route(f"/{WEBHOOK_SECRET}", methods=['POST'])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

# 📌 Health check (можно использовать в UptimeRobot)
@app.route("/", methods=["GET"])
def index():
    return "Бот работает 🟢", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
