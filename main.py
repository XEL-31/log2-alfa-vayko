"""
Log2 Alfa Userbot - Ana Çalıştırıcı
Bot Controller (yönetim paneli) + Userbot'ları aynı anda çalıştırır
Profesyonel, ban-korumalı, Railway uyumlu
"""
import asyncio
import os
import sys
from pyrogram import Client, idle
from dotenv import load_dotenv

load_dotenv()

import config
import database

# Global bot client
bot_client = None

async def start_bot_controller():
    """Telegram Bot (yönetim paneli) başlat"""
    if not config.BOT_TOKEN:
        print("❌ BOT_TOKEN yok! .env dosyasına BOT_TOKEN ekle")
        print("BotFather -> @BotFather -> /newbot -> token al")
        return None

    # API_ID/HASH bot için de gerekli ama login flow'da kullanıcıdan da alınabilir
    # Eğer .env'de yoksa dummy kullan ama login flow için gerekli, o yüzden geçici değerler
    api_id = config.API_ID if config.API_ID != 0 else 12345
    api_hash = config.API_HASH if config.API_HASH else "0123456789abcdef0123456789abcdef"

    # Gerçek API_ID/HASH yoksa bile bot çalışsın, çünkü kullanıcı login sırasında verecek
    # Ama Pyrogram için geçerli API_ID/HASH lazım, bu yüzden .env'de mutlaka olmalı uyarısı verdik
    # Yine de dummy ile başlatmayı deneme, hata verecek -> burada validate
    if config.API_ID == 0 or not config.API_HASH:
        print("⚠️  UYARI: API_ID/API_HASH .env'de eksik. Bot çalışmayabilir.")
        print("my.telegram.org'dan al ve .env'e ekle")
        # Dummy ile devam etme, hata verir - bu yüzden çık
        # Ama kullanıcı sadece botu test etmek istiyorsa diye yine de dene, hata verirse logla
        # Burada gerçek değerleri zorunlu kılıyoruz
        if api_id == 12345:
            print("❌ Bot başlatılamadı, API_ID/HASH zorunlu. Lütfen .env'i doldur.")
            return None

    bot = Client(
        name="log2alfa_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workdir=config.WORKDIR,
        sleep_threshold=60
    )

    import bot_controller
    bot_controller.bot_app = bot
    bot_controller.register_bot_handlers(bot)

    await bot.start()
    me = await bot.get_me()
    print(f"🤖 Bot Controller aktif: @{me.username} (ID: {me.id})")
    print(f"🔗 https://t.me/{me.username} -> /start dene")

    # Bot profilini otomatik güncelle (vayko edition - bir kere)
    try:
        await bot.set_my_short_description("◼ LOG2 ALFA — vayko edition | Hızlı, güvenli, ban korumalı userbot. .alfa ile başla.")
        await bot.set_my_description("LOG2 ALFA\nvayko edition\n\nTelegram hesabın için kişisel userbot.\n• .alfa → durum\n• .ping → hız\n• /start → panel\n\nGeliştirici: @vaykoo")
        print("✅ Bot açıklama güncellendi (vayko)")
    except Exception as e:
        print(f"bot açıklama atlandı: {e}")

    return bot

async def main():
    print("""
    ╔════════════════════════════════════╗
    ║   Log2 Alfa Userbot v2.0 - Pro       ║
    ║   Railway + Pyrogram + TGCrypto    ║
    ╚════════════════════════════════════╝
    """)

    # DB init
    os.makedirs(config.WORKDIR, exist_ok=True)
    await database.init_db()
    print("✅ Veritabanı hazır")

    # tek seferlik: tüm session + log kanalları sıfırla (herkes baştan girsin)
    _rv = (os.getenv("RESET_ALL") or "").strip().strip('"').strip("'").lower()
    print(f"RESET_ALL env={_rv!r} DB={database.DB_PATH}", flush=True)
    if _rv in ("1", "true", "yes", "evet"):
        try:
            import aiosqlite
            # durdur aktif userbotlar yok henüz — sadece DB
            async with aiosqlite.connect(database.DB_PATH) as db:
                async with db.execute("SELECT owner_id FROM sessions") as cur:
                    rows = await cur.fetchall()
                print(f"RESET silinecek session: {rows}", flush=True)
                await db.execute("DELETE FROM sessions")
                await db.execute("DELETE FROM settings WHERE key LIKE 'log_channel%'")
                await db.commit()
                async with db.execute("SELECT COUNT(*) FROM sessions") as cur:
                    left = (await cur.fetchone())[0]
            print(f"⚠ RESET_ALL → session+log SİLİNDİ (kalan={left}) — herkes bot'tan /start ile girsin", flush=True)
            # SESSION_STRING ile otomatik geri yüklemeyi de engelle bu tur
            config.SESSION_STRING = ""
        except Exception as e:
            import traceback
            print(f"RESET_ALL hata: {e}\n{traceback.format_exc()}", flush=True)

    # Config validate
    config.validate_config()

    # SESSION_STRING env'den geldiyse direkt DB'ye kaydet (ilk kurulum) — kalıcı volume için
    if config.SESSION_STRING:
        target_owner = config.OWNER_ID
        # OWNER_ID 0 ise session'dan çıkar
        if target_owner == 0:
            try:
                from pyrogram import Client
                tmp = Client(name="tmp_session_probe", api_id=config.API_ID, api_hash=config.API_HASH, session_string=config.SESSION_STRING, workdir=config.WORKDIR, in_memory=True)
                await tmp.connect()
                me = await tmp.get_me()
                target_owner = me.id
                await tmp.disconnect()
                print(f"📥 SESSION_STRING için owner tespit edildi: {target_owner} (@{me.username})")
            except Exception as e:
                print(f"⚠️ SESSION_STRING owner tespit edilemedi: {e} — OWNER_ID ayarla")
                target_owner = 0
        if target_owner != 0:
            existing = await database.get_session(target_owner)
            if not existing:
                print(f"📥 SESSION_STRING bulundu, Owner {target_owner} için kaydediliyor...")
                await database.save_session(target_owner, config.SESSION_STRING, config.API_ID, config.API_HASH, phone="")
                print("✅ Session DB'ye kaydedildi (volume /data)")
            else:
                print(f"ℹ️ Zaten kayıtlı session var, env'deki SESSION_STRING atlandı (DB öncelikli)")
        else:
            print("⚠️ SESSION_STRING var ama owner bulunamadı — elle OWNER_ID gir veya /start ile giriş yap")

    # Bot controller başlat
    global bot_client
    bot_client = await start_bot_controller()
    if not bot_client:
        print("❌ Bot Controller başlatılamadı, çıkılıyor...")
        print("İpucu: BOT_TOKEN, API_ID, API_HASH doğru mu? .env örneğine bak: .env.example")
        return

    # Bot ref'i userbot_core'a ver — alın mesaj probe'ı için
    from userbot_core import set_bot_client
    set_bot_client(bot_client)
    print("🔗 Bot ref -> userbot_core (canlı test için)")

    # Destek/Supporta aktif mesajı — quote + smalls (tek isim)
    try:
        from utils.fonts import smalls
        s = smalls("Log2Alfa")
        me = await bot_client.get_me()
        active_msg = (
            f"> ✅ **{s} aktif** ✨ — bot yeniden başlatıldı\n\n"
            f"> • 🤖 bot: `@{me.username}`\n"
            f"> • ⏱ uptime: `hazır`\n"
            f"> • 🔐 mod: `edit-only • ban korumalı`\n"
        )
        for cid in [config.SUPPORT_CHAT_ID, config.LOG_CHANNEL]:
            if cid:
                try:
                    await bot_client.send_message(int(cid) if str(cid).lstrip('-').isdigit() else cid, active_msg, disable_web_page_preview=True)
                    print(f"✅ Aktif mesajı gönderildi: {cid}")
                except Exception as e:
                    print(f"⚠️ aktif mesaj {cid}: {e}")
        if not config.SUPPORT_CHAT_ID and not config.LOG_CHANNEL:
            print("ℹ️ SUPPORT_CHAT_ID / LOG_CHANNEL yok — aktif mesajı atlanıyor (Railway variables'a ekle)")
    except Exception as e:
        print(f"aktif mesaj hatası: {e}")

    # Kayıtlı userbot'ları başlat
    from userbot_core import start_all_saved_userbots, userbot_watchdog
    print("🔄 Kayıtlı userbotlar başlatılıyor...")
    await start_all_saved_userbots()

    from userbot_core import active_userbots
    print(f"✅ {len(active_userbots)} userbot aktif (varsa)")

    # Watchdog — kopan userbotu otomatik yeniden başlatır, kalp atışı loglar
    asyncio.create_task(userbot_watchdog())
    print("🛡 Watchdog aktif (60sn'de bir kontrol, otomatik yeniden başlatma)")

    print("""
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ✨ SİSTEM HAZIR! 
    • Bot'ta /start yaz -> Yönetim paneli
    • Giriş yap -> .log2alfa ile test et
    • Ban koruması aktif (FloodWait, rate-limit)
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """)

    # Sonsuza kadar çalış - idle
    await idle()

    # Kapanış
    print("🛑 Kapatılıyor...")
    for owner_id, app in list(active_userbots.items()):
        try:
            await app.stop()
        except:
            pass
    try:
        await bot_client.stop()
    except:
        pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Durduruldu (CTRL+C)")
    except Exception as e:
        print(f"❌ Fatal hata: {e}")
        import traceback
        traceback.print_exc()
