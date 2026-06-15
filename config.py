import os
from dotenv import load_dotenv

# override=False: переменные, уже заданные в окружении (на хостинге — из панели),
# имеют приоритет над .env-файлом. Так .env не перебьёт настройки сервера.
load_dotenv(override=False)

TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN") or os.getenv("API_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_raw_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _raw_ids.split(",") if x.strip().isdigit()]
