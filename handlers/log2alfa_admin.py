"""Log2 Alfa Admin — Pyrogram native, sade ve çalışan
Neden Asena admin çalışmıyordu?
→ Telethon EditBannedRequest / ChatBannedRights kullanıyordu, Pyrogram'da yok.
→ Bu sürüm Pyrogram client.ban_chat_member / restrict / promote kullanır, gerçekten çalışır.
"""
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, ChatAdminRequired, UserAdminInvalid, PeerIdInvalid
from pyrogram.enums import ChatMemberStatus
from utils.security import rate_limit
from utils.helpers import respond
from utils.fonts import smalls
import asyncio, re

def _is_group(chat) -> bool:
    t = getattr(chat, "type", None)
    if t is None:
        return False
    s = str(getattr(t, "value", None) or getattr(t, "name", None) or t).lower()
    return "group" in s

async def _get_target(client, message):
    # yanıt varsa onu al
    r = message.reply_to_message
    if r and r.from_user:
        return r.from_user
    # argüman varsa @user / id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return None
    q = args[1].strip().split()[0].lstrip("@")
    if not q:
        return None
    try:
        # id mi?
        if q.lstrip("-").isdigit():
            return await client.get_users(int(q))
        return await client.get_users(q)
    except Exception:
        try:
            # chat member'dan dene
            m = await client.get_chat_member(message.chat.id, q)
            return m.user
        except Exception:
            return None

def _need_admin_text():
    return smalls("→ yönetici değilim veya yetkim yok")

@rate_limit(2)
async def ban_handler(client: Client, message):
    if not _is_group(message.chat):
        await respond(client, message, smalls("→ sadece gruplarda"))
        return
    target = await _get_target(client, message)
    if not target:
        await respond(client, message, smalls("→ kullanım: .ban (yanıtla) veya .ban @user"))
        return
    try:
        await client.ban_chat_member(message.chat.id, target.id)
        await respond(client, message, smalls(f"→ banlandı: {target.first_name} ({target.id})"))
    except ChatAdminRequired:
        await respond(client, message, _need_admin_text())
    except UserAdminInvalid:
        await respond(client, message, smalls("→ yöneticiyi banlayamam"))
    except FloodWait as e:
        await respond(client, message, smalls(f"→ flood: {e.value}s bekle"))
    except Exception as e:
        await respond(client, message, smalls(f"→ hata: {e}"))

@rate_limit(2)
async def unban_handler(client: Client, message):
    if not _is_group(message.chat):
        await respond(client, message, smalls("→ sadece gruplarda"))
        return
    target = await _get_target(client, message)
    if not target:
        await respond(client, message, smalls("→ kullanım: .unban (yanıtla) veya .unban @user"))
        return
    try:
        await client.unban_chat_member(message.chat.id, target.id)
        await respond(client, message, smalls(f"→ ban kaldırıldı: {target.first_name}"))
    except Exception as e:
        await respond(client, message, smalls(f"→ hata: {e}"))

@rate_limit(2)
async def kick_handler(client: Client, message):
    if not _is_group(message.chat):
        await respond(client, message, smalls("→ sadece gruplarda"))
        return
    target = await _get_target(client, message)
    if not target:
        await respond(client, message, smalls("→ kullanım: .kick (yanıtla)"))
        return
    try:
        await client.ban_chat_member(message.chat.id, target.id)
        await asyncio.sleep(0.6)
        await client.unban_chat_member(message.chat.id, target.id)
        await respond(client, message, smalls(f"→ atıldı: {target.first_name}"))
    except Exception as e:
        await respond(client, message, smalls(f"→ hata: {e}"))

@rate_limit(2)
async def mute_handler(client: Client, message):
    if not _is_group(message.chat):
        await respond(client, message, smalls("→ sadece gruplarda"))
        return
    target = await _get_target(client, message)
    if not target:
        await respond(client, message, smalls("→ kullanım: .mute (yanıtla)"))
        return
    try:
        await client.restrict_chat_member(message.chat.id, target.id, permissions=message.chat.permissions if hasattr(message.chat,"permissions") else None)
        # basit: tüm yetkileri kapat
        from pyrogram.types import ChatPermissions
        await client.restrict_chat_member(message.chat.id, target.id, ChatPermissions(can_send_messages=False))
        await respond(client, message, smalls(f"→ susturuldu: {target.first_name}"))
    except Exception as e:
        await respond(client, message, smalls(f"→ hata: {e}"))

@rate_limit(2)
async def unmute_handler(client: Client, message):
    if not _is_group(message.chat):
        await respond(client, message, smalls("→ sadece gruplarda"))
        return
    target = await _get_target(client, message)
    if not target:
        await respond(client, message, smalls("→ kullanım: .unmute (yanıtla)"))
        return
    try:
        from pyrogram.types import ChatPermissions
        await client.restrict_chat_member(message.chat.id, target.id, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True))
        await respond(client, message, smalls(f"→ susturma kaldırıldı: {target.first_name}"))
    except Exception as e:
        await respond(client, message, smalls(f"→ hata: {e}"))

@rate_limit(2)
async def promote_handler(client: Client, message):
    if not _is_group(message.chat):
        await respond(client, message, smalls("→ sadece gruplarda"))
        return
    target = await _get_target(client, message)
    if not target:
        await respond(client, message, smalls("→ kullanım: .promote (yanıtla)"))
        return
    try:
        await client.promote_chat_member(message.chat.id, target.id, can_manage_chat=True, can_delete_messages=True, can_restrict_members=True, can_pin_messages=True)
        await respond(client, message, smalls(f"→ yönetici yapıldı: {target.first_name}"))
    except Exception as e:
        await respond(client, message, smalls(f"→ hata: {e}"))

@rate_limit(2)
async def demote_handler(client: Client, message):
    if not _is_group(message.chat):
        await respond(client, message, smalls("→ sadece gruplarda"))
        return
    target = await _get_target(client, message)
    if not target:
        await respond(client, message, smalls("→ kullanım: .demote (yanıtla)"))
        return
    try:
        await client.promote_chat_member(message.chat.id, target.id, can_manage_chat=False, can_delete_messages=False, can_restrict_members=False, can_pin_messages=False)
        await respond(client, message, smalls(f"→ yöneticilik alındı: {target.first_name}"))
    except Exception as e:
        await respond(client, message, smalls(f"→ hata: {e}"))

@rate_limit(2)
async def pin_handler(client: Client, message):
    if not _is_group(message.chat):
        await respond(client, message, smalls("→ sadece gruplarda"))
        return
    r = message.reply_to_message
    if not r:
        await respond(client, message, smalls("→ bir mesaja yanıtla: .pin"))
        return
    try:
        await client.pin_chat_message(message.chat.id, r.id, disable_notification=False)
        await respond(client, message, smalls("→ sabitlendi"))
        try: await message.delete()
        except: pass
    except Exception as e:
        await respond(client, message, smalls(f"→ hata: {e}"))

@rate_limit(3)
async def purge_handler(client: Client, message):
    # .purge / .del — yanıtlanan mesajdan bulunduğun yere kadar siler
    if not _is_group(message.chat):
        # özelde de çalışsın (kendi mesajlarını sil)
        pass
    r = message.reply_to_message
    if not r:
        await respond(client, message, smalls("→ bir mesaja yanıtla: .purge"))
        return
    start_id = r.id
    end_id = message.id
    ids = list(range(start_id, end_id+1))
    # Telegram tek seferde 100 silmeye izin verir
    deleted = 0
    for i in range(0, len(ids), 100):
        chunk = ids[i:i+100]
        try:
            await client.delete_messages(message.chat.id, chunk)
            deleted += len(chunk)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await client.delete_messages(message.chat.id, chunk)
                deleted += len(chunk)
            except Exception:
                pass
        except Exception as e:
            # parça parça dene
            for mid in chunk:
                try:
                    await client.delete_messages(message.chat.id, mid)
                    deleted += 1
                except Exception:
                    pass
        await asyncio.sleep(0.2)
    # rapor (sade: otomatik silinecek)
    try:
        m = await client.send_message(message.chat.id, smalls(f"→ {deleted} mesaj silindi"))
        await asyncio.sleep(3)
        await m.delete()
    except Exception:
        pass

def register_handlers(app: Client):
    from pyrogram.handlers import MessageHandler
    flt = filters.me | filters.outgoing
    app.add_handler(MessageHandler(ban_handler, filters.command(["ban"], prefixes=".") & flt))
    app.add_handler(MessageHandler(unban_handler, filters.command(["unban"], prefixes=".") & flt))
    app.add_handler(MessageHandler(kick_handler, filters.command(["kick"], prefixes=".") & flt))
    app.add_handler(MessageHandler(mute_handler, filters.command(["mute","sustur"], prefixes=".") & flt))
    app.add_handler(MessageHandler(unmute_handler, filters.command(["unmute","unsustur"], prefixes=".") & flt))
    app.add_handler(MessageHandler(promote_handler, filters.command(["promote","yap"], prefixes=".") & flt))
    app.add_handler(MessageHandler(demote_handler, filters.command(["demote","al"], prefixes=".") & flt))
    app.add_handler(MessageHandler(pin_handler, filters.command(["pin","sabitle"], prefixes=".") & flt))
    app.add_handler(MessageHandler(purge_handler, filters.command(["purge","del","sil"], prefixes=".") & flt))
