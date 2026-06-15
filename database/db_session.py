# database/db_session.py
import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(override=False)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Не заданы SUPABASE_URL или SUPABASE_KEY в переменных окружения!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Через logging (а не print), чтобы строка точно попала в логи хостинга.
logging.warning(f"DB CONNECT: Supabase REST -> {SUPABASE_URL}")
print(f"✅ Подключено к Supabase через REST API: {SUPABASE_URL}", flush=True)
