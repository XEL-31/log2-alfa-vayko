"""AFK ve temel araçlar"""
from pyrogram import Client, filters
from pyrogram.enums import MessageEntityType, ChatType
from utils.security import rate_limit
from utils.helpers import respond
import asyncio, time

# Her userbot hesabı kendi AFK durumunu tutar
_afk_states = {}
_me_cache = {}


def _st(client):
    key = getattr(client, "name", "default")
    if key not in _afk_states:
        _afk_states[key] = {
            "is_afk": False,
            "reason": "AFK",
            "since": 0,
            "last_reply": {},
        }
    return _afk_states[key]


def _chat_type_str(chat) -> str:
    ct = getattr(chat, "type", None)
    if ct is None:
        return ""
    if isinstance(ct, str):
        return ct.lower()
    if ct in (ChatType.PRIVATE,):
        return "private"
    if ct in (ChatType.GROUP, ChatType.SUPERGROUP):
        return "group"
    v = getattr(ct, "value", None)
    if isinstance(v, str):
        return v.lower()
    return (getattr(ct, "name", "") or "").lower() or str(ct).lower()


def _dur_format(since):
    dur = int(time.time() - since) if since else 0
    mins, secs = divmod(dur, 60)
    if mins >= 60:
        h, m2 = divmod(mins, 60)
        return f"{h}s {m2}dk {secs}sn"
    return f"{mins}dk {secs}sn"


async def _afk_log(client, text):
    try:
        from userbot_core import send_log
        oid = None
        name = getattr(client, "name", "") or ""
        if name.startswith("userbot_"):
            try:
                oid = int(name.split("_", 1)[1])
            except Exception:
                pass
        await send_log(f"🌙 **AFK**\n{text}", owner_id=oid)
    except Exception as e:
        print(f"AFK log hatası: {e}", flush=True)


async def _afk_off(client, message=None):
    st = _st(client)
    if not st["is_afk"]:
        return
    st["is_afk"] = False
    st["last_reply"] = {}
    dur = _dur_format(st["since"])
    print(f"AFK KAPANDI ({getattr(client,'name','?')}) — süre: {dur}", flush=True)
    await _afk_log(client, f"AFK kapandı — süre: {dur}")
    if message is not None:
        try:
            me = await client.get_me()
            fname = (me.first_name if me else None) or "sen"
        except Exception:
            fname = "sen"
        try:
            await respond(client, message, f"Afk offline {fname}")
        except Exception as e:
            print(f"AFK off mesaj hatası: {e}", flush=True)


@rate_limit(2)
async def afk_handler(client: Client, message):
    st = _st(client)
    if st["is_afk"]:
        print(f"AFK manuel kapatıldı ({getattr(client,'name','?')})", flush=True)
        await _afk_off(client, message)
        return
    args = " ".join(message.command[1:]) if len(message.command) > 1 else "AFK"
    st["is_afk"] = True
    st["reason"] = args
    st["since"] = time.time()
    st["last_reply"] = {}
    print(f"AFK AÇILDI ({getattr(client,'name','?')}) — {args}", flush=True)
    await _afk_log(client, f"AFK açıldı — {args}")
    await respond(
        client, message,
        "Afk modundayım, çıkmak için komutu tekrar kullan veya bir mesaj at.",
    )


async def afk_watch_self(client: Client, message):
    """Kendi düz metin mesajı AFK kapatır — nokta-komutlar kapatmaz"""
    try:
        st = _st(client)
        if not st["is_afk"]:
            return
        # sadece kendi giden mesaj
        if not getattr(message, "outgoing", False):
            fu = message.from_user
            if not fu or not getattr(fu, "is_self", False):
                return
        text = (message.text or message.caption or "").strip()
        # komutlar AFK kapatmaz
        if text.startswith("."):
            return
        try:
            me = await client.get_me()
            fname = me.first_name or "sen"
        except Exception:
            fname = "sen"
        print(f"AFK kendi mesajla otomatik kapandı ({getattr(client,'name','?')})", flush=True)
        await _afk_off(client, message=None)
        try:
            m = await message.reply_text(f"Afk offline {fname}", quote=False)
            await asyncio.sleep(4)
            await m.delete()
        except Exception as e:
            print(f"AFK auto-off reply hatası: {e}", flush=True)
    except Exception as e:
        print(f"AFK watch_self hata: {e}", flush=True)


async def _get_me_cached(client):
    key = getattr(client, "name", "default")
    if key not in _me_cache:
        me = await client.get_me()
        _me_cache[key] = (me.id, (me.username or "").lower())
    return _me_cache[key]


def _entity_type_name(ent) -> str:
    t = getattr(ent, "type", None)
    if t is None:
        return ""
    if isinstance(t, str):
        return t.lower()
    v = getattr(t, "value", None) or getattr(t, "name", None)
    return str(v or t).lower()


async def _is_for_me(client, message, me_id: int, me_username: str) -> bool:
    """DM / yanıt / @etiket / text_mention bana mı?"""
    chat_type = _chat_type_str(message.chat)
    if "private" in chat_type:
        return True

    # yanıtlama
    r = message.reply_to_message
    if r is not None:
        ru = getattr(r, "from_user", None)
        if ru is not None and getattr(ru, "id", None) == me_id:
            return True
        if getattr(r, "outgoing", False):
            return True

    text = message.text or message.caption or ""
    # @username
    if me_username and f"@{me_username}" in text.lower():
        return True

    # entities — ENUM güvenli
    ents = list(message.entities or []) + list(message.caption_entities or [])
    for ent in ents:
        name = _entity_type_name(ent)
        # text_mention → user id kontrol
        if "text_mention" in name:
            u = getattr(ent, "user", None)
            if u is not None and getattr(u, "id", None) == me_id:
                return True
            # user yoksa da mention say (bazı sürümler)
            if u is None:
                return True
        elif name == "mention" or name.endswith("mention"):
            # @username mention — metinden doğrula
            try:
                off = getattr(ent, "offset", 0) or 0
                ln = getattr(ent, "length", 0) or 0
                chunk = text[off:off + ln].lstrip("@").lower()
                if me_username and chunk == me_username:
                    return True
            except Exception:
                if me_username and f"@{me_username}" in text.lower():
                    return True
        # enum doğrudan
        try:
            if ent.type in (MessageEntityType.TEXT_MENTION,):
                u = getattr(ent, "user", None)
                if u is not None and u.id == me_id:
                    return True
            if ent.type in (MessageEntityType.MENTION,) and me_username:
                if f"@{me_username}" in text.lower():
                    return True
        except Exception:
            pass
    return False


async def afk_mention_handler(client: Client, message):
    """AFK iken: DM + etiket + yanıt → her şeye AFK cevabı (çökmeden)"""
    try:
        st = _st(client)
        if not st["is_afk"]:
            return
        # kendi mesajı değil
        fu = message.from_user
        if fu is not None and (getattr(fu, "is_self", False) or getattr(fu, "is_bot", False)):
            return

        me_id, me_username = await _get_me_cached(client)
        if not await _is_for_me(client, message, me_id, me_username):
            return

        chat_id = message.chat.id if message.chat else 0
        last = st["last_reply"].get(chat_id, 0)
        if time.time() - last < 45:
            return
        st["last_reply"][chat_id] = time.time()

        who = (fu.first_name if fu else "?") or "?"
        wuser = (fu.username if fu else "-") or "-"
        wid = fu.id if fu else "?"
        txt = (message.text or message.caption or "")[:120]
        chat_type = _chat_type_str(message.chat)
        chat_title = getattr(message.chat, "title", None) or (
            "özel sohbet" if "private" in chat_type else str(chat_id)
        )
        dur = _dur_format(st["since"])
        reason = st.get("reason") or "AFK"

        print(
            f"AFK DM/etiket: {who} ({wid}) chat={chat_id} type={chat_type}",
            flush=True,
        )

        reply_txt = f"Şuanda Afk'yım Size geri dönüş yapacağım... uptime: {dur}"
        try:
            await message.reply_text(reply_txt, quote=True)
        except Exception as e:
            print(f"AFK reply hatası: {e}", flush=True)
            try:
                await client.send_message(chat_id, reply_txt)
            except Exception as e2:
                print(f"AFK send hata: {e2}", flush=True)

        await _afk_log(client, (
            f"Kim: {who} @{wuser} — {wid}\n"
            f"Nereden: {chat_title} ({chat_type}) {chat_id}\n"
            f"Yazı: {txt}\n"
            f"AFK süresi: {dur}"
        ))
    except Exception as e:
        import traceback
        print(f"AFK mention hatası: {e}\n{traceback.format_exc()}", flush=True)


def register_handlers(app: Client):
    from pyrogram.handlers import MessageHandler
    app.add_handler(MessageHandler(
        afk_handler,
        filters.command("afk", prefixes=".") & (filters.me | filters.outgoing),
    ))
    # kendi düz metin → AFK kapat (komutlar hariç)
    app.add_handler(MessageHandler(
        afk_watch_self,
        filters.outgoing & filters.text & ~filters.regex(r"^\.[a-zA-Z]"),
    ), group=1)
    # grup: her gelen mesaj (text+medya) — etiket/yanıt kontrolü handler içinde
    app.add_handler(MessageHandler(
        afk_mention_handler,
        filters.group & ~filters.outgoing & ~filters.bot,
    ), group=2)
    # DM: her gelen
    app.add_handler(MessageHandler(
        afk_mention_handler,
        filters.private & ~filters.outgoing & ~filters.bot,
    ), group=2)
