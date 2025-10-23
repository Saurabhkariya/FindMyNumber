import asyncio
import requests
import os
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("API_KEY")
DB_PATH = "lookup_cache.db"

# ---------- SQLite setup ----------
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
        INSERT OR REPLACE INTO cache
        (number, name, country, carrier, line_type, spam_score, active, last_checked)
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
    cur.execute("SELECT * FROM cache WHERE number=?", (number,))
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
            "last_checked": row[7],
        }
    return None

# ---------- Bot Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send any phone number with country code (e.g., +14155552671).\n"
        "I'll fetch name, spam score, and carrier info."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Use international format (+countrycode number). Cached lookups are faster!"
    )

async def lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text.strip()
    if not number.startswith("+"):
        await update.message.reply_text("⚠️ Please include country code (e.g., +91).")
        return

    cached = get_from_cache(number)
    if cached:
        reply = (
            f"📞 *Cached Result*\n━━━━━━━━━━\n"
            f"👤 *Name:* {cached['name']}\n"
            f"📱 *Number:* {cached['number']}\n"
            f"🌍 *Country:* {cached['country']}\n"
            f"📡 *Carrier:* {cached['carrier']}\n"
            f"🔌 *Line Type:* {cached['line_type']}\n"
            f"🧠 *Spam Score:* {cached['spam_score']}\n"
            f"✅ *Active:* {cached['active']}\n"
            f"🕓 Checked: {cached['last_checked']}"
        )
        await update.message.reply_text(reply, parse_mode="Markdown")
        return

    try:
        base = requests.get(f"https://api.numlookupapi.com/v1/validate/{number}?apikey={API_KEY}").json()
    except Exception:
        await update.message.reply_text("❌ Lookup service unavailable.")
        return
    if not base.get("valid"):
        await update.message.reply_text("❌ Invalid or unrecognized number.")
        return

    # Name lookup
    name = "Unknown"
    try:
        cnam = requests.get(f"https://api.opencnam.com/v3/phone/{number}", timeout=5)
        if cnam.status_code == 200:
            data = cnam.json()
            if "name" in data:
                name = data["name"]
    except Exception:
        pass

    # Spam check
    spam_score = "No data"
    try:
        spam = requests.get(f"https://spamcalls.net/api/check/{number}?format=json", timeout=5)
        if spam.status_code == 200:
            spam_score = spam.json().get("spam_score", "No data")
    except Exception:
        pass

    info = {
        "name": name,
        "number": base["international_format"],
        "country": base["country_name"],
        "carrier": base.get("carrier", "N/A"),
        "line_type": base.get("line_type", "N/A"),
        "spam_score": spam_score,
        "active": base.get("valid", False),
    }
    save_to_cache(number, info)

    reply = (
        f"📞 *Lookup Result*\n━━━━━━━━━━\n"
        f"👤 *Name:* {name}\n"
        f"📱 *Number:* {info['number']}\n"
        f"🌍 *Country:* {info['country']}\n"
        f"📡 *Carrier:* {info['carrier']}\n"
        f"🔌 *Line Type:* {info['line_type']}\n"
        f"🧠 *Spam Score:* {spam_score}\n"
        f"✅ *Active:* {info['active']}"
    )
    await update.message.reply_text(reply, parse_mode="Markdown")

# ---------- Main ----------
async def main():
    init_db()
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lookup))
    print("Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
