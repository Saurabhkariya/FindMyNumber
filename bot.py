import requests
import os
import sqlite3
from datetime import datetime
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("API_KEY")

# --- Initialize SQLite Database ---
DB_PATH = "lookup_cache.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            number TEXT PRIMARY KEY,
            name TEXT,
            country TEXT,
            carrier TEXT,
            line_type TEXT,
            spam_score TEXT,
            active TEXT,
            last_checked TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_to_cache(number, info):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO cache (number, name, country, carrier, line_type, spam_score, active, last_checked)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        number,
        info.get("name"),
        info.get("country"),
        info.get("carrier"),
        info.get("line_type"),
        info.get("spam_score"),
        str(info.get("active")),
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

def get_from_cache(number):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM cache WHERE number = ?", (number,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "number": row[0],
            "name": row[1],
            "country": row[2],
            "carrier": row[3],
            "line_type": row[4],
            "spam_score": row[5],
            "active": row[6],
            "last_checked": row[7]
        }
    return None

# --- Core Bot Functions ---
def start(update, context):
    update.message.reply_text(
        "👋 Hi! Send me any phone number with country code (e.g., +919876543210)\n"
        "I'll find name, spam score, and network details.\n"
        "⚡ Cached results for faster responses!"
    )

def lookup(update, context):
    number = update.message.text.strip()
    if not number.startswith("+"):
        update.message.reply_text("⚠️ Please include the country code, like +91.")
        return

    # Check cache first
    cached = get_from_cache(number)
    if cached:
        info = (
            f"📞 *Phone Lookup (Cached)*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 *Name:* {cached['name']}\n"
            f"📱 *Number:* {cached['number']}\n"
            f"🌍 *Country:* {cached['country']}\n"
            f"📡 *Carrier:* {cached['carrier']}\n"
            f"🔌 *Line Type:* {cached['line_type']}\n"
            f"🧠 *Spam Score:* {cached['spam_score']}\n"
            f"✅ *Active:* {cached['active']}\n"
            f"🕓 *Checked:* {cached['last_checked']}"
        )
        update.message.reply_text(info, parse_mode="Markdown")
        return

    # Otherwise fetch fresh info
    try:
        r = requests.get(f"https://api.numlookupapi.com/v1/validate/{number}?apikey={API_KEY}")
        base = r.json()
    except Exception:
        update.message.reply_text("❌ Error contacting lookup service.")
        return

    if not base.get("valid"):
        update.message.reply_text("❌ Invalid or unrecognized number.")
        return

    # Get name
    name = "Unknown"
    try:
        cnam_resp = requests.get(f"https://api.opencnam.com/v3/phone/{number}", timeout=5)
        if cnam_resp.status_code == 200:
            data = cnam_resp.json()
            if "name" in data:
                name = data["name"]
    except Exception:
        pass

    # Get spam info
    spam_score = "No data"
    try:
        spam_resp = requests.get(f"https://spamcalls.net/api/check/{number}?format=json", timeout=5)
        if spam_resp.status_code == 200:
            sdata = spam_resp.json()
            spam_score = sdata.get("spam_score", "No data")
    except Exception:
        pass

    # Compile info
    info_dict = {
        "name": name,
        "number": base["international_format"],
        "country": base["country_name"],
        "carrier": base.get("carrier", "N/A"),
        "line_type": base.get("line_type", "N/A"),
        "spam_score": spam_score,
        "active": base.get("valid", False)
    }

    # Save to cache
    save_to_cache(number, info_dict)

    # Format reply
    info = (
        f"📞 *Phone Lookup Result*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 *Name:* {name}\n"
        f"📱 *Number:* {info_dict['number']}\n"
        f"🌍 *Country:* {info_dict['country']}\n"
        f"📡 *Carrier:* {info_dict['carrier']}\n"
        f"🔌 *Line Type:* {info_dict['line_type']}\n"
        f"🧠 *Spam Score:* {spam_score}\n"
        f"✅ *Active:* {info_dict['active']}"
    )

    update.message.reply_text(info, parse_mode="Markdown")

def help_command(update, context):
    update.message.reply_text(
        "ℹ️ Just send any phone number in full international format (like +12025550123).\n"
        "Cached results will reply faster!"
    )

def main():
    init_db()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, lookup))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()