"""Grup etiket — .tagall / .dur
Başlangıç mesajı YOK. Tek tek etiket (smalls). Sonda smalls rapor.
"""
import asyncio
import re
from pyrogram import Client, filters
from pyrogram.enums import ChatType, ChatMembersFilter, ParseMode
from pyrogram.errors import FloodWait
from utils.security import rate_limit
from utils.helpers import respond
from utils.fonts import smalls

_jobs: dict[int, dict] = {}
INTERVAL = 3.0
MAX_MEMBERS = 400


def _is_group(chat) -> bool:
    ct = getattr(chat, "type", None)
    if ct is None:
        return False
    if ct in (ChatType.GROUP, ChatType.SUPERGROUP):
        return True
    s = str(getattr(ct, "value", None) or getattr(ct, "name", None) or ct).lower()
    return "group" in s and "channel" not in s


def _is_real_user(u) -> bool:
    if u is None:
        return False
    if getattr(u, "is_bot", False) or getattr(u, "bot", False):
        return False
    if getattr(u, "is_deleted", False) or getattr(u, "deleted", False):
        return False
    uid = getattr(u, "id", None)
    return bool(uid and uid > 0)


async def _collect_members(client: Client, chat_id: int, me_id: int) -> list:
    users, seen = [], set()

    async def _add(u):
        if not _is_real_user(u):
            return
        if u.id == me_id or u.id in seen:
            return
        seen.add(u.id)
        users.append(u)

    try:
        async for m in client.get_chat_members(
            chat_id, query="", limit=MAX_MEMBERS, filter=ChatMembersFilter.SEARCH
        ):
            await _add(getattr(m, "user", None))
            if len(users) >= MAX_MEMBERS:
                break
    except Exception as e:
        print(f"→ tagall SEARCH hata: {e}", flush=True)

    if len(users) < 2:
        try:
            async for m in client.get_chat_members(
                chat_id, limit=MAX_MEMBERS, filter=ChatMembersFilter.RECENT
            ):
                await _add(getattr(m, "user", None))
                if len(users) >= MAX_MEMBERS:
                    break
        except Exception as e:
            print(f"→ tagall RECENT hata: {e}", flush=True)

    if len(users) < 2:
        try:
            from pyrogram import raw
            offset = 0
            while len(users) < MAX_MEMBERS:
                peer = await client.resolve_peer(chat_id)
                r = await client.invoke(
                    raw.functions.channels.GetParticipants(
                        channel=peer,
                        filter=raw.types.ChannelParticipantsRecent(),
                        offset=offset,
                        limit=200,
                        hash=0,
                    )
                )
                parts = getattr(r, "participants", None) or []
                id_map = {u.id: u for u in (getattr(r, "users", None) or [])}
                if not parts:
                    break
                for p in parts:
                    uid = getattr(p, "user_id", None)
                    u = id_map.get(uid) if uid else None
                    if u is None:
                        continue
                    class U:
                        pass
                    uu = U()
                    uu.id = u.id
                    uu.first_name = getattr(u, "first_name", None) or "üye"
                    uu.is_bot = bool(getattr(u, "bot", False))
                    uu.is_deleted = bool(getattr(u, "deleted", False))
                    await _add(uu)
                offset += len(parts)
                if len(parts) < 200:
                    break
        except Exception as e:
            print(f"→ tagall RAW hata: {e}", flush=True)
    return users


def _report_text(tagged: int, custom: str) -> str:
    """smalls rapor — başlangıç mesajı yok, sadece final"""
    lines = [
        "✦  log2alfa tagall rapor",
        "━━━━━━━━━━━━━━━━",
    ]
    if custom:
        lines.append(f"→ Mesaj: {custom[:80]}")
    lines.append(f"→ Kac Kisi Etiketlendi? : {tagged}")
    lines.append("━━━━━━━━━━━━━━━━")
    return smalls("\n".join(lines))


async def _tag_loop(client: Client, chat_id: int, text: str, stop: asyncio.Event, reply_to: int | None):
    try:
        me = await client.get_me()
        members = await _collect_members(client, chat_id, me.id)
        if not members:
            await client.send_message(chat_id, smalls("→ etiketlenecek kisi yok"))
            return

        total = len(members)
        # başlangıç metni YOK — direkt etiket
        tagged = 0
        msg_part = (text or "").strip()
        msg_small = smalls(msg_part) if msg_part else ""

        for u in members:
            if stop.is_set():
                break
            raw_name = str(getattr(u, "first_name", None) or "uye").replace("<", "").replace(">", "")[:24]
            name_s = smalls(raw_name)
            # →  (İsim), mesaj   — isim tıklanabilir mention, smalls metin
            if msg_small:
                body = f'→  (<a href="tg://user?id={u.id}">{name_s}</a>), {msg_small}'
            else:
                body = f'→  (<a href="tg://user?id={u.id}">{name_s}</a>)'
            try:
                await client.send_message(
                    chat_id,
                    body,
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=reply_to,
                    disable_web_page_preview=True,
                )
                tagged += 1
            except FloodWait as e:
                wait = int(getattr(e, "value", None) or 5)
                await asyncio.sleep(wait + 1)
                try:
                    await client.send_message(
                        chat_id, body, parse_mode=ParseMode.HTML,
                        reply_to_message_id=reply_to, disable_web_page_preview=True,
                    )
                    tagged += 1
                except Exception as e2:
                    print(f"→ tagall retry hata: {e2}", flush=True)
            except Exception as e:
                err = str(e).lower()
                print(f"→ tagall gönderim hata: {e}", flush=True)
                m = re.search(r"wait of (\d+)", err)
                if m or "flood" in err:
                    await asyncio.sleep(int(m.group(1)) if m else 5)
                    continue
                if "forbidden" in err or "chat_write" in err:
                    break
            if stop.is_set():
                break
            try:
                await asyncio.wait_for(stop.wait(), timeout=INTERVAL)
                break
            except asyncio.TimeoutError:
                pass

        try:
            await client.send_message(chat_id, _report_text(tagged, msg_part))
        except Exception:
            pass
        print(f"→ tagall bitti tagged={tagged}/{total} stop={stop.is_set()}", flush=True)
    except Exception as e:
        print(f"→ tagall loop hata: {e}", flush=True)
    finally:
        _jobs.pop(chat_id, None)


@rate_limit(3)
async def tagall_handler(client: Client, message):
    chat = message.chat
    if not chat or not _is_group(chat):
        await respond(client, message, smalls("→ sadece gruplarda"))
        return
    chat_id = chat.id
    if chat_id in _jobs and not _jobs[chat_id]["stop"].is_set():
        await respond(client, message, smalls("→ zaten calisiyor — .dur"))
        return

    args = " ".join(message.command[1:]).strip() if message.command else ""
    reply = message.reply_to_message
    text = args
    reply_to = None
    if reply is not None:
        reply_to = reply.id
        if not text:
            text = (reply.text or reply.caption or "").strip()

    stop = asyncio.Event()
    try:
        await message.delete()
    except Exception:
        pass

    task = asyncio.create_task(_tag_loop(client, chat_id, text, stop, reply_to))
    _jobs[chat_id] = {"stop": stop, "task": task}
    print(f"→ tagall start chat={chat_id} text={text[:40]!r}", flush=True)


@rate_limit(1)
async def dur_handler(client: Client, message):
    chat = message.chat
    if not chat or not _is_group(chat):
        await respond(client, message, smalls("→ sadece gruplarda"))
        return
    chat_id = chat.id
    job = _jobs.get(chat_id)
    if not job or job["stop"].is_set():
        await respond(client, message, smalls("→ calisan tagall yok"))
        return
    job["stop"].set()
    try:
        await message.delete()
    except Exception:
        pass
    print(f"→ tagall stop chat={chat_id}", flush=True)


def register_handlers(app: Client):
    from pyrogram.handlers import MessageHandler
    flt = filters.me | filters.outgoing
    app.add_handler(MessageHandler(
        tagall_handler,
        filters.command(["tagall", "tag"], prefixes=".") & flt,
    ))
    app.add_handler(MessageHandler(
        dur_handler,
        filters.command(["dur", "tagstop"], prefixes=".") & flt,
    ))
