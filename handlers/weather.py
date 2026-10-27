"""Hava durumu — .hava <şehir> (varsayılan: Gaziantep)"""
import json, urllib.request, urllib.parse
from pyrogram import Client, filters
from utils.security import rate_limit
from utils.helpers import respond


@rate_limit(3)
async def weather_handler(client: Client, message):
    city = " ".join(message.command[1:]).strip() or "Gaziantep"
    try:
        await respond(client, message, f"🌤 {city} için bakılıyor...")
    except: pass
    try:
        url = "https://wttr.in/" + urllib.parse.quote(city) + "?format=j1"
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read().decode())
        c = data["current_condition"][0]
        desc = (c.get("lang_tr") or c.get("weatherDesc") or [{}])[0].get("value", "")
        txt = (f"🌤 **{city}**\n\n"
               f"{desc}\n"
               f"🌡 Sıcaklık: `{c['temp_C']}°C` (hissedilen {c['FeelsLikeC']}°C)\n"
               f"💧 Nem: `{c['humidity']}%`\n"
               f"🌬 Rüzgar: `{c['windspeedKmph']} km/s`")
        await respond(client, message, txt)
    except Exception as e:
        print(f"hava hata: {e}", flush=True)
        try:
            await respond(client, message, "hava durumu alınamadı — şehir adını kontrol et")
        except: pass


def register_handlers(app: Client):
    from pyrogram.handlers import MessageHandler
    app.add_handler(MessageHandler(weather_handler, filters.command("hava", prefixes=".") & (filters.me | filters.outgoing)))
