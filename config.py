import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("FORM_BOT_TOKEN")
ADMIN_ID       = int(os.getenv("ADMIN_CHAT_ID", "0"))
SHEET_ID       = os.getenv("GOOGLE_SHEET_ID", "")

# Conversation states
ASK_LANG, ASK_NAME, ASK_PHONE, ASK_REGION, ASK_CATEGORY, ASK_DOCTOR, ASK_QUESTION = range(7)
