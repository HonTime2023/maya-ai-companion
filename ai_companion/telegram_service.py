import requests
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_message(message, chat_id=None):
    """
    Send a Telegram message using the bot.
    If chat_id is not provided, the default chat ID from .env is used.
    """

    if not BOT_TOKEN:
        print("⚠️ Telegram BOT token not configured.")
        return False

    chat_id = chat_id or DEFAULT_CHAT_ID

    if not chat_id:
        print("⚠️ Telegram chat ID not configured.")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            return True
        else:
            print("Telegram API error:", response.text)
            return False

    except Exception as e:
        print("Telegram connection error:", e)
        return False
