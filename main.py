import os
import time
import sqlite3
import telebot
import requests
import json
import re
from urllib.parse import quote
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

DB_PATH = "bot.db"

# ---------- DATABASE ----------
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

conn = db()
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  first_seen INTEGER,
  last_seen INTEGER,
  is_premium INTEGER DEFAULT 0
)
""")

conn.commit()

def upsert_user(user):
    now = int(time.time())
    uid = user.id

    cur.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()

    if row:
        cur.execute("UPDATE users SET last_seen=? WHERE user_id=?", (now, uid))
    else:
        cur.execute(
            "INSERT INTO users(user_id, first_seen, last_seen, is_premium) VALUES (?,?,?,0)",
            (uid, now, now)
        )

    conn.commit()

def is_premium(uid):
    cur.execute("SELECT is_premium FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    return bool(r and r[0] == 1)

# ---------- RATE LIMIT ----------
FREE_LIMIT = 10
WINDOW = 300

rate_data = {}

def allow(uid):
    now = time.time()

    if is_premium(uid):
        return True

    data = rate_data.get(uid)

    if not data:
        rate_data[uid] = [now, 1]
        return True

    start, used = data

    if now - start > WINDOW:
        rate_data[uid] = [now, 1]
        return True

    if used >= FREE_LIMIT:
        return False

    rate_data[uid][1] += 1
    return True

# ---------- MENU ----------
def menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📊 Tools"), KeyboardButton("👤 Account"))
    kb.row(KeyboardButton("⭐ Premium"), KeyboardButton("ℹ️ Help"))
    return kb

# ---------- TIKTOK TOOL ----------

TT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.tiktok.com/"
}

SESSION = requests.Session()
SESSION.headers.update(TT_HEADERS)

cache = {}

def get_html(url):
    try:
        r = SESSION.get(url, timeout=10)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return None

def extract_json(html):
    try:
        match = re.search(
            r'<script id="UNIVERSAL_DATA_FOR_REHYDRATION".*?>(.*?)</script>',
            html,
            re.S
        )
        if not match:
            return None
        return json.loads(match.group(1))
    except:
        return None

def parse_user(data):
    try:
        user = data["DEFAULT_SCOPE"]["webapp.user-detail"]["userInfo"]["user"]
        stats = data["DEFAULT_SCOPE"]["webapp.user-detail"]["userInfo"]["stats"]

        return {
            "uid": user["id"],
            "username": user["uniqueId"],
            "nickname": user["nickname"],
            "followers": stats["followerCount"],
            "following": stats["followingCount"],
            "likes": stats["heartCount"],
            "videos": stats["videoCount"]
        }
    except:
        return None

def get_tiktok(username):

    username = username.lower().replace("@", "")

    if username in cache:
        return cache[username]

    url = f"https://www.tiktok.com/@{quote(username)}"

    html = get_html(url)

    if html:
        data = extract_json(html)

        if data:
            user = parse_user(data)

            if user:
                cache[username] = user
                return user

    return None

# ---------- COMMANDS ----------

@bot.message_handler(commands=["start"])
def start(message):

    upsert_user(message.from_user)

    bot.send_message(
        message.chat.id,
        "👋 Xin chào\n\nBot đang hoạt động 24/7 🚀",
        reply_markup=menu()
    )

@bot.message_handler(commands=["help"])
def help(message):

    bot.send_message(
        message.chat.id,
        """
📖 Lệnh bot

/start
/help
/info
/ping
/tiktok username
"""
    )

@bot.message_handler(commands=["ping"])
def ping(message):

    if not allow(message.from_user.id):
        bot.reply_to(message, "⛔ Bạn đã hết lượt")
        return

    bot.reply_to(message, "pong 🏓")

@bot.message_handler(commands=["info"])
def info(message):

    uid = message.from_user.id
    prem = "Premium" if is_premium(uid) else "Free"

    bot.send_message(
        message.chat.id,
        f"""
👤 ID: {uid}
⭐ Gói: {prem}
"""
    )

@bot.message_handler(commands=["tiktok"])
def tiktok(message):

    if not allow(message.from_user.id):
        bot.reply_to(message, "⛔ Bạn đã hết lượt")
        return

    args = message.text.split()

    if len(args) < 2:
        bot.reply_to(message, "Dùng: /tiktok username")
        return

    username = args[1]

    bot.reply_to(message, "⏳ Đang lấy dữ liệu...")

    data = get_tiktok(username)

    if not data:
        bot.send_message(message.chat.id, "❌ Không lấy được data")
        return

    bot.send_message(
        message.chat.id,
        f"""
🎵 TikTok

User: @{data['username']}
Nick: {data['nickname']}

Followers: {data['followers']}
Following: {data['following']}
Likes: {data['likes']}
Videos: {data['videos']}

https://www.tiktok.com/@{data['username']}
"""
    )

print("Bot running...")

bot.infinity_polling()
