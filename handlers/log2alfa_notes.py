# ✦ Log2 Alfa Notlar — Pyrogram native (medya + metin notları)
#
# Komutlar:
#   .nsave <ad>    → yanıtlanan mesajı not olarak kaydeder (metin VEYA medya)
#   .not <ad>      → notu gösterir (medya notu ise medyayı yeniden gönderir)
#   .notlar        → bu sohbetteki notları listeler
#   .notsil <ad>   → notu siler
#   .notsil hepsi  → tüm notları siler
#
# Medya notları file_id ile saklanır → başka sohbete taşınsa da çalışır.
import os
import aiosqlite

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler

from utils.helpers import respond
from utils.fonts import smalls as S

HELP_TXT = (S("✦ ɴᴏᴛ sɪsᴛᴇᴍɪ") + "\n\n"
            "`.nsave <ad>` — yanıtladığın mesajı not yap (metin veya medya)\n"
            "`.not <ad>` — notu göster\n"
            "`.notlar` — bu sohbetteki notlar\n"
            "`.notsil <ad>` — notu sil (`" + S("hepsi") + "` → tümü)\n"
            "`#ad` — notu doğrudan çağır")

_DB = os.getenv("NOTES_DB") or ("/data/log2alfa_notes.db" if os.path.isdir("/data") else "./log2alfa_notes.db")


async def _init():
    async with aiosqlite.connect(_DB) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS notes (
            chat_id INTEGER, keyword TEXT, text TEXT, file_id TEXT, media_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, keyword))""")
        await db.commit()


def _norm(kw: str) -> str:
    return (kw or "").strip().lstrip("#").lower()[:48]


async def _save(chat_id, keyword, text=None, file_id=None, media_type=None):
    async with aiosqlite.connect(_DB) as db:
        await db.execute("""INSERT OR REPLACE INTO notes (chat_id, keyword, text, file_id, media_type)
                            VALUES (?, ?, ?, ?, ?)""", (chat_id, keyword, text, file_id, media_type))
        await db.commit()


async def _get(chat_id, keyword):
    async with aiosqlite.connect(_DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM notes WHERE chat_id=? AND keyword=?", (chat_id, keyword)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def _list(chat_id):
    async with aiosqlite.connect(_DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM notes WHERE chat_id=? ORDER BY keyword", (chat_id,)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def _delete(chat_id, keyword):
    async with aiosqlite.connect(_DB) as db:
        cur = await db.execute("DELETE FROM notes WHERE chat_id=? AND keyword=?", (chat_id, keyword))
        await db.commit()
        return cur.rowcount


async def _delete_all(chat_id):
    async with aiosqlite.connect(_DB) as db:
        cur = await db.execute("DELETE FROM notes WHERE chat_id=?", (chat_id,))
        await db.commit()
        return cur.rowcount


async def _send_note(client, chat_id, note, reply_to=None):
    """Notu gönderir — medya notu ise medyayı yeniden yollar."""
    fid = note.get("file_id")
    txt = note.get("text") or ""
    if fid:
        mtype = note.get("media_type") or "document"
        cap = txt or None
        try:
            if mtype == "photo":
                return await client.send_photo(chat_id, fid, caption=cap, reply_to_message_id=reply_to)
            if mtype == "video":
                return await client.send_video(chat_id, fid, caption=cap, reply_to_message_id=reply_to)
            if mtype == "animation":
                return await client.send_animation(chat_id, fid, caption=cap, reply_to_message_id=reply_to)
            if mtype == "audio":
                return await client.send_audio(chat_id, fid, caption=cap, reply_to_message_id=reply_to)
            if mtype == "voice":
                return await client.send_voice(chat_id, fid, caption=cap, reply_to_message_id=reply_to)
            return await client.send_document(chat_id, fid, caption=cap, reply_to_message_id=reply_to)
        except Exception as e:
            print(f"not medya gönderilemedi ({mtype}): {e}", flush=True)
    if txt:
        return await client.send_message(chat_id, txt, reply_to_message_id=reply_to)
    return None


# ───────────────────────────── komutlar ─────────────────────────────

async def kaydet_handler(client: Client, message):
    """.nsave <ad> — yanıtlanan mesajı not olarak kaydeder."""
    args = (message.text or "").split(maxsplit=1)
    keyword = _norm(args[1]) if len(args) > 1 else ""
    if not keyword:
        return await respond(client, message, S("✦ ᴋᴜʟʟᴀɴɪᴍ: ") + "`.nsave <ad>` " + S("(bir mesajı yanıtla)"))
    rep = message.reply_to_message
    if not rep:
        return await respond(client, message, S("✦ ʙɪʀ ᴍᴇsᴀᴊı ʏᴀɴıᴛʟᴀʏɪᴘ ") + "`.nsave <ad>` " + S("ʏᴀᴢ."))

    txt = getattr(rep, "text", None) or getattr(rep, "caption", None) or None
    fid = mtype = None
    for kind, attr in (("photo", "photo"), ("video", "video"), ("animation", "animation"),
                       ("audio", "audio"), ("voice", "voice"), ("document", "document"),
                       ("sticker", "sticker")):
        obj = getattr(rep, attr, None)
        if obj is not None:
            fid = getattr(obj, "file_id", None)
            mtype = kind
            break
    if not txt and not fid:
        return await respond(client, message, S("✦ ʏᴀɴıᴛʟᴀɴᴀɴ ᴍᴇsᴀᴊᴅᴀ ᴋᴀʏᴅᴇᴅɪʟᴇᴄᴇᴋ ɪᴄᴇʀɪᴋ ʏᴏᴋ."))

    await _save(message.chat.id, keyword, txt, fid, mtype)
    tur = S("ᴍᴇᴅʏᴀ + ᴍᴇᴛɪɴ") if (fid and txt) else (S("ᴍᴇᴅʏᴀ") if fid else S("ᴍᴇᴛɪɴ"))
    return await respond(client, message, f"✅ `#{keyword}` {S('ɴᴏᴛ ᴏʟᴀʀᴀᴋ ᴋᴀʏᴅᴇᴅɪʟᴅɪ')} ({tur})")


async def not_handler(client: Client, message):
    """.not <ad> — notu gösterir."""
    args = (message.text or "").split(maxsplit=1)
    keyword = _norm(args[1]) if len(args) > 1 else ""
    if not keyword:
        return await respond(client, message, S("✦ ᴋᴜʟʟᴀɴɪᴍ: ") + "`.not <ad>`")
    note = await _get(message.chat.id, keyword)
    if not note:
        return await respond(client, message, f"✖️ `#{keyword}` {S('ʙᴜʟᴜɴᴀᴍᴀᴅı')} — `.notlar` " + S("ɪʟᴇ ʟɪsᴛᴇʟᴇ."))
    await _send_note(client, message.chat.id, note, reply_to=getattr(message, "id", None))


async def notlar_handler(client: Client, message):
    """.notlar — bu sohbetteki notları listeler."""
    notes = await _list(message.chat.id)
    if not notes:
        return await respond(client, message, S("✦ ʙᴜ sᴏʜʙᴇᴛᴛᴇ ɴᴏᴛ ʏᴏᴋ."))
    lines = [S("✦ ɴᴏᴛʟᴀʀ") + f"  ({len(notes)})", "━━━━━━━━━━━━━━━━"]
    for n in notes:
        t = (n.get("text") or "").replace("\n", " ")
        if len(t) > 34:
            t = t[:34] + "…"
        if n.get("file_id") and not t:
            t = "[" + (n.get("media_type") or "medya") + "]"
        lines.append(f"• `#{n['keyword']}` — {t or '—'}")
    lines += ["━━━━━━━━━━━━━━━━", S("ɢᴏsᴛᴇʀᴍᴇᴋ ɪᴄɪɴ: ") + "`.not <ad>`"]
    return await respond(client, message, "\n".join(lines))


async def notsil_handler(client: Client, message):
    """.notsil <ad> — notu siler."""
    args = (message.text or "").split(maxsplit=1)
    keyword = _norm(args[1]) if len(args) > 1 else ""
    if not keyword:
        return await respond(client, message, S("✦ ᴋᴜʟʟᴀɴɪᴍ: ") + "`.notsil <ad>` " + S("ᴠᴇʏᴀ ") + "`.notsil hepsi`")
    if keyword in ("hepsi", "tumu", "tümü", "all"):
        n = await _delete_all(message.chat.id)
        return await respond(client, message, f"🗑️ {n} {S('ɴᴏᴛ sɪʟɪɴᴅɪ.')}")
    n = await _delete(message.chat.id, keyword)
    if not n:
        return await respond(client, message, f"✖️ `#{keyword}` {S('ʙᴜʟᴜɴᴀᴍᴀᴅı')}")
    return await respond(client, message, f"🗑️ `#{keyword}` {S('sɪʟɪɴᴅɪ.')}")


async def hashtag_handler(client: Client, message):
    """#ad yazılınca notu çağırır (not varsa)."""
    txt = (message.text or "").strip()
    if not txt.startswith("#") or " " in txt:
        return
    keyword = _norm(txt)
    if not keyword:
        return
    note = await _get(message.chat.id, keyword)
    if not note:
        return
    await _send_note(client, message.chat.id, note, reply_to=getattr(message, "id", None))


# ───────────────────────────── kayıt ─────────────────────────────

def register_handlers(app: Client):
    flt = filters.me | filters.outgoing
    app.add_handler(MessageHandler(kaydet_handler,
        filters.command(["nsave", "kaydet", "notekle", "notkaydet"], prefixes=".") & flt))
    app.add_handler(MessageHandler(not_handler,
        filters.command(["not", "notal", "notgoster", "notgöster"], prefixes=".") & flt))
    app.add_handler(MessageHandler(notlar_handler,
        filters.command(["notlar", "notes"], prefixes=".") & flt))
    app.add_handler(MessageHandler(notsil_handler,
        filters.command(["notsil", "delnote", "clear"], prefixes=".") & flt))
    app.add_handler(MessageHandler(hashtag_handler, filters.regex(r"^#\w{1,48}$") & ~flt))

    try:
        import asyncio
        asyncio.get_event_loop().create_task(_init())
    except Exception:
        pass

    try:
        from userbot.cmdhelp import CmdHelp
        CmdHelp("notes").add_command("nsave", "<ad>", "Yanıtlanan mesajı not yapar (metin/medya).") \
            .add_command("not", "<ad>", "Notu gösterir.") \
            .add_command("notlar", None, "Sohbetteki notları listeler.") \
            .add_command("notsil", "<ad|hepsi>", "Notu/notları siler.") \
            .add_info("@Log2Alfa • medya destekli notlar").add()
    except Exception:
        pass
