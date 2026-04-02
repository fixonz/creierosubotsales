import os
from dotenv import load_dotenv

load_dotenv()

# Admin Layer (A1)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

# Confirmation Layer (2C2)
TATUM_API_KEY = os.getenv("TATUM_API_KEY")
LTC_ADDRESSES = [addr.strip() for addr in os.getenv("LTC_ADDRESSES", "").split(",") if addr.strip()]
DEPOSIT_TIMEOUT_MINUTES = int(os.getenv("DEPOSIT_TIMEOUT_MINUTES", 30))
# Database
DB_PATH = "bot_database.sqlite"
