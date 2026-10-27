"""Log2 Alfa Info — sade bilgi komutları, Pyrogram native"""
from pyrogram import Client, filters
from utils.security import rate_limit
from utils.helpers import respond
from utils.fonts import smalls

@rate_limit(2)
async def id_handler(client: Client, message):
    r = message.reply_to_message
    chat = message.chat
    me = await client.get_me()
    lines = []
    lines.append(smalls("✦ id bilgisi"))
    lines.append(smalls("━━━━━━━━━━━━━━━━"))
    lines.append(smalls(f"→ sen: {me.id} (@{me.username or '-'})"))
    lines.append(smalls(f"→ sohbet: {chat.id} ({getattr(chat,'title',None) or chat.type})"))
    if r:
        fu = r.from_user
        if fu:
            lines.append(smalls(f"→ yanıt: {fu.id} — {fu.first_name} (@{fu.username or '-'})"))
        lines.append(smalls(f"→ mesaj id: {r.id}"))
    lines.append(smalls(f"→ bu mesaj: {message.id}"))
    await respond(client, message, "\n".join(lines))

@rate_limit(2)
async def whois_handler(client: Client, message):
    target = None
    r = message.reply_to_message
    if r and r.from_user:
        target = r.from_user
    else:
        args = message.text.split(maxsplit=1)
        if len(args) > 1:
            q = args[1].strip().lstrip("@")
            try:
                if q.isdigit():
                    target = await client.get_users(int(q))
                else:
                    target = await client.get_users(q)
            except Exception:
                pass
    if not target:
        # kendisi
        target = await client.get_me()
    # chat member bilgisi (gruplarda)
    status = ""
    try:
        if message.chat and "group" in str(getattr(message.chat.type, "")).lower():
            m = await client.get_chat_member(message.chat.id, target.id)
            status = str(getattr(m.status, "value", m.status))
    except Exception:
        pass
    bio = ""
    try:
        full = await client.get_chat(target.id)
        bio = getattr(full, "bio", None) or ""
    except Exception:
        pass
    lines = [
        smalls("✦ kişi bilgisi"),
        smalls("━━━━━━━━━━━━━━━━"),
        smalls(f"→ ad: {target.first_name or ''} {target.last_name or ''}".strip()),
        smalls(f"→ username: @{target.username or '-'}"),
        smalls(f"→ id: {target.id}"),
        smalls(f"→ bot mu: {'evet' if getattr(target,'is_bot',False) else 'hayır'}"),
    ]
    if status:
        lines.append(smalls(f"→ grup durumu: {status}"))
    if bio:
        lines.append(smalls(f"→ bio: {bio[:120]}"))
    await respond(client, message, "\n".join(lines))

@rate_limit(2)
async def chatinfo_handler(client: Client, message):
    chat = message.chat
    try:
        full = await client.get_chat(chat.id)
    except Exception:
        full = chat
    lines = [
        smalls("✦ sohbet bilgisi"),
        smalls("━━━━━━━━━━━━━━━━"),
        smalls(f"→ başlık: {getattr(full,'title',None) or getattr(chat,'title','-')}"),
        smalls(f"→ id: {chat.id}"),
        smalls(f"→ tip: {chat.type}"),
    ]
    # üye sayısı
    try:
        cnt = await client.get_chat_members_count(chat.id)
        lines.append(smalls(f"→ üyeler: {cnt}"))
    except Exception:
        pass
    desc = getattr(full, "description", None) or getattr(full, "bio", None)
    if desc:
        lines.append(smalls(f"→ açıklama: {desc[:120]}"))
    await respond(client, message, "\n".join(lines))

def register_handlers(app: Client):
    from pyrogram.handlers import MessageHandler
    flt = filters.me | filters.outgoing
    app.add_handler(MessageHandler(id_handler, filters.command(["id","chatid","userid"], prefixes=".") & flt))
    app.add_handler(MessageHandler(whois_handler, filters.command(["whois","info","kim"], prefixes=".") & flt))
    app.add_handler(MessageHandler(chatinfo_handler, filters.command(["chatinfo","grupbilgi"], prefixes=".") & flt))
