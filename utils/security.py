"""
Güvenlik ve Ban Koruması - Log2 Alfa Userbot

Telegram'ın userbot'ları spam olarak algılamaması için alınan önlemler:
1. FloodWait tam otomatik handle (e.value kadar uyur)
2. Sadece filters.me -> sadece kendi hesabın komut çalıştırır
3. Mesajları silmez, sadece kendi mesajını düzenler (edit)
4. Toplu işlemlerde delay (örneğin daktilo, tag)
5. Rate limit: aynı komut 2 saniyede bir
"""
import asyncio
import time
from functools import wraps
from pyrogram.errors import FloodWait

# Rate limit: (user_id, func) -> son komut zamanı — komut bazlı
_last_command = {}

def rate_limit(seconds=2):
    def decorator(func):
        @wraps(func)
        async def wrapper(client, message):
            uid = message.from_user.id if message.from_user else 0
            key = (uid, func.__name__)
            now = time.time()
            last = _last_command.get(key, 0)
            if now - last < seconds:
                # çok sık — kısa uyarı
                try:
                    await message.edit_text("biraz hızlısın — 1 sn bekle")
                except Exception:
                    try: await message.reply_text("biraz hızlısın — 1 sn bekle")
                    except Exception: pass
                return
            _last_command[key] = now
            try:
                return await func(client, message)
            except FloodWait as e:
                print(f"⏳ FloodWait: {e.value} saniye bekleniyor...")
                await asyncio.sleep(e.value)
                try:
                    return await func(client, message)
                except Exception as ex2:
                    print(f"FloodWait sonrası hata: {ex2}")
            except Exception as e:
                print(f"Handler hatası {func.__name__}: {e}")
        return wrapper
    return decorator

# İnsan gibi yazma efekti için delay
async def human_delay(min_ms=80, max_ms=180):
    import random
    await asyncio.sleep(random.uniform(min_ms/1000, max_ms/1000))

BAN_WARNING = """
⚠️ **Güvenlik Uyarısı - Ban Riskini Azalt**

Telegram, yeni hesapları veya spam davranışlarını otomatik banlayabilir. Lütfen:

✓ İlk 24 saat sadece 2-3 komut test et
✓ Gruplarda art arda komut gönderme
✓ .tagall gibi toplu etiketlemeyi günde 1-2 kez kullan
✓ Hesabın 2FA (iki adımlı doğrulama) açık tut
✓ Userbot'u 7/24 açık bırakma, arada durdur

Bu bot FloodWait'i otomatik bekler ve sadece kendi mesajlarını düzenler, bu yüzden normal kullanımda güvenlidir.
"""
