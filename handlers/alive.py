from pyrogram import Client, filters
from utils.helpers import ALIVE_MSGS, get_uptime, respond
from utils.security import rate_limit
from utils.fonts import smalls

_last_alive = None

@rate_limit(3)
async def log2alfa_handler(client: Client, message):
    global _last_alive
    import random
    try:
        pool = [m for m in ALIVE_MSGS if m != _last_alive] or ALIVE_MSGS
        choice = random.choice(pool)
        _last_alive = choice
        text = f"**{smalls(choice)}**\n\n{smalls('uptime')}: `{get_uptime()}`"
        if not await respond(client, message, text):
            await respond(client, message, f"{smalls('log2alfa user bot aktif')} — {get_uptime()}")
    except Exception as e:
        print(f"log2alfa hata: {e}", flush=True)

@rate_limit(1)
async def ping_handler(client: Client, message):
    print(f"🏓 PING tetiklendi: {repr((message.text or '')[:50])} from={getattr(message.from_user,'id',0)} out={getattr(message,'outgoing',False)}", flush=True)
    import time
    s = time.time()
    ms = int((time.time() - s) * 1000)
    durum = "iyi" if ms < 150 else "normal" if ms < 400 else "yoğun"
    try:
        res = await respond(client, message, f"**{smalls('pong')}** ✓\n{ms}ms • {smalls(durum)}\n{smalls('userbot aktif')} — {get_uptime()}")
        print(f"🏓 PING respond sonucu: {res}", flush=True)
    except Exception as e:
        print(f"ping hata: {e}", flush=True)
        import traceback; traceback.print_exc()

def register_handlers(app: Client):
    from pyrogram.handlers import MessageHandler
    # SADECE giriş yapan hesabın kendi mesajları — başkası yazınca algılamaz
    app.add_handler(MessageHandler(log2alfa_handler, filters.command(["log2alfa","alfa","log2","alive"], prefixes=".") & (filters.me | filters.outgoing)))
    app.add_handler(MessageHandler(ping_handler, filters.command("ping", prefixes=".") & (filters.me | filters.outgoing)))
