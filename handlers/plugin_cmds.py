"""Userbot plugin yönetimi — .pal / .psil / .plist / .pget
.pal  → .py dosyasına yanıtla → yükle (her plugin tipi, Asena dahil)
.psil → isimle veya dosyaya yanıtla → sil
  .psil <isim>  veya  .psil (dosyaya yanıt)
.plist → plugin listesi
.pget <isim> → dosyayı gönder
"""
import os
import hashlib
from pyrogram import Client, filters
from utils.security import rate_limit
from utils.helpers import respond
from utils.fonts import smalls
from utils.plugin_loader import PLUGIN_DIR, list_plugins, delete_plugin, get_plugin_code, get_plugin_path
from utils.plugin_loader import install_from_temp

def _is_group(chat) -> bool:
    ct = getattr(chat, "type", None)
    if ct is None:
        return False
    s = str(getattr(ct, "value", None) or getattr(ct, "name", None) or ct).lower()
    return "group" in s

def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    if n < 1024*1024:
        return f"{n/1024:.1f}KB"
    return f"{n/1024/1024:.1f}MB"

def _hash_file(path: str) -> str:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:12]
    except:
        return ""

# ── .plist ──
@rate_limit(3)
async def plist_handler(client: Client, message):
    plugins = list_plugins()
    if not plugins:
        await respond(client, message, smalls("→ plugin yok — .pal ile yükle"))
        return
    lines = [smalls("✦ plugin listesi"), smalls("━━━━━━━━━━━━━━━━")]
    for p in plugins:
        lines.append(smalls(f"• {p['name']} ({_fmt_size(p['size'])})"))
    lines.append(smalls("━━━━━━━━━━━━━━━━"))
    lines.append(smalls(f"→ toplam: {len(plugins)}"))
    await respond(client, message, "\n".join(lines))

# ── .pal (plugin al) — duplicate engelli ──
@rate_limit(3)
async def pal_handler(client: Client, message):
    reply = message.reply_to_message
    if not reply or not reply.document:
        await respond(client, message, smalls("→ bir .py dosyasına yanıt ver: .pal"))
        return
    doc = reply.document
    fname = doc.file_name or "plugin.py"
    if not fname.endswith(".py"):
        await respond(client, message, smalls("→ sadece .py dosyası"))
        return
    if doc.file_size and doc.file_size > 400 * 1024:
        await respond(client, message, smalls("→ dosya çok büyük (400KB limit)"))
        return
    try:
        tmp = await client.download_media(reply)
    except Exception as e:
        await respond(client, message, smalls(f"→ indirme hatası: {e}"))
        return
    if not tmp or not os.path.exists(tmp):
        await respond(client, message, smalls("→ indirme başarısız"))
        return

    # duplicate kontrol — aynı içerik zaten yüklü mü?
    try:
        tmp_hash = _hash_file(tmp)
        # isim bazlı kontrol
        import re
        base = os.path.basename(fname)
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", base[:-3]) if base.endswith(".py") else re.sub(r"[^a-zA-Z0-9_\-]", "_", base)
        dest_check = get_plugin_path(safe_name)
        if os.path.exists(dest_check):
            existing_hash = _hash_file(dest_check)
            if tmp_hash and tmp_hash == existing_hash:
                try: os.remove(tmp)
                except: pass
                await respond(client, message, smalls(f"→ zaten yüklü: {safe_name}\n→ aynı dosya tekrar yüklenmedi"))
                return
        # içerik bazlı — farklı isimde aynı dosya var mı?
        for p in list_plugins():
            ph = _hash_file(p["path"])
            if ph and ph == tmp_hash:
                try: os.remove(tmp)
                except: pass
                await respond(client, message, smalls(f"→ aynı içerik zaten yüklü: {p['name']}\n→ tekrar yüklenmedi"))
                return
    except Exception:
        pass

    try:
        with open(tmp, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(4000)
        if "import" not in head and "def " not in head and "register" not in head:
            pass
    except Exception:
        pass
    try:
        dest, name, reg = install_from_temp(client, tmp, fname)
        reg_txt = reg or "1 komut"
        # kullanım açıklaması (CmdHelp)
        usage = ""
        try:
            from userbot import CMD_HELP
            # CMD_HELP anahtarı dosya adı (with/without .py)
            usage = CMD_HELP.get(name) or CMD_HELP.get(name + ".py") or ""
            # Bazı pluginler farklı key kullanır, ilk eşleşeni al
            if not usage:
                for k, v in CMD_HELP.items():
                    if name.lower() in k.lower() or k.lower() in name.lower():
                        usage = v
                        break
        except Exception:
            usage = ""
        # ana bilgi
        info_lines = [smalls(f"→ plugin yüklendi: {name}"), smalls(f"→ kayıt: {reg_txt}")]
        await respond(client, message, "\n".join(info_lines))
        print(f"→ .pal ok {name} {reg_txt}", flush=True)
        # kullanım açıklaması ayrı mesaj olarak gönder
        if usage:
            try:
                # usage zaten markdown'lı, olduğu gibi gönder (smalls değil)
                await client.send_message(message.chat.id, usage, reply_to_message_id=message.id)
            except Exception:
                # fallback smalls
                await respond(client, message, usage)
        else:
            # CmdHelp yoksa genel bilgi
            await respond(client, message, smalls(f"→ kullanım: .{name} / .help ile dene\n→ liste: .plist"))
    except Exception as e:
        await respond(client, message, smalls(f"→ yükleme hatası: {e}"))
        print(f".pal hata: {e}", flush=True)
    finally:
        try:
            os.remove(tmp)
        except:
            pass

# ── .psil — isim veya yanıtla sil ──
@rate_limit(3)
async def psil_handler(client: Client, message):
    args = message.command[1:] if message.command else []
    name = None
    if args:
        name = args[0].strip().replace(".py","")
    else:
        # yanıtla silme
        reply = message.reply_to_message
        if reply:
            # dosyaya yanıt → dosya adından
            if reply.document and reply.document.file_name:
                name = reply.document.file_name.replace(".py","")
                # sanitize'e gerek yok delete_plugin yapacak
            elif reply.caption or reply.text:
                # metinden ilk kelimeyi plugin ismi say
                txt = (reply.caption or reply.text or "").strip().split()
                if txt:
                    cand = txt[0].strip().lstrip("•-").replace(".py","")
                    # sadece geçerli isimse al
                    if cand and len(cand) < 40 and "/" not in cand:
                        # eğer liste mesajıysa, • plugin ismi formatından çıkar
                        # ama tek kelime ise direkt kullan
                        pass
            # eğer hala yoksa, reply'nin kendisi bir plugin dosyası mı kontrol et
            if not name and reply.document:
                name = (reply.document.file_name or "").replace(".py","")
        if not name:
            await respond(client, message, smalls("→ kullanım: .psil <isim>\n→ veya bir .py dosyasına yanıtla: .psil\n→ örnek: .psil emojify"))
            return
    # temizle
    name = name.strip().replace(".py","")
    if "/" in name or "\\" in name or ".." in name:
        await respond(client, message, smalls("→ geçersiz isim"))
        return
    # isim sanitize edilmiş halde sil — plugin_loader zaten sanitize ediyor
    existed = delete_plugin(name)
    if existed:
        await respond(client, message, smalls(f"→ plugin silindi: {name}\n→ yeniden başlat önerilir"))
    else:
        plugins = list_plugins()
        names = ", ".join(p["name"] for p in plugins) or "yok"
        await respond(client, message, smalls(f"→ bulunamadı: {name}\n→ mevcut: {names}\n→ ipucu: dosyaya yanıt vererek de silebilirsin"))

# ── .pget ──
@rate_limit(3)
async def pget_handler(client: Client, message):
    args = message.command[1:] if message.command else []
    if not args:
        # yanıtla da alabilir
        reply = message.reply_to_message
        if reply and reply.document and reply.document.file_name and reply.document.file_name.endswith(".py"):
            name = reply.document.file_name.replace(".py","")
        else:
            await respond(client, message, smalls("→ kullanım: .pget <isim>"))
            return
    else:
        name = args[0].strip().replace(".py","")
    code = get_plugin_code(name)
    if code is None:
        await respond(client, message, smalls(f"→ yok: {name}"))
        return
    path = get_plugin_path(name)
    try:
        await client.send_document(
            message.chat.id,
            path,
            caption=smalls(f"→ plugin: {name}"),
            reply_to_message_id=message.id if _is_group(message.chat) else None,
        )
        try:
            await message.delete()
        except:
            pass
    except Exception as e:
        await respond(client, message, smalls(f"→ gönderim hatası: {e}"))

def register_handlers(app: Client):
    from pyrogram.handlers import MessageHandler
    flt = filters.me | filters.outgoing
    app.add_handler(MessageHandler(plist_handler, filters.command(["plist","p_list","plugins","pliste","plistesi"], prefixes=".") & flt))
    app.add_handler(MessageHandler(pal_handler, filters.command(["pal","p_al","pyukle","p_yukle","plugin_al","padd","yukle"], prefixes=".") & flt))
    app.add_handler(MessageHandler(psil_handler, filters.command(["psil","p_sil","pdel","p_del","plugin_sil","premove","sil"], prefixes=".") & flt))
    app.add_handler(MessageHandler(pget_handler, filters.command(["pget","p_get","p_goster","getplugin"], prefixes=".") & flt))
