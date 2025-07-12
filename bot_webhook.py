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
