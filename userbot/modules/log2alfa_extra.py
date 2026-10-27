"""Log2 Alfa Extra — eksik komutları tamamlar (medya, yönetim aliasları) — Telethon uyumlu"""
import re
import asyncio
import os
import requests
from userbot.events import register
from userbot.cmdhelp import CmdHelp
from userbot import CMD_HELP
from telethon.tl import functions
from telethon.tl.functions.users import GetFullUserRequest

def _parse_tme_link(link: str):
    link = link.strip()
    link = re.sub(r'^https?://', '', link)
    link = link.replace('t.me/', '').strip('/')
    parts = link.split('/')
    if len(parts) == 2:
        chat = parts[0]
        try: msg_id = int(parts[1])
        except: return None, None
        return chat, msg_id
    elif len(parts) == 3 and parts[0] == 'c':
        try:
            chat_id = int("-100" + parts[1])
            msg_id = int(parts[2])
            return chat_id, msg_id
        except: return None, None
    return None, None

# ========== MEDYA ==========
@register(outgoing=True, pattern=r"^\.save(?: |$)(\S.*)?")
async def save_media(event):
    text = (event.text or "").strip()
    m = re.search(r'(https?://t\.me/[^\s]+|t\.me/[^\s]+)', text)
    if m:
        link = m.group(1)
        chat, msg_id = _parse_tme_link(link)
        if chat is None:
            await event.edit("`Link hatalı. Örn: t.me/kanal/123 veya t.me/c/123456/789`")
            return
        await event.edit("`Medya alınıyor...`")
        try:
            msg = await event.client.get_messages(chat, ids=msg_id)
            if not msg or (not getattr(msg, 'media', None) and not getattr(msg, 'text', None) and not getattr(msg, 'message', None)):
                await event.edit("`Mesaj bulunamadı veya medya yok.`")
                return
            if getattr(msg, 'media', None):
                path = await event.client.download_media(msg)
                if path:
                    cap = getattr(msg, 'text', None) or getattr(msg, 'message', None) or ""
                    await event.client.send_file(event.chat_id, path, caption=cap)
                    try: os.remove(path)
                    except: pass
                    await event.delete()
                    return
            txt = getattr(msg, 'text', None) or getattr(msg, 'message', None) or "`Boş mesaj`"
            await event.client.send_message(event.chat_id, txt)
            await event.delete()
            return
        except Exception as e:
            await event.edit(f"`Kaydedilemedi: {e}`")
            return
    if event.reply_to_msg_id:
        try:
            rmsg = await event.get_reply_message()
            arg = text[5:].strip() if len(text) > 5 else ""
            is_note_like = bool(re.match(r'^\w+$', arg)) and rmsg and (getattr(rmsg, 'text', None) or getattr(rmsg, 'message', None)) and not getattr(rmsg, 'media', None)
            if rmsg and getattr(rmsg, 'media', None):
                await event.edit("`Medya kaydediliyor...`")
                path = await event.client.download_media(rmsg)
                if path:
                    cap = getattr(rmsg, 'text', None) or getattr(rmsg, 'message', None) or ""
                    await event.client.send_file(event.chat_id, path, caption=cap)
                    try: os.remove(path)
                    except: pass
                    await event.delete()
                    return
                await event.edit("`İndirilemedi.`")
                return
            if is_note_like:
                return
        except Exception:
            return
    return

@register(outgoing=True, pattern=r"^\.dlmedia$")
async def dlmedia(event):
    if not event.reply_to_msg_id:
        await event.edit("`Bir medyaya yanıt ver. Örn: .dlmedia (reply)`")
        return
    await event.edit("`İndiriliyor...`")
    try:
        rmsg = await event.get_reply_message()
        if not rmsg or not getattr(rmsg, 'media', None):
            await event.edit("`Medya bulunamadı.`")
            return
        path = await event.client.download_media(rmsg)
        if path:
            cap = getattr(rmsg, 'text', None) or getattr(rmsg, 'message', None) or "✅ kaydedildi"
            await event.client.send_file(event.chat_id, path, caption=cap)
            try: os.remove(path)
            except: pass
            await event.delete()
        else:
            await event.edit("`İndirilemedi.`")
    except Exception as e:
        await event.edit(f"`Hata: {e}`")

# ========== YÖNETİM ALIASLARI ==========
@register(outgoing=True, pattern=r"^\.unpin(?: |$)(.*)")
async def unpin(event):
    try:
        from telethon.tl.functions.messages import UpdatePinnedMessage
        if not event.reply_to_msg_id:
            # tüm sabitleri kaldır
            await event.client(UpdatePinnedMessage(peer=event.chat_id, id=0, unpin=True))
            await event.edit("`Sabit kaldırıldı.`")
            await asyncio.sleep(2)
            try: await event.delete()
            except: pass
            return
        await event.client(UpdatePinnedMessage(peer=event.chat_id, id=event.reply_to_msg_id, unpin=True))
        await event.edit("`Yanıtlanan sabit kaldırıldı.`")
        await asyncio.sleep(1)
        try: await event.delete()
        except: pass
    except Exception as e:
        await event.edit(f"`Kaldırılamadı: {e}`")

@register(outgoing=True, pattern=r"^\.warns(?: |$)(.*)")
async def warns(event):
    try:
        from userbot.modules.sql_helper.warn_sql import getir_warn
        from userbot.modules.admin import get_user_from_event
        user, _ = await get_user_from_event(event)
        if not user:
            await event.edit("`Kullanıcı bulunamadı.`")
            return
        cnt = getir_warn(user.id)
        await event.edit(f"[{user.first_name}](tg://user?id={user.id}) uyarı sayısı: `{cnt}/3`")
    except Exception as e:
        await event.edit(f"`Hata: {e}`")

@register(outgoing=True, pattern=r"^\.delnote(?: |$)(\w*)")
async def delnote(event):
    kw = event.pattern_match.group(1).strip() if event.pattern_match else ""
    if not kw:
        await event.edit("`Kullanım: .delnote <not adı>`")
        return
    try:
        from userbot.modules.sql_helper.notes_sql import rm_note
        if rm_note(event.chat_id, kw) is False:
            await event.edit(f"`{kw} bulunamadı.`")
        else:
            await event.edit(f"`{kw} silindi.`")
    except Exception as e:
        await event.edit(f"`Hata: {e}`")

@register(outgoing=True, pattern=r"^\.get(?: |$)(\w*)")
async def getnote(event):
    kw = event.pattern_match.group(1).strip() if event.pattern_match else ""
    if not kw:
        await event.edit("`Kullanım: .get <not adı>`")
        return
    try:
        from userbot.modules.sql_helper.notes_sql import get_note
        note = get_note(event.chat_id, kw)
        if not note:
            await event.edit(f"`{kw} bulunamadı.`")
            return
        if note.f_mesg_id:
            try:
                from userbot import BOTLOG_CHATID
                msg_o = await event.client.get_messages(BOTLOG_CHATID, ids=int(note.f_mesg_id))
                if msg_o and getattr(msg_o, 'media', None):
                    path = await event.client.download_media(msg_o)
                    if path:
                        await event.client.send_file(event.chat_id, path, caption=note.reply or "")
                        try: os.remove(path)
                        except: pass
                        try: await event.delete()
                        except: pass
                        return
                await event.client.send_message(event.chat_id, note.reply or "`Boş not`")
                try: await event.delete()
                except: pass
                return
            except Exception as e:
                await event.edit(f"`Get hata: {e}`")
                return
        await event.edit(note.reply or "`Boş not`")
    except Exception as e:
        await event.edit(f"`Hata: {e}`")

# ========== BİLGİ ALIASLARI ==========
@register(outgoing=True, pattern=r"^\.id(?: |$)(.*)")
async def idcmd(event):
    rmsg = await event.get_reply_message()
    if rmsg:
        try:
            uid = rmsg.sender.id if getattr(rmsg, 'sender', None) else getattr(rmsg, 'sender_id', None) or event.chat_id
        except:
            uid = getattr(rmsg, 'sender_id', event.chat_id)
        try:
            name = rmsg.sender.first_name if getattr(rmsg, 'sender', None) else "Kullanıcı"
        except:
            name = "Kullanıcı"
        await event.edit(f"**{name}** ID: `{uid}` | Chat: `{event.chat_id}` | Msg: `{rmsg.id}`")
    else:
        me = await event.client.get_me()
        await event.edit(f"Sen ID: `{me.id}` | Chat: `{event.chat_id}`")

@register(outgoing=True, pattern=r"^\.info(?: |$)(.*)")
async def infocmd(event):
    try:
        await event.edit("`Bilgi alınıyor...`")
        rmsg = await event.get_reply_message()
        user = None
        if rmsg and getattr(rmsg, 'sender', None):
            user = rmsg.sender
        else:
            arg = event.pattern_match.group(1).strip() if event.pattern_match else ""
            if arg:
                try:
                    if arg.isdigit():
                        user = await event.client.get_entity(int(arg))
                    else:
                        user = await event.client.get_entity(arg)
                except: pass
            if not user:
                user = await event.client.get_me()
        try:
            full = await event.client(GetFullUserRequest(user.id if hasattr(user, 'id') else user))
            u = full.user if hasattr(full, 'user') else user
            bio = getattr(full, 'about', '') if hasattr(full, 'about') else ''
            text = f"**{getattr(u, 'first_name', '')}** @{getattr(u, 'username', '-')}\nID: `{u.id}`\nBio: {bio or '-'}"
            await event.edit(text)
        except Exception as e:
            await event.edit(f"`info hata: {e}`")
    except Exception as e:
        await event.edit(f"`Hata: {e}`")

@register(outgoing=True, pattern=r"^\.chatinfo$")
async def chatinfo(event):
    try:
        chat = await event.get_chat()
        title = getattr(chat, 'title', '') or getattr(event.chat, 'title', '')
        cid = event.chat_id
        count = getattr(chat, 'participants_count', 'Bilinmiyor')
        text = f"**{title}**\nID: `{cid}`\nÜye: `{count}`\nTip: `{chat.__class__.__name__}`"
        await event.edit(text)
    except Exception as e:
        await event.edit(f"`chatinfo hata: {e}`")

@register(outgoing=True, pattern=r"^\.hava(?: |$)(.*)")
async def hava(event):
    city = event.pattern_match.group(1).strip() if event.pattern_match else ""
    if not city:
        await event.edit("`Kullanım: .hava <şehir>`")
        return
    try:
        await event.edit(f"`{city} için hava alınıyor...`")
        from userbot import OPEN_WEATHER_MAP_APPID as OWM_API
        if not OWM_API:
            await event.edit("`OWM API yok.`")
            return
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OWM_API}&lang=tr&units=metric"
        r = requests.get(url, timeout=10)
        j = r.json()
        if j.get("cod") != 200:
            await event.edit(f"`Şehir bulunamadı: {city}`")
            return
        main = j["main"]
        w = j["weather"][0]
        await event.edit(f"**{city}** — {w['description'].title()}\nSıcaklık: `{main['temp']}°C` Hissedilen: `{main['feels_like']}°C`\nNem: `{main['humidity']}%`")
    except Exception as e:
        await event.edit(f"`hava hata: {e}`")

@register(outgoing=True, pattern=r"^\.log2alfa$|^\.alfa$|^\.log2$")
async def log2alfa_cmd(event):
    try:
        from userbot.modules.system_stats import amialive
        await amialive(event)
    except Exception as e:
        try: await event.edit("✅ **Log2Alfa aktif** — `.ping` ile test et")
        except: pass

@register(outgoing=True, pattern=r"^\.phelp(?: |$)(.*)")
async def phelp(event):
    arg = event.pattern_match.group(1).strip() if event.pattern_match else ""
    try:
        all_cmds = sorted(CMD_HELP.keys())
        if not all_cmds:
            await event.edit("`Plugin yok.`")
            return
        if arg and arg.isdigit():
            page = int(arg)
            per = 50
            total = (len(all_cmds) + per -1)//per
            page = max(1, min(page, total))
            start = (page-1)*per
            chunk = all_cmds[start:start+per]
            txt = f"**Pluginler ({len(all_cmds)}) — Sayfa {page}/{total}**\n\n"
            for k in chunk:
                txt += f"• `{k}`\n"
            txt += f"\n`.phelp <sayı>` ile sayfa değiştir"
            await event.edit(txt)
            return
        if arg and arg in CMD_HELP:
            await event.edit(CMD_HELP[arg])
            return
        per = 50
        chunk = all_cmds[:per]
        txt = f"**Pluginler ({len(all_cmds)}) — Sayfa 1**\n\n"
        for k in chunk:
            txt += f"• `{k}`\n"
        txt += f"\n`.phelp <plugin>` detay, `.phelp 2` sonraki sayfa"
        await event.edit(txt)
    except Exception as e:
        await event.edit(f"`phelp hata: {e}`")

CmdHelp('log2alfa_extra')  # Log2 Alfa.add_command('save', '<link> / (reply)', 'Kısıtlı dahil medyayı kaydet').add_command('dlmedia', '(reply)', 'Medyayı indir').add_command('hava', '<şehir>', 'Hava durumu (.weather alias)').add_command('id', '(reply)', 'ID göster').add_command('info', '(reply|@u)', 'Kullanıcı bilgisi (.whois)').add_command('chatinfo', None, 'Grup bilgisi').add_command('unpin', '(reply)', 'Sabit kaldır').add_command('warns', '[reply/@u]', 'Uyarı sayısını göster').add_command('delnote', '<ad>', 'Not sil (.clear alias)').add_command('get', '<ad>', 'Not getir').add_command('log2alfa', None, 'Durum (.alive)').add_command('phelp', '[sayı|ad]', 'Plugin listesi').add()
