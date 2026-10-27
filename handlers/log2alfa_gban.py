# ✦ Log2 Alfa GBan / GMute — Pyrogram native (gerçekten çalışır)
#
# Asena'nın Telethon tabanlı gban/gmute'ı Pyrogram'da çalışmıyordu ve zaten
# yüklenmiyordu (plugin_loader userbot.modules.* kayıtlarını filtreliyor).
# Bu modül kendi SQLite tablosunu kullanır ve gerçek işlem yapar.
#
# Komutlar:
#   .gban <yanıt|@kullanıcı|id> [sebep]   → kullanıcıyı global yasaklar (bulunduğun gruptan da atar)
#   .ungban <yanıt|@kullanıcı|id>         → global yasağı kaldırır
#   .gbanlar                              → global yasak listesi
#   .gmute <yanıt|@kullanıcı|id> [sebep]  → global susturur (yazdığı her grup mesajı silinir)
#   .ungmute <yanıt|@kullanıcı|id>        → global susturmayı kaldırır
#   .gmutelar                             → global susturma listesi
import os
import asyncio
import time
import aiosqlite

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler

from utils.helpers import respond
from utils.fonts import smalls as S

HELP_TXT = (S("✦ ɢʙᴀɴ / ɢᴍᴜᴛᴇ") + "\n\n"
            "`.gban <yanıt|@u|id> [sebep]` — global yasak (gruptan atar)\n"
            "`.ungban <...>` — yasağı kaldır\n"
            "`.gbanlar` — yasak listesi\n"
            "`.gmute <...> [sebep]` — global sustur (mesajları silinir)\n"
            "`.ungmute <...>` — susturmayı kaldır\n"
            "`.gmutelar` — susturma listesi\n\n"
            + S("ɴᴏᴛ: ") + S("global susturmada kişinin yazdığı mesajlar grupta silinir; "
                             "global yasakta ayrıca mümkünse gruptan atılır."))

_DB = os.getenv("GBAN_DB") or ("/data/log2alfa_notes.db" if os.path.isdir("/data") else "./log2alfa_notes.db")

_gbanned = set()
_gmuted = set()
_last_sync = 0.0


async def _init():
    async with aiosqlite.connect(_DB) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS gban (
            uid INTEGER PRIMARY KEY, reason TEXT, at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS gmute (
            uid INTEGER PRIMARY KEY, reason TEXT, at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        await db.commit()
    await _sync(force=True)


async def _sync(force=False):
    global _last_sync
    if not force and (time.time() - _last_sync) < 60:
        return
    try:
        async with aiosqlite.connect(_DB) as db:
            async with db.execute("SELECT uid FROM gban") as cur:
                _gbanned.clear()
                _gbanned.update(r[0] for r in await cur.fetchall())
            async with db.execute("SELECT uid FROM gmute") as cur:
                _gmuted.clear()
                _gmuted.update(r[0] for r in await cur.fetchall())
        _last_sync = time.time()
    except Exception as e:
        print(f"gban sync hata: {e}", flush=True)


async def _watchdog():
    while True:
        await asyncio.sleep(60)
        await _sync(force=True)


async def _rows(table):
    try:
        async with aiosqlite.connect(_DB) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(f"SELECT * FROM {table} ORDER BY at DESC") as cur:
                return [dict(r) for r in await cur.fetchall()]
    except Exception:
        return []


async def _add(table, uid, reason=""):
    async with aiosqlite.connect(_DB) as db:
        await db.execute(f"INSERT OR REPLACE INTO {table} (uid, reason) VALUES (?, ?)", (uid, reason))
        await db.commit()
    (_gbanned if table == "gban" else _gmuted).add(uid)


async def _remove(table, uid):
    async with aiosqlite.connect(_DB) as db:
        cur = await db.execute(f"DELETE FROM {table} WHERE uid=?", (uid,))
        await db.commit()
        ok = cur.rowcount > 0
    (_gbanned if table == "gban" else _gmuted).discard(uid)
    return ok


async def _resolve(client, message):
    """Yanıt / @kullanıcı / id → (user, sebep)"""
    rep = message.reply_to_message
    if rep and getattr(rep, "from_user", None):
        parts = (message.text or "").split(maxsplit=1)
        sebep = parts[1].strip() if len(parts) > 1 else ""
        return rep.from_user, sebep
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        return None, ""
    q = parts[1].strip()
    sebep = parts[2].strip() if len(parts) > 2 else ""
    try:
        if q.lstrip("-").isdigit():
            return await client.get_users(int(q)), sebep
        return await client.get_users(q.lstrip("@")), sebep
    except Exception as e:
        print(f"gban hedef çözümlenemedi ({q}): {e}", flush=True)
        return None, sebep


async def _name_of(client, uid):
    try:
        u = await client.get_users(uid)
        ad = u.first_name or ""
        return f"{ad} @{u.username}" if getattr(u, "username", None) else (ad or str(uid))
    except Exception:
        return str(uid)


def _list_text(rows, title, bos):
    if not rows:
        return S(f"✦ {bos}")
    lines = [S(f"✦ {title}") + f"  ({len(rows)})", "━━━━━━━━━━━━━━━━"]
    for r in rows[:40]:
        r_ = (r.get("reason") or "").strip()
        lines.append(f"• `{r['uid']}`" + (f" — {r_[:30]}" if r_ else ""))
    if len(rows) > 40:
        lines.append(f"… +{len(rows) - 40}")
    return "\n".join(lines)


# ───────────────────────────── komutlar ─────────────────────────────

async def gban_handler(client: Client, message):
    user, sebep = await _resolve(client, message)
    if not user:
        return await respond(client, message, S("✦ ᴋᴜʟʟᴀɴɪᴍ: ") + "`.gban <yanıt|@kullanıcı|id> [sebep]`")
    if getattr(user, "is_self", False):
        return await respond(client, message, S("✦ ᴋᴇɴᴅɪɴɪ ɢʙᴀɴʟᴀʏᴀᴍᴀᴢsıɴ."))
    await _add("gban", user.id, sebep)
    atildi = ""
    try:
        await client.ban_chat_member(message.chat.id, user.id)
        atildi = " • " + S("ɢʀᴜᴘᴛᴀɴ ᴀᴛıʟᴅı")
    except Exception:
        pass
    isim = user.first_name or str(user.id)
    uname = f" @{user.username}" if getattr(user, "username", None) else ""
    return await respond(client, message,
        f"🚫 **GBAN** — {isim}{uname}\n`{user.id}`\n"
        + (S("sᴇʙᴇᴘ: ") + f"{sebep}\n" if sebep else "")
        + S("ᴀʀᴛıᴋ ʜᴇʀ ɢʀᴜᴘᴛᴀ ᴍᴇsᴀᴊʟᴀʀı sɪʟɪɴɪʀ") + atildi)


async def ungban_handler(client: Client, message):
    user, _ = await _resolve(client, message)
    if not user:
        return await respond(client, message, S("✦ ᴋᴜʟʟᴀɴɪᴍ: ") + "`.ungban <yanıt|@kullanıcı|id>`")
    ok = await _remove("gban", user.id)
    return await respond(client, message,
        (f"✅ `{user.id}` {S('ɢʙᴀɴ ᴋᴀʟᴅıʀıʟᴅı.')}" if ok else S("✦ ᴛʜɪs ᴋɪşɪ ɢʙᴀɴʟı ᴅᴇɢɪʟ.")))


async def gbanlar_handler(client: Client, message):
    rows = await _rows("gban")
    return await respond(client, message, _list_text(rows, "ɢʙᴀɴ ʟɪsᴛᴇsɪ", "ɢʙᴀɴʟı ᴋɪᴍsᴇ ʏᴏᴋ."))


async def gmute_handler(client: Client, message):
    user, sebep = await _resolve(client, message)
    if not user:
        return await respond(client, message, S("✦ ᴋᴜʟʟᴀɴɪᴍ: ") + "`.gmute <yanıt|@kullanıcı|id> [sebep]`")
    if getattr(user, "is_self", False):
        return await respond(client, message, S("✦ ᴋᴇɴᴅɪɴɪ ɢᴍᴜᴛᴇʟᴀʏᴀᴍᴀᴢsıɴ."))
    await _add("gmute", user.id, sebep)
    isim = user.first_name or str(user.id)
    uname = f" @{user.username}" if getattr(user, "username", None) else ""
    return await respond(client, message,
        f"🔇 **GMUTE** — {isim}{uname}\n`{user.id}`\n"
        + (S("sᴇʙᴇᴘ: ") + f"{sebep}\n" if sebep else "")
        + S("ᴀʀᴛıᴋ ʜᴇʀ ɢʀᴜᴘᴛᴀ ᴍᴇsᴀᴊʟᴀʀı sɪʟɪɴɪʀ"))


async def ungmute_handler(client: Client, message):
    user, _ = await _resolve(client, message)
    if not user:
        return await respond(client, message, S("✦ ᴋᴜʟʟᴀɴɪᴍ: ") + "`.ungmute <yanıt|@kullanıcı|id>`")
    ok = await _remove("gmute", user.id)
    return await respond(client, message,
        (f"✅ `{user.id}` {S('ɢᴍᴜᴛᴇ ᴋᴀʟᴅıʀıʟᴅı.')}" if ok else S("✦ ᴛʜɪs ᴋɪşɪ ɢᴍᴜᴛᴇʟı ᴅᴇɢɪʟ.")))


async def gmutelar_handler(client: Client, message):
    rows = await _rows("gmute")
    return await respond(client, message, _list_text(rows, "ɢᴍᴜᴛᴇ ʟɪsᴛᴇsɪ", "ɢᴍᴜᴛᴇʟı ᴋɪᴍsᴇ ʏᴏᴋ."))


async def enforce_handler(client: Client, message):
    """GBAN/GMUTE uygulaması: kişinin grup mesajlarını siler, gbanned ise atar."""
    uid = getattr(getattr(message, "from_user", None), "id", None)
    if not uid or getattr(message, "outgoing", False):
        return
    if (time.time() - _last_sync) > 60:
        await _sync()
    if uid not in _gbanned and uid not in _gmuted:
        return
    try:
        await message.delete()
    except Exception as e:
        print(f"gban/gmute silme hatası ({uid}): {e}", flush=True)
    if uid in _gbanned:
        try:
            await client.ban_chat_member(message.chat.id, uid)
        except Exception:
            pass


# ───────────────────────────── kayıt ─────────────────────────────

def register_handlers(app: Client):
    flt = filters.me | filters.outgoing
    app.add_handler(MessageHandler(gban_handler, filters.command(["gban"], prefixes=".") & flt))
    app.add_handler(MessageHandler(ungban_handler, filters.command(["ungban"], prefixes=".") & flt))
    app.add_handler(MessageHandler(gbanlar_handler, filters.command(["gbanlar", "gbanlist"], prefixes=".") & flt))
    app.add_handler(MessageHandler(gmute_handler, filters.command(["gmute"], prefixes=".") & flt))
    app.add_handler(MessageHandler(ungmute_handler, filters.command(["ungmute"], prefixes=".") & flt))
    app.add_handler(MessageHandler(gmutelar_handler, filters.command(["gmutelar", "gmutelist"], prefixes=".") & flt))
    # Uygulama katmanı — gruplarda çalışır, diğer handler'lardan önce
    app.add_handler(MessageHandler(enforce_handler, filters.group), group=-2)

    try:
        asyncio.get_event_loop().create_task(_init())
        asyncio.get_event_loop().create_task(_watchdog())
    except Exception:
        pass

    try:
        from userbot.cmdhelp import CmdHelp
        CmdHelp("gban").add_command("gban", "<yanıt|@u|id> [sebep]", "Global yasak (gruptan atar).") \
            .add_command("ungban", "<yanıt|@u|id>", "Global yasağı kaldırır.") \
            .add_command("gbanlar", None, "Global yasak listesi.") \
            .add_command("gmute", "<yanıt|@u|id> [sebep]", "Global susturma (mesajları silinir).") \
            .add_command("ungmute", "<yanıt|@u|id>", "Global susturmayı kaldırır.") \
            .add_command("gmutelar", None, "Global susturma listesi.") \
            .add_info("@Log2Alfa • Pyrogram native gban/gmute").add()
    except Exception:
        pass
