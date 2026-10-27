"""Log2 Alfa Extra Pyro — eksik komutlar için Pyrogram native tamamlayıcı
Yeni eklenen: .purgeme, .unpin, .warns, .delnote, .get, .save, .dlmedia, .edit, .sd
Hepsi Pyrogram API ile, aynı davranış Telethon'daki gibi.
"""
import re, asyncio, os, requests
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from utils.security import rate_limit
from utils.helpers import respond
from utils.fonts import smalls

# helper: t.me link parse
def _parse_tme(link: str):
    link = link.strip()
    link = re.sub(r'^https?://', '', link)
    link = link.replace('t.me/', '').strip('/')
    parts = link.split('/')
    if len(parts) == 2:
        chat = parts[0]
        try: mid = int(parts[1])
        except: return None, None
        return chat, mid
    elif len(parts) == 3 and parts[0] == 'c':
        try:
            cid = int("-100" + parts[1])
            mid = int(parts[2])
            return cid, mid
        except: return None, None
    return None, None

# ========== PURGEME ==========
@rate_limit(2)
async def purgeme_handler(client: Client, message):
    txt = message.text or ""
    parts = txt.split(maxsplit=1)
    if len(parts) < 2:
        await respond(client, message, smalls("→ kullanım: .purgeme <sayı>  (örn: .purgeme 5)"))
        return
    try:
        count = int(parts[1].strip().split()[0])
    except:
        await respond(client, message, smalls("→ sayı hatalı. örn: .purgeme 5"))
        return
    if count <=0 or count>50:
        await respond(client, message, smalls("→ 1-50 arası gir"))
        return
    # DM'de 5 ile sınırlı (güvenlik)
    is_private = message.chat and str(message.chat.type).lower()=="private"
    if is_private and count>5:
        await respond(client, message, smalls("→ dm'de max 5"))
        return
    try:
        me = await client.get_me()
        my_id = me.id
    except:
        my_id = message.from_user.id if message.from_user else 0
    to_delete=[]
    try:
        async for msg in client.get_chat_history(message.chat.id, limit=300):
            try:
                fid = getattr(msg.from_user, "id", None) if getattr(msg, "from_user", None) else None
                is_me = (fid==my_id) or getattr(msg, "outgoing", False)
                if is_me:
                    to_delete.append(msg.id)
                    if len(to_delete)>=count:
                        break
            except: continue
    except Exception as e:
        print(f"purgeme history hata {e}", flush=True)
    if not to_delete:
        await respond(client, message, smalls("→ silinecek kendi mesajın yok"))
        return
    # komutun kendisi de silinsin
    if message.id not in to_delete:
        to_delete.append(message.id)
    # sil
    deleted=0
    for i in range(0, len(to_delete), 100):
        chunk = to_delete[i:i+100]
        try:
            await client.delete_messages(message.chat.id, chunk)
            deleted+=len(chunk)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await client.delete_messages(message.chat.id, chunk)
                deleted+=len(chunk)
            except: pass
        except Exception as e:
            print(f"purgeme sil hata {e}", flush=True)
        await asyncio.sleep(0.2)
    try:
        m = await client.send_message(message.chat.id, smalls(f"→ {deleted} mesaj silindi"))
        await asyncio.sleep(2)
        try: await m.delete()
        except: pass
    except: pass

# ========== UNPIN ==========
@rate_limit(2)
async def unpin_handler(client: Client, message):
    r = message.reply_to_message
    try:
        if r:
            await client.unpin_chat_message(message.chat.id, r.id)
            await respond(client, message, smalls("→ yanıtlanan sabit kaldırıldı"))
            try: await message.delete()
            except: pass
        else:
            # son pin kaldır / tümünü kaldır
            await client.unpin_chat_message(message.chat.id)
            await respond(client, message, smalls("→ sabit kaldırıldı"))
            await asyncio.sleep(2)
            try: await message.delete()
            except: pass
    except Exception as e:
        await respond(client, message, smalls(f"→ kaldırılamadı: {e}"))

# ========== WARNS ==========
@rate_limit(2)
async def warns_handler(client: Client, message):
    # hedef kullanıcı
    target=None
    r = message.reply_to_message
    if r and r.from_user:
        target=r.from_user
    else:
        args = message.text.split(maxsplit=1)
        if len(args)>1:
            q=args[1].strip().split()[0].lstrip("@")
            if q:
                try:
                    if q.isdigit():
                        target=await client.get_users(int(q))
                    else:
                        target=await client.get_users(q)
                except: pass
    if not target:
        # kendisi
        try:
            target=await client.get_me()
        except:
            await respond(client, message, smalls("→ kullanıcı bulunamadı"))
            return
    try:
        from userbot.modules.sql_helper.warn_sql import getir_warn
        cnt = getir_warn(target.id)
        await respond(client, message, smalls(f"→ {target.first_name} uyarı: {cnt}/3"))
    except Exception as e:
        # alternatif: direkt db sorgu
        try:
            import sqlite3
            conn=sqlite3.connect("log2alfa.db")
            cur=conn.cursor()
            cur.execute("SELECT num_warn FROM warns WHERE user_id=?", (target.id,))
            row=cur.fetchone()
            cnt=row[0] if row else 0
            conn.close()
            await respond(client, message, smalls(f"→ {target.first_name} uyarı: {cnt}/3"))
        except Exception as e2:
            await respond(client, message, smalls(f"→ hata: {e} / {e2}"))

# ========== NOTES: delnote / get ==========
@rate_limit(2)
async def delnote_handler(client: Client, message):
    args = message.text.split(maxsplit=1)
    if len(args)<2 or not args[1].strip():
        await respond(client, message, smalls("→ kullanım: .delnote <ad>"))
        return
    kw=args[1].strip().split()[0]
    try:
        from userbot.modules.sql_helper.notes_sql import rm_note
        if rm_note(message.chat.id, kw) is False:
            await respond(client, message, smalls(f"→ {kw} bulunamadı"))
        else:
            await respond(client, message, smalls(f"→ {kw} silindi"))
    except Exception as e:
        await respond(client, message, smalls(f"→ hata: {e}"))

@rate_limit(2)
async def getnote_handler(client: Client, message):
    args = message.text.split(maxsplit=1)
    if len(args)<2 or not args[1].strip():
        await respond(client, message, smalls("→ kullanım: .get <ad>"))
        return
    kw=args[1].strip().split()[0]
    try:
        from userbot.modules.sql_helper.notes_sql import get_note
        note=get_note(message.chat.id, kw)
        if not note:
            await respond(client, message, smalls(f"→ {kw} bulunamadı"))
            return
        # f_mesg_id varsa BOTLOG'dan al
        if getattr(note, 'f_mesg_id', None):
            try:
                from config import DATABASE_PATH
                import asyncio
                # BOTLOG_CHATID env'den al
                import os
                botlog = os.getenv("BOTLOG_CHATID") or os.getenv("LOG_CHANNEL") or ""
                # notes_sql f_mesg_id BOTLOG'da saklar, ama Pyrogram'da o kanala erişim gerek
                # direkt reply gönder
                # önce download dene
                # fallback: text reply
                if note.reply:
                    await respond(client, message, note.reply)
                else:
                    await respond(client, message, smalls("→ boş not"))
                return
            except Exception as e:
                await respond(client, message, smalls(f"→ get hata: {e}"))
                return
        await respond(client, message, note.reply or smalls("→ boş not"))
    except Exception as e:
        await respond(client, message, smalls(f"→ hata: {e}"))

# ========== MEDYA: save / dlmedia ==========
@rate_limit(2)
async def save_handler(client: Client, message):
    text = message.text or ""
    # link var mı?
    m=re.search(r'(https?://t\.me/[^\s]+|t\.me/[^\s]+)', text)
    if m:
        link=m.group(1)
        chat, mid=_parse_tme(link)
        if chat is None:
            await respond(client, message, smalls("→ link hatalı. örn: t.me/kanal/123 veya t.me/c/12345/678"))
            return
        await respond(client, message, smalls("→ medya alınıyor..."))
        try:
            # Pyrogram get_messages
            try:
                # chat username veya -100 id
                msg = await client.get_messages(chat, message_ids=mid)
            except Exception as e:
                # fallback: try with int chat
                try:
                    msg = await client.get_messages(int(chat) if str(chat).lstrip("-").isdigit() else chat, message_ids=mid)
                except:
                    raise e
            if not msg or (not getattr(msg, 'media', None) and not getattr(msg, 'text', None) and not getattr(msg, 'caption', None)):
                await respond(client, message, smalls("→ mesaj bulunamadı veya medya yok"))
                return
            if getattr(msg, 'media', None):
                # download
                path = await client.download_media(msg)
                if path:
                    cap = getattr(msg, 'caption', None) or getattr(msg, 'text', None) or ""
                    # send accordingly
                    if getattr(msg, 'photo', None):
                        await client.send_photo(message.chat.id, path, caption=cap)
                    elif getattr(msg, 'video', None):
                        await client.send_video(message.chat.id, path, caption=cap)
                    elif getattr(msg, 'document', None):
                        await client.send_document(message.chat.id, path, caption=cap)
                    elif getattr(msg, 'audio', None):
                        await client.send_audio(message.chat.id, path, caption=cap)
                    elif getattr(msg, 'voice', None):
                        await client.send_voice(message.chat.id, path, caption=cap)
                    else:
                        await client.send_document(message.chat.id, path, caption=cap)
                    try: os.remove(path)
                    except: pass
                    try: await message.delete()
                    except: pass
                    return
            # text
            txt = getattr(msg, 'text', None) or getattr(msg, 'caption', None) or "boş"
            await client.send_message(message.chat.id, txt)
            try: await message.delete()
            except: pass
            return
        except Exception as e:
            await respond(client, message, smalls(f"→ kaydedilemedi: {e}"))
            return
    # link yok, reply medya mı? (kısıtlı bypass)
    r=message.reply_to_message
    if r and getattr(r, 'media', None):
        # Not: .save yalnızca medya içindir.
        _args = (text or "").split(maxsplit=1)
        if len(_args) > 1 and _args[1].strip():
            await respond(client, message, smalls("→ kullanım: .save (medyaya yanıtla)  |  .save <t.me/link>"))
            return
        await respond(client, message, smalls("→ medya kaydediliyor..."))
        try:
            path=await client.download_media(r)
            if path:
                cap=getattr(r, 'caption', None) or getattr(r, 'text', None) or ""
                # tipine göre gönder
                if getattr(r, 'photo', None):
                    await client.send_photo(message.chat.id, path, caption=cap)
                elif getattr(r, 'video', None):
                    await client.send_video(message.chat.id, path, caption=cap)
                elif getattr(r, 'document', None):
                    await client.send_document(message.chat.id, path, caption=cap)
                else:
                    await client.send_document(message.chat.id, path, caption=cap)
                try: os.remove(path)
                except: pass
                try: await message.delete()
                except: pass
                return
            await respond(client, message, smalls("→ indirilemedi"))
            return
        except Exception as e:
            await respond(client, message, smalls(f"→ hata: {e}"))
            return
    # yanıtta medya yok + tek kelime argüman → not kaydı (uyumluluk)
    # eski alışkanlık: .save <ad> (metin yanıtı) -> not kaydet (asıl komut .nsave)
    if r:
        args = text.split(maxsplit=1)
        # .save veya .save <ad>
        kw=None
        if len(args)>1:
            # ilk kelimeyi al, link değilse
            cand=args[1].strip().split()[0]
            if cand and not cand.startswith("http") and "t.me" not in cand:
                # tek kelime mi?
                if re.match(r'^\w+$', cand):
                    kw=cand
        if kw:
            # not kaydet — ortak notlar modülü (.nsave ile aynı tablo, medya destekli)
            try:
                from handlers.log2alfa_notes import _save as _note_save, _norm as _note_norm
                _reply_text = getattr(r, 'text', None) or getattr(r, 'caption', None) or None
                _fid = _mtype = None
                for _k, _a in (("photo","photo"),("video","video"),("animation","animation"),
                               ("audio","audio"),("voice","voice"),("document","document"),("sticker","sticker")):
                    _o = getattr(r, _a, None)
                    if _o is not None:
                        _fid, _mtype = getattr(_o, "file_id", None), _k
                        break
                await _note_save(message.chat.id, _note_norm(kw), _reply_text, _fid, _mtype)
                await respond(client, message, smalls(f"→ not kaydedildi: #{kw}"))
                return
            except Exception as e:
                print(f"save→not devri hata: {e}", flush=True)
                pass
    # hiçbir şey değilse yardım
    await respond(client, message, smalls("→ kullanım: .save <t.me/link>  |  .save (medyaya yanıtla)"))

@rate_limit(2)
async def dlmedia_handler(client: Client, message):
    r=message.reply_to_message
    if not r or not getattr(r, 'media', None):
        await respond(client, message, smalls("→ bir medyaya yanıtla: .dlmedia"))
        return
    await respond(client, message, smalls("→ indiriliyor..."))
    try:
        path=await client.download_media(r)
        if path:
            cap=getattr(r, 'caption', None) or getattr(r, 'text', None) or smalls("→ kaydedildi")
            # tip
            if getattr(r, 'photo', None):
                await client.send_photo(message.chat.id, path, caption=cap)
            elif getattr(r, 'video', None):
                await client.send_video(message.chat.id, path, caption=cap)
            else:
                await client.send_document(message.chat.id, path, caption=cap)
            try: os.remove(path)
            except: pass
            try: await message.delete()
            except: pass
        else:
            await respond(client, message, smalls("→ indirilemedi"))
    except Exception as e:
        await respond(client, message, smalls(f"→ hata: {e}"))

# ========== EDIT / SD ==========
@rate_limit(2)
async def edit_handler(client: Client, message):
    args = message.text.split(maxsplit=1)
    if len(args)<2 or not args[1].strip():
        await respond(client, message, smalls("→ kullanım: .edit <yeni mesaj>"))
        return
    new_text=args[1]
    try:
        me=await client.get_me()
        my_id=me.id
    except:
        my_id=message.from_user.id if message.from_user else 0
    found=None
    try:
        async for msg in client.get_chat_history(message.chat.id, limit=20):
            try:
                fid=getattr(msg.from_user, "id", None) if getattr(msg,"from_user",None) else None
                is_me=(fid==my_id) or getattr(msg,"outgoing",False)
                if is_me and msg.id != message.id:
                    found=msg
                    break
            except: continue
    except Exception as e:
        print(f"edit history hata {e}", flush=True)
    if found:
        try:
            await client.edit_message_text(message.chat.id, found.id, new_text)
            try: await message.delete()
            except: pass
        except Exception as e:
            await respond(client, message, smalls(f"→ düzenlenemedi: {e}"))
    else:
        await respond(client, message, smalls("→ düzenlenecek mesaj yok"))

@rate_limit(2)
async def sd_handler(client: Client, message):
    args = message.text.split(maxsplit=2)
    # .sd <süre> <mesaj>
    if len(args)<3:
        # try split differently
        txt = message.text or ""
        parts=txt.split(maxsplit=2)
        if len(parts)<3:
            await respond(client, message, smalls("→ kullanım: .sd <süre> <mesaj>  örn: .sd 5 merhaba"))
            return
        try:
            counter=int(parts[1])
            text=parts[2]
        except:
            await respond(client, message, smalls("→ süre hatalı"))
            return
    else:
        try:
            counter=int(args[1])
            text=args[2]
        except:
            await respond(client, message, smalls("→ süre hatalı"))
            return
    if counter<=0 or counter>60:
        await respond(client, message, smalls("→ süre 1-60 olmalı"))
        return
    if not text.strip():
        await respond(client, message, smalls("→ mesaj boş"))
        return
    try: await message.delete()
    except: pass
    try:
        smsg=await client.send_message(message.chat.id, text)
        await asyncio.sleep(counter)
        try: await smsg.delete()
        except: pass
    except Exception as e:
        print(f"sd hata {e}", flush=True)

def register_handlers(app: Client):
    from pyrogram.handlers import MessageHandler
    flt = filters.me | filters.outgoing
    app.add_handler(MessageHandler(purgeme_handler, filters.command(["purgeme","purgeMe","silme"], prefixes=".") & flt))
    app.add_handler(MessageHandler(unpin_handler, filters.command(["unpin","unPin","sabitkaldir"], prefixes=".") & flt))
    app.add_handler(MessageHandler(warns_handler, filters.command(["warns","uyarilar"], prefixes=".") & flt))
    app.add_handler(MessageHandler(delnote_handler, filters.command(["delnote","clear","notsil"], prefixes=".") & flt))
    app.add_handler(MessageHandler(getnote_handler, filters.command(["get","notal"], prefixes=".") & flt))
    app.add_handler(MessageHandler(save_handler, filters.command(["save"], prefixes=".") & flt))
    app.add_handler(MessageHandler(dlmedia_handler, filters.command(["dlmedia","indirmedia"], prefixes=".") & flt))
    app.add_handler(MessageHandler(edit_handler, filters.command(["edit","duzenle"], prefixes=".") & flt))
    app.add_handler(MessageHandler(sd_handler, filters.command(["sd","selfdestruct"], prefixes=".") & flt))
