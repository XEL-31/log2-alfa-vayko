"""Asena Plugin Kanalından Toplu Çekme — .fetchasena / .asenacek
Tüm .py dosyalarını https://t.me/asenaplugin kanalından çeker, /data/plugins'a kaydeder
ve anında yükler. Normal kullanıcılar da tetikleyebilir (incoming dahil).
"""
import os
import asyncio
import time
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.fonts import smalls
from utils.helpers import respond

# Kanal bilgileri
CHANNEL = "asenaplugin"  # username, id -1001258161760
PLUGIN_DIR_FALLBACK = "/data/plugins"

def _plugin_dir():
    # plugin_loader ile aynı mantık
    env = os.getenv("PLUGIN_DIR")
    if env:
        return env
    if os.path.isdir("/data"):
        return "/data/plugins"
    return os.path.join(os.getcwd(), "plugins")

async def _fetch_all(client: Client, message: Message, limit: int = 0):
    """limit=0 tümü, yoksa ilk N — kanala katılıp tüm geçmişi tara"""
    dir_path = _plugin_dir()
    os.makedirs(dir_path, exist_ok=True)
    # Kanala katılmayı dene (public kanalda history için)
    try:
        await client.join_chat(CHANNEL)
        await asyncio.sleep(1)
    except:
        pass
    try:
        chat = await client.get_chat(CHANNEL)
    except Exception as e:
        await respond(client, message, smalls(f"kanal bulunamadı: {e}"))
        return
    await respond(client, message, smalls(f"⏳ {chat.title} taranıyor..."))
    count = 0
    saved = 0
    skipped = 0
    failed = 0
    start = time.time()
    # Mesaj geçmişini tara — 0 ise hepsi (1000 limit, tekrar .fetchasena ile devam)
    total_to_scan = limit if limit and limit > 0 else 1000
    scanned = 0
    last_edit = 0
    try:
        async for msg in client.get_chat_history(chat.id, limit=total_to_scan):
            scanned += 1
            if not msg.document:
                continue
            fname = msg.document.file_name or ""
            if not fname.endswith(".py"):
                continue
            count += 1
            # Dosya adını sanitize et (Türkçe karakter, boşluk)
            try:
                from utils.plugin_loader import _sanitize
                safe_fname = _sanitize(fname[:-3]) + ".py" if fname.endswith(".py") else _sanitize(fname) + ".py"
            except:
                import re
                safe_fname = re.sub(r"[^a-zA-Z0-9_\-]", "_", fname)
                if not safe_fname.endswith(".py"):
                    safe_fname += ".py"
            dest = os.path.join(dir_path, safe_fname)
            # Aynı dosya varsa atla
            if os.path.exists(dest):
                try:
                    if os.path.getsize(dest) > 10:
                        skipped += 1
                        continue
                except:
                    pass
            # İndir (orijinal dosya adına rağmen safe isme kaydet)
            try:
                tmp_dest = dest  # direkt safe isme indir
                await client.download_media(msg, file_name=tmp_dest)
                # Doğrula
                if os.path.exists(dest) and os.path.getsize(dest) > 10:
                    saved += 1
                    # Anında yüklemeyi dene (diğer userbotlara da)
                    try:
                        from utils.plugin_loader import load_plugin, _sanitize
                        from userbot_core import active_userbots
                        # Kendi app için (sanitize)
                        try:
                            sname = _sanitize(fname[:-3])
                            load_plugin(client, sname)
                        except Exception as e:
                            print(f"fetch yükleme hata {fname}: {e}", flush=True)
                        # Diğerleri (sanitize)
                        try:
                            for oid, other in list(active_userbots.items()):
                                if other is client:
                                    continue
                                try:
                                    if other and getattr(other, "is_connected", False):
                                        try:
                                            from utils.plugin_loader import _sanitize as _sz2
                                            s2 = _sz2(fname[:-3])
                                        except:
                                            import re as _re2
                                            s2 = _re2.sub(r"[^a-zA-Z0-9_\-]", "_", fname[:-3])
                                        load_plugin(other, s2)
                                except:
                                    pass
                        except:
                            pass
                    except Exception as e:
                        print(f"load_plugin import hata: {e}", flush=True)
                else:
                    failed += 1
                    try:
                        if os.path.exists(dest):
                            os.remove(dest)
                    except:
                        pass
            except Exception as e:
                print(f"download hata {fname}: {e}", flush=True)
                failed += 1
            # Ara bilgi
            if time.time() - last_edit > 5 and (saved % 5 == 0):
                last_edit = time.time()
                try:
                    await message.edit_text(smalls(f"⏳ {saved} indirildi, {skipped} atlandı, {count} bulundu..."))
                except:
                    pass
            # Flood koruması
            await asyncio.sleep(0.3)
            if limit and saved >= limit:
                break
        elapsed = int(time.time() - start)
        await respond(client, message, smalls(f"✅ bitti: {saved} indirildi, {skipped} zaten vardı, {failed} hata\n→ taranan: {scanned} mesaj, bulunan .py: {count}\n→ süre: {elapsed}sn\n→ .plist ile gör"))
    except Exception as e:
        import traceback
        traceback.print_exc()
        await respond(client, message, smalls(f"hata: {e}"))

async def fetch_handler(client: Client, message: Message):
    # Komut: .fetchasena [limit]  / .asenacek [limit]
    args = message.text.split()
    limit = 0
    if len(args) > 1:
        try:
            limit = int(args[1])
        except:
            limit = 0
    await _fetch_all(client, message, limit=limit)

# Otomatik çekme — plugins boşsa ilk açılışta otomatik başlat (kullanıcı istemiş)
async def _auto_fetch_if_empty(client: Client):
    await asyncio.sleep(10)  # userbot tam açılsın
    try:
        dir_path = _plugin_dir()
        try:
            py_count = len([p for p in Path(dir_path).glob("*.py") if p.stat().st_size > 10])
        except:
            py_count = 0
        print(f"auto fetch check: py_count={py_count} dir={dir_path}", flush=True)
        if py_count < 80:
            print(f"auto fetch: {py_count} plugin var, 150 hedef — ek çekiliyor", flush=True)
            try:
                from userbot_core import send_log
                await send_log("🔍 Pluginler boş — asenaplugin'den otomatik çekiliyor (150)...")
            except Exception as e:
                print(f"send_log hata: {e}", flush=True)
            try:
                # Kanala katıl (public kanalda history için gerekebilir)
                try:
                    await client.join_chat(CHANNEL)
                    print(f"joined {CHANNEL}", flush=True)
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"join hata (önemli değil): {e}", flush=True)
                chat = await client.get_chat(CHANNEL)
                print(f"chat {chat.title} id={chat.id}", flush=True)
                saved = 0
                scanned = 0
                # Tüm geçmişi tara (1000 limit) — 30 değil, 100+ çek
                async for msg in client.get_chat_history(chat.id, limit=1000):
                    scanned += 1
                    if not msg.document or not msg.document.file_name.endswith(".py"):
                        continue
                    fname = msg.document.file_name
                    try:
                        from utils.plugin_loader import _sanitize
                        safe_fname = _sanitize(fname[:-3]) + ".py"
                    except:
                        import re
                        safe_fname = re.sub(r"[^a-zA-Z0-9_\-]", "_", fname[:-3]) + ".py"
                    dest = os.path.join(dir_path, safe_fname)
                    if os.path.exists(dest) and os.path.getsize(dest) > 10:
                        continue
                    try:
                        print(f"indiriliyor {fname} -> {safe_fname} msg={msg.id}", flush=True)
                        await client.download_media(msg, file_name=dest)
                        if os.path.exists(dest) and os.path.getsize(dest) > 10:
                            saved += 1
                            print(f"indirildi {safe_fname} {os.path.getsize(dest)}b", flush=True)
                            try:
                                from utils.plugin_loader import load_plugin
                                load_plugin(client, safe_fname[:-3])
                                print(f"yüklendi {safe_fname}", flush=True)
                            except Exception as e:
                                print(f"yukleme hata {safe_fname}: {e}", flush=True)
                        else:
                            print(f"indirildi ama bozuk {fname}", flush=True)
                            try: os.remove(dest)
                            except: pass
                    except Exception as e:
                        print(f"download hata {fname}: {e}", flush=True)
                        import traceback; traceback.print_exc()
                    await asyncio.sleep(0.4)
                    if saved >= 150:
                        break
                print(f"auto fetch bitti: {saved} indirildi, taranan {scanned}", flush=True)
                try:
                    from userbot_core import send_log
                    await send_log(f"✅ Otomatik çekme bitti: {saved} plugin indirildi ({scanned} tarandı). .plist ile gör — .fetchasena ile daha fazla")
                except:
                    pass
            except Exception as e:
                print(f"auto fetch hata: {e}", flush=True)
                import traceback; traceback.print_exc()
                try:
                    from userbot_core import send_log
                    await send_log(f"❌ Otomatik çekme hata: {e}")
                except:
                    pass
        else:
            print(f"auto fetch skip: zaten {py_count} plugin var", flush=True)
    except Exception as e:
        print(f"auto fetch if empty hata: {e}", flush=True)
        import traceback; traceback.print_exc()

def register_handlers(app: Client):
    from pyrogram.handlers import MessageHandler
    # Fetch sadece sahibi tetiklesin (güvenlik) — pluginler zaten herkes için çalışacak
    flt_owner = filters.me | filters.outgoing
    app.add_handler(MessageHandler(fetch_handler, filters.command(["fetchasena","asenacek","asenaçek","plugincek"], prefixes=".") & flt_owner))
    # Otomatik çekme task'ı başlat
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(_auto_fetch_if_empty(app))
    except Exception as e:
        print(f"auto fetch task hata: {e}", flush=True)
