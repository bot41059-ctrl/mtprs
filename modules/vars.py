import os

API_ID    = os.environ.get("API_ID", "29719806")
API_HASH  = os.environ.get("API_HASH", "c8e87805739aa77bd5bd4076148a9a66")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "") 

WEBHOOK = True
PORT = int(os.environ.get("PORT", 8870))

# Admin & Owner Telegram IDs (can provide multiple separated by spaces or commas)
OWNER_ID = int(os.environ.get("OWNER_ID", "0")) if os.environ.get("OWNER_ID", "0").isdigit() else 0
raw_admins = os.environ.get("ADMINS", "").replace(",", " ").split()
ADMINS = [int(x) for x in raw_admins if x.isdigit()]
if OWNER_ID and OWNER_ID not in ADMINS:
    ADMINS.append(OWNER_ID)

# Membership limits
FREE_LIMIT = int(os.environ.get("FREE_LIMIT", "5"))

# Cloudflare KV REST API Credentials (Optional - Falls back to local SQLite if not configured)
CF_ACCOUNT_ID   = os.environ.get("CF_ACCOUNT_ID", "").strip()
CF_NAMESPACE_ID = os.environ.get("CF_NAMESPACE_ID", "").strip()
CF_API_TOKEN    = os.environ.get("CF_API_TOKEN", "").strip()

# Cloudflare Custom Worker URL (Optional alternative)
CF_WORKER_URL   = os.environ.get("CF_WORKER_URL", "https://cp-extractor-bot.mypresonal65.workers.dev").strip().rstrip("/")
CF_WORKER_TOKEN = os.environ.get("CF_WORKER_TOKEN", "my_cp_admin_secret_2026").strip()


def is_admin(user_id: int) -> bool:
    """Checks whether the given Telegram user ID is an admin or owner."""
    if not user_id:
        return False
    return (user_id in ADMINS) or (OWNER_ID and user_id == OWNER_ID)
