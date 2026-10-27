# Copyright (C) 2019 The Raphielscape Company LLC.
# Log2 Alfa Fix v2 — ultra güvenli purge (asla tüm hesap / DM / bot geçmişi silinmez)

from asyncio import sleep
from telethon.errors import rpcbaseerrors

from userbot import BOTLOG, BOTLOG_CHATID, CMD_HELP
from userbot.events import register
from userbot.cmdhelp import CmdHelp
from userbot.language import get_value
LANG = get_value("purge")

# Sadece grup/süpergrup/kanalda purge serbest, DM ve botlarda yasak
def _is_private(event):
    try:
        if getattr(event, "is_private", False):
            return True
        # fallback: chat.type kontrol
        chat = getattr(event, "chat", None)
        if chat:
            t = str(getattr(chat, "type", "")).lower()
            if "private" in t or "bot" in t:
                return True
            # chat.id pozitif ve 9 haneli gibi küçükse kullanıcı DM olabilir (gruplar negatif)
            # ama Pyrogram'da DM id pozitif, grup negatif
            cid = getattr(event, "chat_id", None)
            if isinstance(cid, int) and cid > 0 and cid < 10**13:
                # Ek kontrol: is_group false ise private
                if not getattr(event, "is_group", False):
                    return True
    except:
        pass
    return False

def _is_bot_chat(event):
    try:
        chat = getattr(event, "chat", None)
        if chat and getattr(chat, "is_bot", False):
            return True
        # kullanıcının kendisiyle mesajlaşma (Saved Messages)
        try:
            me = event.client.get_me()
            # bu async değil, burada çağıramayız, sadece id karşılaştırma
        except:
            pass
    except:
        pass
    return False

@register(outgoing=True, pattern="^.purge$")
async def fastpurger(purg):
    """ .purge — sadece bulunduğun grup/kanalda, yanıtladığın mesajdan itibaren siler. DM/bot geçmişine asla dokunmaz. """
    # DM / özel sohbet koruması
    if _is_private(purg):
        await purg.edit("❌ `DM ve bot sohbetlerinde .purge yasak — sadece gruplarda çalışır.`")
        return
    if purg.reply_to_msg_id is None:
        await purg.edit(LANG['NEED_MSG'])
        return
    chat_id = purg.chat_id
    # Bot log kanalı koruması
    try:
        if BOTLOG_CHATID and int(chat_id) == int(BOTLOG_CHATID):
            await purg.edit("❌ `Log kanalında purge yasak.`")
            return
    except:
        pass
    reply_id = purg.reply_to_msg_id
    end_id = purg.id
    if reply_id > end_id:
        reply_id, end_id = end_id, reply_id
    ids = list(range(reply_id, end_id + 1))
    # Güvenlik limiti: tek seferde max 50 mesaj, fazlası için uyar
    if len(ids) > 50:
        await purg.edit(f"⚠️ `Çok fazla mesaj ({len(ids)}). Güvenlik için max 50. Daha küçük aralıkla dene — yanıtladığın mesajı daha yakına al.`")
        return
    if len(ids) > 1000:
        print(f"purge block large {len(ids)} in {chat_id}", flush=True)
        return
    deleted = 0
    for i in range(0, len(ids), 100):
        chunk = ids[i:i+100]
        try:
            await purg.client.delete_messages(chat_id, chunk)
            deleted += len(chunk)
            await sleep(0.4)
        except rpcbaseerrors.BadRequestError as e:
            print(f"purge BadRequest {e}", flush=True)
            break
        except Exception as e:
            print(f"purge hata {e}", flush=True)
            break
    try:
        done = await purg.client.send_message(chat_id, LANG['PURGED'].format(str(deleted)))
        if BOTLOG:
            try:
                await purg.client.send_message(BOTLOG_CHATID, f"purge {deleted} mesaj silindi (chat {chat_id}, range {reply_id}-{end_id})")
            except:
                pass
        await sleep(2)
        try: await done.delete()
        except: pass
    except Exception as e:
        print(f"purge done hata {e}", flush=True)


@register(outgoing=True, pattern="^.purgeme")
async def purgeme(delme):
    """ .purgeme <sayı> — sadece o grupta kendi mesajlarını siler, DM'de 5 ile sınırlı. """
    message = delme.text or ""
    try:
        parts = message.split(maxsplit=1)
        if len(parts) < 2:
            await delme.edit("`Kaç mesaj silinecek? Örn: .purgeme 5`")
            return
        count = int(parts[1].strip())
    except:
        await delme.edit("`Sayı hatalı. Örn: .purgeme 5`")
        return
    if count <= 0 or count > 50:
        await delme.edit("`1-50 arası gir (güvenlik limiti).`")
        return
    # DM'de çok daha sıkı
    if _is_private(delme) and count > 5:
        await delme.edit("`DM'de max 5.`")
        return
    chat_id = delme.chat_id
    try:
        if BOTLOG_CHATID and int(chat_id) == int(BOTLOG_CHATID):
            await delme.edit("`Log kanalında yasak.`")
            return
    except: pass
    try:
        me = await delme.client.get_me()
        my_id = me.id
    except:
        my_id = delme.sender_id
    to_delete = []
    try:
        async for msg in delme.client.get_chat_history(chat_id, limit=300):
            try:
                fid = getattr(msg.from_user, "id", None) if getattr(msg, "from_user", None) else None
                is_me = (fid == my_id) or getattr(msg, "outgoing", False)
                if is_me:
                    to_delete.append(msg.id)
                    if len(to_delete) >= count:
                        break
            except: continue
    except Exception as e:
        print(f"purgeme history hata {e}", flush=True)
    if not to_delete:
        await delme.edit("`Silinecek kendi mesajın bulunamadı.`")
        return
    # komutun kendisi zaten to_delete içinde olabilir, değilse ekle ama sayıyı aşma
    try:
        if delme.id not in to_delete and len(to_delete) < count + 1:
            to_delete.append(delme.id)
    except: pass
    deleted = 0
    for i in range(0, len(to_delete), 100):
        chunk = to_delete[i:i+100]
        try:
            await delme.client.delete_messages(chat_id, chunk)
            deleted += len(chunk)
            await sleep(0.3)
        except Exception as e:
            print(f"purgeme sil hata {e}", flush=True)
            break
    try:
        smsg = await delme.client.send_message(chat_id, LANG['PURGED_ME'].format(str(deleted)))
        if BOTLOG:
            try: await delme.client.send_message(BOTLOG_CHATID, f"purgeme {deleted} silindi (chat {chat_id})")
            except: pass
        await sleep(2)
        try: await smsg.delete()
        except: pass
    except Exception as e:
        print(f"purgeme done hata {e}", flush=True)


@register(outgoing=True, pattern="^.del$")
async def delete_it(delme):
    """ .del — sadece yanıtlanan 1 mesaj + komutunu siler, asla toplu silmez. """
    # DM koruması: DM'de de 1 mesaj silmek serbest ama toplu değil — zaten 1
    if delme.reply_to_msg_id is None:
        await delme.edit("`Silmek için bir mesaja yanıt ver.`")
        await sleep(2)
        try: await delme.delete()
        except: pass
        return
    msg_src = await delme.get_reply_message()
    if not msg_src:
        await delme.edit("`Mesaj bulunamadı.`")
        return
    # Güvenlik: log kanalı mesajını silme
    try:
        if BOTLOG_CHATID and int(delme.chat_id) == int(BOTLOG_CHATID):
            await delme.edit("`Log kanalında del yasak.`")
            return
    except: pass
    try:
        await msg_src.delete()
        await delme.delete()
        if BOTLOG:
            try: await delme.client.send_message(BOTLOG_CHATID, "del: 1 mesaj silindi")
            except: pass
    except rpcbaseerrors.BadRequestError:
        try: await delme.edit("`Bu mesajı silemiyorum.`")
        except: pass
        await sleep(2)
        try: await delme.delete()
        except: pass
    except Exception as e:
        print(f"del hata {e}", flush=True)


@register(outgoing=True, pattern="^.edit")
async def editer(edit):
    """ .edit <yeni mesaj> — son kendi mesajını düzenler. """
    message = edit.text or ""
    try:
        string = message.split(maxsplit=1)[1] if len(message.split(maxsplit=1)) > 1 else ""
    except:
        string = ""
    if not string:
        await edit.edit("`Yeni mesajı yaz. Örn: .edit merhaba`")
        return
    chat = edit.chat_id
    try:
        me = await edit.client.get_me()
        my_id = me.id
    except:
        my_id = edit.sender_id
    found = None
    try:
        async for msg in edit.client.get_chat_history(chat, limit=20):
            try:
                fid = getattr(msg.from_user, "id", None) if getattr(msg, "from_user", None) else None
                is_me = (fid == my_id) or getattr(msg, "outgoing", False)
                if is_me and msg.id != edit.id:
                    found = msg
                    break
            except: continue
    except Exception as e:
        print(f"edit history hata {e}", flush=True)
    if found:
        try:
            await edit.client.edit_message_text(chat, found.id, string)
            try: await edit.delete()
            except: pass
            if BOTLOG:
                try: await edit.client.send_message(BOTLOG_CHATID, "edit yapıldı")
                except: pass
        except Exception as e:
            await edit.edit(f"Düzenlenemedi: {e}")
    else:
        await edit.edit("`Düzenlenecek mesaj bulunamadı.`")


@register(outgoing=True, pattern="^.sd")
async def selfdestruct(destroy):
    """ .sd <süre> <mesaj> — kendini yok eden mesaj. """
    message = destroy.text or ""
    try:
        parts = message.split(maxsplit=2)
        counter = int(parts[1]) if len(parts) > 1 else 0
        text = parts[2] if len(parts) > 2 else ""
    except:
        await destroy.edit("`Kullanım: .sd <süre> <mesaj> Örn: .sd 5 merhaba`")
        return
    if counter <= 0 or counter > 60:
        await destroy.edit("`Süre 1-60 saniye olmalı.`")
        return
    if not text:
        await destroy.edit("`Mesaj boş olamaz.`")
        return
    try: await destroy.delete()
    except: pass
    try:
        smsg = await destroy.client.send_message(destroy.chat_id, text)
        await sleep(counter)
        try: await smsg.delete()
        except: pass
        if BOTLOG:
            try: await destroy.client.send_message(BOTLOG_CHATID, "sd tamamlandı")
            except: pass
    except Exception as e:
        print(f"sd hata {e}", flush=True)

CmdHelp('purge').add_command(
    'purge', None, 'Yanıtladığın mesajdan itibaren sadece o grupta en fazla 50 mesaj siler (DM/bot korumalı).'
).add_command(
    'purgeme', '<sayı>', 'Sadece o grupta kendi mesajlarını siler (DM max 5, grup max 50).'
).add_command(
    'del', None, 'Yanıtlanan 1 mesajı siler (toplu silmez).'
).add_command(
    'edit', '<yeni mesaj>', 'Son kendi mesajını düzenler.'
).add_command(
    'sd', '<x> <mesaj>', 'x saniyede yok olan mesaj.'
).add()
