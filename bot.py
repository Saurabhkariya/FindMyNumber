import requests
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import os

BOT_TOKEN = os.getenv("8452280131:AAEUaXltKYIkvA_9nWFwA_lfVhscsKjULh0")
API_KEY = os.getenv("num_live_e8fTD4ZOp4CG6TQNKlDolWPJXcfWBeJANwbrdW2j")

def start(update, context):
    update.message.reply_text("👋 Hi! Send me any phone number with country code (e.g., +919876543210)")

def lookup(update, context):
    number = update.message.text.strip()
    if not number.startswith("+"):
        update.message.reply_text("⚠️ Please include the country code, like +91 for India.")
        return

    url = f"https://api.numlookupapi.com/v1/validate/{number}?apikey={API_KEY}"
    r = requests.get(url).json()

    if r.get("valid"):
        info = (
            f"✅ *Number:* {r['international_format']}\n"
            f"🌍 *Country:* {r['country_name']}\n"
            f"📡 *Carrier:* {r.get('carrier', 'N/A')}\n"
            f"📞 *Line type:* {r.get('line_type', 'N/A')}\n"
            f"📅 *Active:* {r.get('valid', False)}"
        )
    else:
        info = "❌ Could not find details for this number."

    update.message.reply_text(info, parse_mode="Markdown")

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, lookup))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()