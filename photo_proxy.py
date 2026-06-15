# photo_proxy.py — запускается вместе с ботом, проксирует фото из Telegram
import os
import asyncio
from aiohttp import web, ClientSession

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN") or os.getenv("API_TOKEN", "")
PROXY_PORT = int(os.getenv("PROXY_PORT", "8080"))

# Простой кэш чтобы не дёргать Telegram лишний раз
_url_cache = {}

async def handle_photo(request):
    file_id = request.query.get("file_id", "")
    if not file_id:
        return web.Response(status=400, text="file_id required")

    # CORS — разрешаем запросы с GitHub Pages и любого домена
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
    }

    if request.method == "OPTIONS":
        return web.Response(headers=headers)

    # Берём из кэша если уже запрашивали
    if file_id in _url_cache:
        file_url = _url_cache[file_id]
    else:
        async with ClientSession() as session:
            async with session.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
                params={"file_id": file_id}
            ) as r:
                data = await r.json()
                if not data.get("ok"):
                    return web.Response(status=404, text="File not found", headers=headers)
                file_path = data["result"]["file_path"]
                file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                _url_cache[file_id] = file_url

    # Скачиваем файл и отдаём клиенту
    async with ClientSession() as session:
        async with session.get(file_url) as r:
            content = await r.read()
            content_type = r.headers.get("Content-Type", "image/jpeg")
            return web.Response(
                body=content,
                content_type=content_type,
                headers=headers
            )

async def handle_healthcheck(request):
    return web.Response(text="ok")

def create_proxy_app():
    app = web.Application()
    app.router.add_get("/photo", handle_photo)
    app.router.add_options("/photo", handle_photo)
    app.router.add_get("/health", handle_healthcheck)
    return app

async def start_proxy():
    app = create_proxy_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PROXY_PORT)
    await site.start()
    print(f"📸 Photo proxy запущен на порту {PROXY_PORT}")
    return runner
