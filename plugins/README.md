# Plugin Sistemi

Bu klasör boş bırakılır — pluginler `/data/plugins` (Railway) veya `./plugins` içine kaydedilir.

## Yükleme (userbot)
- Bir .py dosyasına **yanıt** olarak: `.pal`
- Listele: `.plist`  (veya `.plugins`)
- Sil: `.psil <isim>`  (ör: `.psil hello`)
- Dosyayı geri al: `.pget <isim>`

## Yükleme (bot)
- Bot'a özelden .py dosyası gönder (admin) → otomatik yüklenir
- Admin → `» Panel → • Admin → 🔌 Pluginler` → listele / sil butonları

## Plugin Yazımı
Her plugin tek dosya `ad.py`, içinde mutlaka `register_handlers(app)` olmalı:

```python
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler

async def hello_handler(client: Client, message):
    await message.edit_text("merhaba custom plugin ✅")

def register_handlers(app: Client):
    app.add_handler(MessageHandler(
        hello_handler,
        filters.command(["hello"], prefixes=".") & (filters.me | filters.outgoing)
    ))
```

Başkasının pluginini indir → yukarıdaki gibi .pal ile yükle → anında aktif.
Silince restart önerilir (tam temizlik için).
