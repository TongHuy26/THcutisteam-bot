import os
import telebot

TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

users = set()

@bot.message_handler(commands=['start'])
def start(message):
    users.add(message.from_user.id)

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📊 Tools", "👤 Account")
    markup.row("ℹ️ Help", "🏓 Ping")

    bot.send_message(
        message.chat.id,
        "👋 Xin chào!\n\nBot đang hoạt động 24/7 🚀",
        reply_markup=markup
    )


@bot.message_handler(commands=['ping'])
def ping(message):
    bot.reply_to(message, "pong 🏓")


@bot.message_handler(commands=['help'])
def help(message):
    bot.reply_to(
        message,
        """
📖 Danh sách lệnh

/start - mở menu
/ping - test bot
/help - trợ giúp
/info - thông tin bot
"""
    )


@bot.message_handler(commands=['info'])
def info(message):
    bot.reply_to(
        message,
        f"""
🤖 Bot Information

👥 Users: {len(users)}
⚡ Status: Online
"""
    )


@bot.message_handler(func=lambda m: m.text == "🏓 Ping")
def ping_button(message):
    bot.reply_to(message, "pong 🏓")


@bot.message_handler(func=lambda m: m.text == "ℹ️ Help")
def help_button(message):
    help(message)


@bot.message_handler(func=lambda m: m.text == "📊 Tools")
def tools(message):
    bot.reply_to(message, "Tools đang phát triển 🚀")


@bot.message_handler(func=lambda m: m.text == "👤 Account")
def account(message):
    bot.reply_to(message, f"ID của bạn: {message.from_user.id}")


print("Bot is running...")

bot.infinity_polling()
