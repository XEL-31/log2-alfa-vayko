import asyncio
import time
import os
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired, PhoneNumberInvalid
import config
from utils.helpers import SAVED_MSG_TEXT, get_uptime
import database

# Global userbot instances: owner_id -> Client
active_userbots = {}

# Bot client referansı (alınan mesaj probe'ı için) — main.py kurar
bot_client_ref = None

def set_bot_client(bc):
    global bot_client_ref
    bot_client_ref = bc

# Watchdog kalp atışı sayacı
_watchdog_ticks = 0

async def create_userbot_client(session_string: str, api_id: int = None, api_hash: str = None, owner_id: int = 0) -> Client:
    """Var olan session_string ile userbot client oluştur"""
    # session_string varsa api_id/hash gerekmez ama Pyrogram ister, config'den al
    api_id = api_id or config.API_ID
    api_hash = api_hash or config.API_HASH
    if not api_id or not api_hash:
        raise ValueError("API_ID / API_HASH eksik!")

    workdir = config.WORKDIR
    os.makedirs(workdir, exist_ok=True)

    app = Client(
        name=f"userbot_{owner_id}",
        api_id=api_id,
        api_hash=api_hash,
        session_string=session_string,
        workdir=workdir,
        sleep_threshold=config.FLOOD_SLEEP_THRESHOLD,
        max_concurrent_transmissions=config.MAX_CONCURRENT_TRANSMISSIONS,
        # Ban riskini azalt: no_updates=False ama gerekli
    )

    # Handlerları yükle — Log2 Alfa sade (Asena karmaşası yok)
    from handlers import alive as alive_h
    from handlers import help_menu as help_h
    from handlers import tools as tools_h
    from handlers import weather as weather_h
    from handlers import calculator as calc_h
    from handlers import music as music_h
    from handlers import dm_guard as dm_h
    from handlers import tagall as tagall_h
    from handlers import plugin_cmds as plugin_h
    from handlers import log2alfa_admin as sadmin_h
    from handlers import log2alfa_info as sinfo_h
    from handlers import fetch_asena as fetch_h
    from handlers import log2alfa_extra_pyro as extra_h
    from handlers import log2alfa_notes as notes_h
    from handlers import log2alfa_gban as gban_h

    alive_h.register_handlers(app)
    help_h.register_handlers(app)
    tools_h.register_handlers(app)
    weather_h.register_handlers(app)
    calc_h.register_handlers(app)
    music_h.register_handlers(app)
    dm_h.register_handlers(app)
    tagall_h.register_handlers(app)
    plugin_h.register_handlers(app)
    sadmin_h.register_handlers(app)
    sinfo_h.register_handlers(app)
    fetch_h.register_handlers(app)
    extra_h.register_handlers(app)
    notes_h.register_handlers(app)     # .kaydet / .not / .notlar / .notsil / #not
    gban_h.register_handlers(app)      # .gban / .gmute / .ungban / .ungmute + uygulama
    # Custom plugins (başkalarının .py)
    try:
        from utils.plugin_loader import load_all_plugins, start_plugin_watcher
        ok, fail, errs = load_all_plugins(app)
        if ok or fail:
            print(f"→ custom pluginler: {ok} ok, {fail} fail", flush=True)
        # Yeni eklenen pluginleri otomatik yükle (restart gerekmesin)
        try:
            start_plugin_watcher(app)
        except Exception as e:
            print(f"watcher başlatma hatası: {e}", flush=True)
    except Exception as e:
        print(f"custom plugin load hatası: {e}", flush=True)
    # Debug — her mesajı logla (tanılama)
    try:
        from handlers import debug as debug_h
        debug_h.register_handlers(app)
        print("Debug handler yüklendi", flush=True)
    except Exception as e:
        print(f"Debug yükleme hatası: {e}", flush=True)
    return app

async def start_userbot_for_owner(owner_id: int, skip_channel: bool = False):
    """DB'den session alıp userbotu başlat (skip_channel: toplu başlatmada kanal sonraya kalır)"""
    if owner_id in active_userbots:
        try:
            # zaten çalışıyor mu kontrol
            client = active_userbots[owner_id]
            if client.is_connected:
                return client
        except:
            pass
        # temizle
        active_userbots.pop(owner_id, None)

    data = await database.get_session(owner_id)
    if not data:
        print(f"Session bulunamadı owner {owner_id}")
        return None

    session_string = data["session_string"]
    api_id = data["api_id"] or config.API_ID
    api_hash = data["api_hash"] or config.API_HASH

    app = await create_userbot_client(session_string, api_id, api_hash, owner_id)

    try:
        await app.start()
        me = await app.get_me()
        print(f"✅ Log2 Alfa Userbot başlatıldı: {me.first_name} (@{me.username}) ID:{me.id} Owner:{owner_id}", flush=True)
        print(f"🔔 Userbot HAZIR — .ping / .saat / .al artık yanıt vermeli", flush=True)

        # Kayıtlı mesajlara bilgilendirme — Log2 Alfa
        try:
            from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            from pyrogram import enums
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💻 Destek", url=config.DEV_URL or config.SUPPORT_URL or "https://t.me/")]])
            name = (me.first_name or "Dostum").strip()
            try:
                text = SAVED_MSG_TEXT.format(name=name)
            except:
                text = SAVED_MSG_TEXT
            await app.send_message("me", text, reply_markup=kb, disable_web_page_preview=True, parse_mode=enums.ParseMode.MARKDOWN)
            print("📩 Saved Messages'a bilgilendirme gönderildi", flush=True)
        except Exception as e:
            print(f"Saved Messages gönderilemedi: {e}", flush=True)

        # userbot.bot proxy için current_app set et (pluginlerin borg.send_file çalışsın)
        try:
            from userbot import _set_current_app
            _set_current_app(app)
        except Exception:
            pass

        # ÖNEMLİ: aktif_userbots'a KAYIT KANAL İŞLEMİNDEN ÖNCE OLSUN —
        # diğer hesapların "sahibi bulma" bekleme döngüsü bunu tarar
        active_userbots[owner_id] = app

        # Log kanalı garantisi (Log2 Alfa Log)
        if not skip_channel:
            try:
                await ensure_log_channel(app, owner_id)
            except Exception as e:
                print(f"log kanal hatası: {e}", flush=True)
        return app
    except Exception as e:
        import traceback
        err = str(e)
        if "AUTH_KEY_UNREGISTERED" in err or "401" in err:
            print(f"⚠️ Userbot {owner_id} oturumu geçersiz (AUTH_KEY_UNREGISTERED) — DB'den temizlenmesi önerilir", flush=True)
            # Otomatik temizleme dene
            try:
                await database.delete_session(owner_id)
                print(f"🗑️ Geçersiz oturum {owner_id} DB'den silindi", flush=True)
            except Exception as ce:
                print(f"temizleme hatası {owner_id}: {ce}", flush=True)
        else:
            print(f"Userbot başlatılamadı {owner_id}: {e}", flush=True)
            traceback.print_exc()
        try:
            await app.stop()
        except:
            pass
        return None

async def pause_userbot_for_owner(owner_id: int):
    """Pasif et — sadece durdur, session kalsın (hatırlama)"""
    app = active_userbots.get(owner_id)
    if app:
        try:
            await app.stop()
            print(f"Userbot pasif edildi owner {owner_id}")
        except Exception as e:
            print(f"Pasif hatası: {e}")
        active_userbots.pop(owner_id, None)
    # DB silme — oturum hatırlanır

async def stop_userbot_for_owner(owner_id: int):
    """Çıkış — durdur ve session sil"""
    await pause_userbot_for_owner(owner_id)
    await database.delete_session(owner_id)
    print(f"Session silindi {owner_id}")

# Ana hesap (eski, köklü hesap) — log kanalını OLUŞTURAN ve üye YAPAN hesap olmalı:
# yeni hesapların DM/davet yetkisi kısıtlı (PEER_ID_INVALID)
MAIN_OWNER_UID = int(os.getenv("ADMIN_UID", "0"))

async def start_all_saved_userbots():
    """Bot açılırken kayıtlı tüm userbotları başlat — ana hesap ÖNCE"""
    sessions = await database.get_all_sessions()
    print(f"🔄 DB session sayısı: {len(sessions)} → {[s.get('owner_id') for s in sessions]}", flush=True)
    def _prio(s):
        try:
            return 0 if int(s["owner_id"]) == MAIN_OWNER_UID else 1
        except Exception:
            return 1
    sessions = sorted(sessions, key=_prio)
    # 1) sırayla GİRİŞ (ban riski için delay) — kanal işi ŞU AN YAPILMAZ
    connected = []
    for s in sessions:
        owner_id = s["owner_id"]
        try:
            app = await start_userbot_for_owner(owner_id, skip_channel=True)
            if app:
                connected.append((owner_id, app))
        except Exception as e:
            print(f"Toplu başlatma hatası {owner_id}: {e}")
        await asyncio.sleep(1)  # ban riski için araya delay
    # 2) tümü bağlı → log kanalı PARALEL garantilenir (sahip tespit saniyeler sürer)
    if connected:
        results = await asyncio.gather(
            *[ensure_log_channel(app, oid) for oid, app in connected],
            return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                print(f"log kanal hatası: {r}", flush=True)

async def userbot_watchdog():
    """
    Kalıcı izleme görevi — her 60sn:
    • bağlı userbotu kontrol et, kopmuşsa otomatik yeniden başlat
    • 5 dakikada bir kalp atışı logla (canlılık kanıtı)
    """
    global _watchdog_ticks
    while True:
        await asyncio.sleep(60)
        _watchdog_ticks += 1
        for owner_id, app in list(active_userbots.items()):
            try:
                connected = bool(app.is_connected)
                if not connected:
                    print(f"⚠️ [WATCHDOG] userbot {owner_id} bağlantı koptu — yeniden başlatılıyor...", flush=True)
                    active_userbots.pop(owner_id, None)
                    try:
                        await start_userbot_for_owner(owner_id)
                        print(f"[WATCHDOG] userbot {owner_id} yeniden başlatıldı", flush=True)
                    except Exception as e:
                        print(f"[WATCHDOG] yeniden başlatma hatası {owner_id}: {e}", flush=True)
                elif _watchdog_ticks % 5 == 0:
                    print(f"❤️ [WATCHDOG] userbot {owner_id} bağlı ✓ ({_watchdog_ticks*60}s)", flush=True)
                    try:
                        await _channel_access_retry(owner_id, app)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[WATCHDOG] hata {owner_id}: {e}", flush=True)

# --- LOG KANALI (her userbot hesabına ÖZEL, kalıcı) ---
# owner_id -> channel id
log_channels: dict = {}
_ensure_lock = asyncio.Lock()

def _log_key(owner_id: int) -> str:
    return f"log_channel_{int(owner_id)}"

def _log_ts_key(owner_id: int) -> str:
    return f"log_channel_ts_{int(owner_id)}"

async def _persist_session(app: Client, owner_id: int):
    """Peer cache session_string'e yazılsın — restart'ta get_chat çalışsın"""
    try:
        data = await database.get_session(owner_id)
        if not data:
            return
        ss = await app.export_session_string()
        await database.save_session(
            owner_id, ss,
            data.get("api_id") or 0,
            data.get("api_hash") or "",
            data.get("phone") or "",
        )
    except Exception as e:
        print(f"→ session persist hata ({owner_id}): {e}", flush=True)

async def _channel_access_retry(owner_id: int, app: Client):
    """Watchdog: hesabın kendi log kanalını doğrula (yeni kanal AÇMAZ)"""
    try:
        cid = await database.get_setting(_log_key(owner_id))
        if not cid:
            return
        cid = int(cid)
        log_channels[owner_id] = cid
        try:
            await app.get_chat(cid)
        except Exception:
            pass
    except Exception:
        pass

async def _create_log_channel(app: Client, owner_id: int):
    """Bu hesap için TEK log kanalı — restart'ta tekrar açılmaz"""
    me = None
    try:
        me = await app.get_me()
    except Exception:
        pass
    uname = (getattr(me, "username", None) or str(owner_id)) if me else str(owner_id)
    fname = (getattr(me, "first_name", None) or uname) if me else uname
    title = f"Log2 Alfa Log · {uname}"
    ch = await app.create_channel(title=title)
    log_channels[owner_id] = ch.id
    await database.set_setting(_log_key(owner_id), str(ch.id))
    await database.set_setting(_log_ts_key(owner_id), str(int(time.time())))
    await _persist_session(app, owner_id)
    try:
        await app.send_message(
            ch.id,
            "✦ ʟᴏɢ ᴋᴀɴᴀʟı ʜᴀᴢıʀ\n"
            "━━━━━━━━━━━━━━━━\n"
            f"→ Hesap: {fname}\n"
            f"→ ID: `{owner_id}`\n"
            "→ Bu kanal bu userbota özeldir\n"
            "→ Her giriş/çıkışta yeniden açılmaz\n"
            "━━━━━━━━━━━━━━━━",
        )
    except Exception:
        pass
    print(f"→ Log kanalı OLUŞTURULDU owner={owner_id} ch={ch.id} ({title})", flush=True)
    return ch.id

async def ensure_log_channel(app: Client, owner_id: int):
    """
    Her userbot = kendi log kanalı.
    DB'de varsa KORU. Restart'ta yeni açma.
    Sadece yoksa / CHANNEL_INVALID ise oluştur.
    """
    owner_id = int(owner_id)
    cid_raw = await database.get_setting(_log_key(owner_id))
    cid = int(cid_raw) if cid_raw else None

    # eski global tek kanal → bu owner'a miras (bir kez)
    if not cid:
        try:
            legacy = await database.get_setting("log_channel")
            legacy_owner = await database.get_setting("log_channel_owner")
            if legacy:
                take = False
                if legacy_owner and str(legacy_owner) == str(owner_id):
                    take = True
                elif not legacy_owner and owner_id == MAIN_OWNER_UID:
                    take = True
                if take:
                    # başka owner bu id'yi almış mı?
                    taken = False
                    for s in await database.get_all_sessions():
                        oid = int(s["owner_id"])
                        if oid == owner_id:
                            continue
                        other = await database.get_setting(_log_key(oid))
                        if other and str(other) == str(legacy):
                            taken = True
                            break
                    if not taken:
                        cid = int(legacy)
                        await database.set_setting(_log_key(owner_id), str(cid))
                        ts = await database.get_setting("log_channel_ts") or str(int(time.time()))
                        await database.set_setting(_log_ts_key(owner_id), ts)
                        print(f"→ Log kanalı miras owner={owner_id} ch={cid}", flush=True)
        except Exception as e:
            print(f"→ log miras hata: {e}", flush=True)

    if cid:
        try:
            await app.get_chat(cid)
            log_channels[owner_id] = cid
            print(f"→ Log kanalı OK owner={owner_id} ch={cid}", flush=True)
            return cid
        except Exception as e:
            err = str(e).lower()
            # PEER_ID_INVALID / not known → KORU (session cache)
            if ("peer" in err and "invalid" in err) or "not known yet" in err:
                log_channels[owner_id] = cid
                print(f"→ Log kanalı peer yok — KORUNUYOR owner={owner_id} ch={cid}", flush=True)
                return cid
            # taze kayıt varsa her türlü koru
            try:
                ts = await database.get_setting(_log_ts_key(owner_id))
                if ts and (time.time() - float(ts)) < 86400 * 60:
                    log_channels[owner_id] = cid
                    print(f"→ Log kanalı taze/kayıtlı — KORUNUYOR owner={owner_id} ch={cid}", flush=True)
                    return cid
            except Exception:
                pass
            # sadece gerçekten silinmişse yenile
            if "channel_invalid" in err or "chat not found" in err or "chat_id_invalid" in err:
                print(f"→ Log kanalı GEÇERSİZ owner={owner_id} ch={cid} — yenisi açılacak", flush=True)
                try:
                    await database.set_setting(_log_key(owner_id), "")
                except Exception:
                    pass
                cid = None
            else:
                log_channels[owner_id] = cid
                print(f"→ Log kanalı belirsiz — KORUNUYOR owner={owner_id}: {e}", flush=True)
                return cid

    if cid:
        log_channels[owner_id] = cid
        return cid

    async with _ensure_lock:
        again = await database.get_setting(_log_key(owner_id))
        if again:
            log_channels[owner_id] = int(again)
            return int(again)
        try:
            return await _create_log_channel(app, owner_id)
        except Exception as e:
            print(f"→ log kanal oluşturma hatası owner={owner_id}: {e}", flush=True)
            return None

async def send_log(text: str, owner_id: int | None = None):
    """Hesaba özel log kanalına yaz. owner_id yoksa ilk bağlı hesap."""
    targets = [int(owner_id)] if owner_id is not None else list(active_userbots.keys())
    for oid in targets:
        app = active_userbots.get(oid)
        if not app:
            continue
        try:
            if not app.is_connected:
                continue
        except Exception:
            continue
        cid = log_channels.get(oid)
        if not cid:
            try:
                raw = await database.get_setting(_log_key(oid))
                if raw:
                    cid = int(raw)
                    log_channels[oid] = cid
            except Exception:
                pass
        if not cid:
            try:
                cid = await ensure_log_channel(app, oid)
            except Exception:
                continue
        if not cid:
            continue
        try:
            await app.send_message(cid, text)
            return
        except Exception as e:
            err = str(e).lower()
            print(f"→ log gönderim hata owner={oid}: {e}", flush=True)
            if "channel_invalid" in err or "chat not found" in err or "chat_id_invalid" in err:
                try:
                    await database.set_setting(_log_key(oid), "")
                except Exception:
                    pass
                log_channels.pop(oid, None)
            continue

# --- Login Flow için geçici client yönetimi ---
# Telefonla giriş için geçici client'lar: owner_id -> Client (henüz session yokken)
temp_login_clients = {}  # owner_id -> {client, api_id, api_hash, phone, phone_code_hash}

async def initiate_login(api_id: int, api_hash: str, phone: str, owner_id: int):
    """Telefon numarasına kod gönder, temp client oluştur"""
    workdir = config.WORKDIR
    os.makedirs(workdir, exist_ok=True)
    # Geçici client - session olmadan
    client = Client(
        name=f"login_{owner_id}_{phone}",
        api_id=api_id,
        api_hash=api_hash,
        workdir=workdir,
        in_memory=True
    )
    await client.connect()
    try:
        sent = await client.send_code(phone)
        # sakla
        temp_login_clients[owner_id] = {
            "client": client,
            "api_id": api_id,
            "api_hash": api_hash,
            "phone": phone,
            "phone_code_hash": sent.phone_code_hash
        }
        return sent
    except PhoneNumberInvalid:
        await client.disconnect()
        raise ValueError("❌ Telefon numarası geçersiz! Örnek: +9055xxxxxxx")
    except FloodWait as e:
        await client.disconnect()
        raise ValueError(f"⏳ FloodWait: {e.value} saniye beklemelisin!")
    except Exception as e:
        await client.disconnect()
        raise e

async def complete_login(owner_id: int, code: str, password: str = None):
    """Kodu doğrula, gerekirse 2FA, session string üret ve kaydet"""
    data = temp_login_clients.get(owner_id)
    if not data:
        raise ValueError("Oturum bulunamadı. Lütfen baştan giriş yapın.")

    client = data["client"]
    api_id = data["api_id"]
    api_hash = data["api_hash"]
    phone = data["phone"]
    phone_code_hash = data["phone_code_hash"]

    # kodu temizle: boşlukları sil
    code = code.replace(" ", "").strip()

    try:
        # Pyrogram'da sign_in phone_code ile
        await client.sign_in(phone, phone_code_hash, code)
    except SessionPasswordNeeded:
        if not password:
            # 2FA gerekiyor, client'i kapatma bekle
            raise SessionPasswordNeeded("2FA gerekli")
        # 2FA var, password ile dene
        try:
            await client.check_password(password)
        except Exception as e:
            raise ValueError("Şifreniz Yanlış, Tekrar deneyiniz veya baştan giriş yapınız.")
    except PhoneCodeInvalid:
        raise ValueError("Kodunuz Yanlış, Tekrar deneyiniz.")
    except PhoneCodeExpired:
        await client.disconnect()
        temp_login_clients.pop(owner_id, None)
        raise ValueError("Kodun süresi doldu. Yeni kod isteyin.")
    except Exception as e:
        raise e

    # Başarılı - session string üret
    try:
        session_string = await client.export_session_string()
        # DB'ye kaydet
        await database.save_session(owner_id, session_string, api_id, api_hash, phone)
        await client.disconnect()
        temp_login_clients.pop(owner_id, None)
        # Not: userbotu burada başlatma, bot_controller halledecek — hatasız giriş için
        return session_string
    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        temp_login_clients.pop(owner_id, None)
        raise e

async def cancel_login(owner_id: int):
    data = temp_login_clients.pop(owner_id, None)
    if data:
        try:
            await data["client"].disconnect()
        except:
            pass
    # Yarım kalan login dosyalarını temizle
    try:
        import glob, pathlib
        workdir = config.WORKDIR
        for fp in glob.glob(os.path.join(workdir, f"login_{owner_id}_*")):
            try: os.remove(fp)
            except: pass
        for fp in pathlib.Path(workdir).glob(f"login_{owner_id}_*.session*"):
            try: fp.unlink()
            except: pass
    except:
        pass
