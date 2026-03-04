import os
import telebot

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Missing BOT_TOKEN env var")

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "✅ Bot đang chạy trên Render! Gõ /ping để thử.")

@bot.message_handler(commands=["ping"])
def ping(message):
    bot.reply_to(message, "pong ✅")

bot.infinity_polling(skip_pending=True)
