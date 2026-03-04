import os
import time
import sqlite3
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Missing BOT_TOKEN env var")

# Admin IDs: điền ID Telegram của bạn (lệnh /myid để lấy)
ADMIN_IDS = set()
ADMIN_IDS_ENV = os.getenv("ADMIN_IDS", "").strip()
if ADMIN_IDS_ENV:
    try:
        ADMIN_IDS = {int(x.strip()) for x in ADMIN_IDS_ENV.split(",") if x.strip()}
    except Exception:
        ADMIN_IDS = set()

DB_PATH = "bot.db"
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ---------- DB ----------
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

conn = db()
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  first_seen INTEGER NOT NULL,
  last_seen INTEGER NOT NULL,
  is_premium INTEGER NOT NULL DEFAULT 0
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS rate_limit (
  user_id INTEGER PRIMARY KEY,
  window_start INTEGER NOT NULL,
  used INTEGER NOT NULL
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

def is_premium(uid: int) -> bool:
    cur.execute("SELECT is_premium FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    return bool(r and r[0] == 1)

def set_premium(uid: int, value: bool):
    cur.execute("UPDATE users SET is_premium=? WHERE user_id=?", (1 if value else 0, uid))
    conn.commit()

def stats():
    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE is_premium=1")
    premium = cur.fetchone()[0]
    return total, premium

# ---------- Anti spam / Rate limit ----------
# Free: 10 lệnh / 5 phút | Premium: không giới hạn
WINDOW_SEC = 300
FREE_LIMIT = 10

def allow(uid: int) -> bool:
    if is_premium(uid):
        return True
    now = int(time.time())
    cur.execute("SELECT window_start, used FROM rate_limit WHERE user_id=?", (uid,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO rate_limit(user_id, window_start, used) VALUES (?,?,?)", (uid, now, 1))
        conn.commit()
        return True

    window_start, used = r
    if now - window_start > WINDOW_SEC:
        cur.execute("UPDATE rate_limit SET window_start=?, used=? WHERE user_id=?", (now, 1, uid))
        conn.commit()
        return True

    if used >= FREE_LIMIT:
        return False

    cur.execute("UPDATE rate_limit SET used=used+1 WHERE user_id=?", (uid,))
    conn.commit()
    return True

def deny_msg():
    return "⛔ Bạn đã dùng hết lượt miễn phí (10 lệnh / 5 phút). Nâng <b>Premium</b> để dùng không giới hạn."

# ---------- UI ----------
def main_menu_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📊 Tools"), KeyboardButton("👤 Account"))
    kb.row(KeyboardButton("⭐ Premium"), KeyboardButton("ℹ️ Help"))
    return kb

def admin_menu_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📈 Stats"), KeyboardButton("📣 Broadcast"))
    kb.row(KeyboardButton("⭐ Premium Set"), KeyboardButton("⬅️ Back"))
    return kb

# ---------- Commands ----------
@bot.message_handler(commands=["start"])
def cmd_start(message):
    upsert_user(message.from_user)
    bot.send_message(
        message.chat.id,
        "👋 Xin chào!\n\n✅ Bot đang online 24/7.\nGõ /menu để mở menu.",
        reply_markup=main_menu_kb()
    )

@bot.message_handler(commands=["menu"])
def cmd_menu(message):
    upsert_user(message.from_user)
    bot.send_message(message.chat.id, "📌 Menu:", reply_markup=main_menu_kb())

@bot.message_handler(commands=["help"])
def cmd_help(message):
    upsert_user(message.from_user)
    bot.send_message(
        message.chat.id,
        "📖 <b>Hướng dẫn</b>\n"
        "• /ping - test bot\n"
        "• /myid - xem ID\n"
        "• /info - thông tin tài khoản\n"
        "• /menu - mở menu\n"
        "\n⭐ Premium: dùng không giới hạn."
    )

@bot.message_handler(commands=["ping"])
def cmd_ping(message):
    upsert_user(message.from_user)
    if not allow(message.from_user.id):
        bot.reply_to(message, deny_msg())
        return
    bot.reply_to(message, "pong ✅")

@bot.message_handler(commands=["myid"])
def cmd_myid(message):
    upsert_user(message.from_user)
    bot.reply_to(message, f"🆔 ID của bạn: <code>{message.from_user.id}</code>")

@bot.message_handler(commands=["info"])
def cmd_info(message):
    upsert_user(message.from_user)
    uid = message.from_user.id
    prem = "✅ Premium" if is_premium(uid) else "🆓 Free"
    bot.send_message(message.chat.id, f"👤 <b>Tài khoản</b>\n• ID: <code>{uid}</code>\n• Gói: {prem}")

# ---------- Buttons ----------
@bot.message_handler(func=lambda m: m.text == "ℹ️ Help")
def btn_help(m): cmd_help(m)

@bot.message_handler(func=lambda m: m.text == "📊 Tools")
def btn_tools(message):
    upsert_user(message.from_user)
    if not allow(message.from_user.id):
        bot.reply_to(message, deny_msg())
        return
    bot.send_message(
        message.chat.id,
        "🧰 <b>Tools</b>\n"
        "• /ping\n"
        "• /info\n"
        "• (sắp có thêm tool mới)\n"
    )

@bot.message_handler(func=lambda m: m.text == "👤 Account")
def btn_account(message):
    cmd_info(message)

@bot.message_handler(func=lambda m: m.text == "⭐ Premium")
def btn_premium(message):
    upsert_user(message.from_user)
    uid = message.from_user.id
    if is_premium(uid):
        bot.send_message(message.chat.id, "⭐ Bạn đang là <b>Premium</b> rồi ✅")
    else:
        bot.send_message(
            message.chat.id,
            "⭐ <b>Premium</b>\n"
            "• Không giới hạn lượt dùng\n"
            "• Ưu tiên tool\n\n"
            "Liên hệ admin để kích hoạt."
        )

# ---------- Admin ----------
def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

@bot.message_handler(commands=["admin"])
def cmd_admin(message):
    upsert_user(message.from_user)
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Bạn không có quyền admin.")
        return
    bot.send_message(message.chat.id, "🛠 Admin panel", reply_markup=admin_menu_kb())

@bot.message_handler(func=lambda m: m.text == "⬅️ Back")
def btn_back(message):
    bot.send_message(message.chat.id, "📌 Menu:", reply_markup=main_menu_kb())

@bot.message_handler(func=lambda m: m.text == "📈 Stats")
def btn_stats(message):
    upsert_user(message.from_user)
    if not is_admin(message.from_user.id):
        return
    total, prem = stats()
    bot.send_message(message.chat.id, f"📈 <b>Stats</b>\n• Users: <b>{total}</b>\n• Premium: <b>{prem}</b>")

# Premium set flow
premium_set_state = {}  # admin_id -> waiting_user_id

@bot.message_handler(func=lambda m: m.text == "⭐ Premium Set")
def btn_premium_set(message):
    upsert_user(message.from_user)
    if not is_admin(message.from_user.id):
        return
    premium_set_state[message.from_user.id] = True
    bot.send_message(message.chat.id, "Gửi ID user để bật/tắt Premium.\nVí dụ: <code>123456789</code>")

@bot.message_handler(func=lambda m: premium_set_state.get(m.from_user.id) and m.text and m.text.strip().isdigit())
def admin_set_premium(message):
    if not is_admin(message.from_user.id):
        return
    uid = int(message.text.strip())
    # toggle
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    if not cur.fetchone():
        bot.reply_to(message, "User chưa từng /start bot nên chưa có trong DB.")
        premium_set_state.pop(message.from_user.id, None)
        return
    new_val = not is_premium(uid)
    set_premium(uid, new_val)
    premium_set_state.pop(message.from_user.id, None)
    bot.reply_to(message, f"✅ Đã {'BẬT' if new_val else 'TẮT'} Premium cho <code>{uid}</code>")

# Broadcast flow (simple)
broadcast_state = {}  # admin_id -> True

@bot.message_handler(func=lambda m: m.text == "📣 Broadcast")
def btn_broadcast(message):
    upsert_user(message.from_user)
    if not is_admin(message.from_user.id):
        return
    broadcast_state[message.from_user.id] = True
    bot.send_message(message.chat.id, "Gửi nội dung để broadcast cho tất cả user.")

@bot.message_handler(func=lambda m: broadcast_state.get(m.from_user.id) and m.text)
def admin_broadcast(message):
    if not is_admin(message.from_user.id):
        return
    text = message.text
    broadcast_state.pop(message.from_user.id, None)

    cur.execute("SELECT user_id FROM users")
    ids = [r[0] for r in cur.fetchall()]
    sent = 0
    for uid in ids:
        try:
            bot.send_message(uid, f"📣 <b>Thông báo</b>\n{text}")
            sent += 1
        except Exception:
            pass
    bot.reply_to(message, f"✅ Đã gửi cho {sent}/{len(ids)} user.")

print("Bot is running...")
bot.infinity_polling(skip_pending=True)
