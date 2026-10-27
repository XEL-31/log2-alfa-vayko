"""
Log2 Alfa → Pyrogram shim (Asena uyumlu): register decorator
Orijinal eski telethon.events.NewMessage kullanır,
Biz Pyrogram filters'e çeviririz ve event objesini uyarlarız

Profesyonel medya shim: sticker / foto / ses / video / document hepsi desteklenir.
Telethon send_file / edit(file=) / reply(file=) Pyrogram'a hatasız çevrilir.
"""
import re
import os
import asyncio
import mimetypes
import traceback
from pathlib import Path

from userbot import PATTERNS, ASENA_PENDING

# Mesaj silindiğinde plugin'i durdurmak için — BaseException ki içteki `except Exception` yakalamasın, direkt wrapper'a gitsin
class MessageDeletedError(BaseException):
    pass

def _is_msg_deleted_error(err_str: str) -> bool:
    s = (err_str or "").lower()
    return ("message_id_invalid" in s or "message to edit not found" in s or "message not found" in s or "msg_id_invalid" in s or "messageidinvalid" in s)

# ── yardımcı: medya akıllı gönderim ──
def _is_url(s: str) -> bool:
    return isinstance(s, str) and (s.startswith("http://") or s.startswith("https://") or s.startswith("tg://"))

async def _smart_send(client, chat_id, file, caption=None, reply_to=None, voice_note=False, video_note=False, **kwargs):
    """
    Telethon send_file → Pyrogram smart send
    file: str path / file_id / url / bytes / file-like / InlineResult / Document
    voice_note/video_note: Telethon flagleri
    Dener: voice → video_note → sticker → audio → video → animation → photo → document
    Her deneme başarısız olursa bir sonrakine geçer, en son document fallback.
    Asla exception fırlatmadan ya Message döner ya da None.
    """
    # ── unwrap: InlineResult / Document / Photo wrapperları çöz ──
    orig_file = file
    try:
        # InlineQueryResult wrapper: .document / .photo / .sticker / .audio / .voice
        if hasattr(file, "document") and getattr(file, "document", None) is not None:
            # Eğer file InlineResult ise ve içinde document var, onu al
            # Ama file zaten Document ise bu dal document.document olur → kontrol et
            doc = getattr(file, "document")
            # Document objesinin kendisinde .document yoktur (None), Inner doc varsa kullan
            # InlineResult.document genelde Document objesidir
            if doc is not file and hasattr(doc, "file_id"):
                file = doc
            elif isinstance(doc, str):
                file = doc
        # Diğer inline alanları — photo/sticker/voice varsa file_id çıkar
        # Eğer file InlineResult ve document yoksa photo/sticker dene
        if hasattr(orig_file, "photo") and getattr(orig_file, "photo", None) is not None:
            # orig_file.photo file_id içerebilir
            if not hasattr(file, "file_id") or file is orig_file:
                ph = getattr(orig_file, "photo")
                if ph is not None and hasattr(ph, "file_id"):
                    # document yoksa photo'yu dene (sticker/photo inline'larında)
                    if isinstance(file, str) and _is_url(file):
                        pass
                    elif not isinstance(file, str) or not file:
                        file = ph
        if hasattr(orig_file, "sticker") and getattr(orig_file, "sticker", None) is not None:
            st = getattr(orig_file, "sticker")
            if st is not None and hasattr(st, "file_id") and (file is orig_file or not hasattr(file, "file_id")):
                file = st
        # Generic file_id çıkarma: Document/Photo/Voice objesi → file_id
        if hasattr(file, "file_id"):
            try:
                fid = file.file_id
                if fid:
                    file = fid
            except Exception:
                pass
        elif hasattr(file, "fileId"):
            try:
                file = file.fileId
            except Exception:
                pass
        # BytesIO / bytes → tempfile? Pyrogram bytes'ı destekler, direkt geçir
    except Exception:
        pass
    # ── hint: InlineResult tipini koru (photo/sticker/voice) için öncelik ──
    hint = None
    try:
        if hasattr(orig_file, "sticker") and getattr(orig_file, "sticker", None) is not None:
            hint = "sticker"
        elif hasattr(orig_file, "voice") and getattr(orig_file, "voice", None) is not None:
            hint = "voice"
        elif hasattr(orig_file, "audio") and getattr(orig_file, "audio", None) is not None:
            hint = "audio"
        elif hasattr(orig_file, "video") and getattr(orig_file, "video", None) is not None:
            hint = "video"
        elif hasattr(orig_file, "photo") and getattr(orig_file, "photo", None) is not None:
            # document yoksa photo hint
            if hint is None:
                hint = "photo"
        elif hasattr(orig_file, "document") and getattr(orig_file, "document", None) is not None:
            # document hint en son
            if hint is None:
                hint = "document"
    except Exception:
        pass

    # ── file artık str (path/file_id/url) veya bytes/file-like veya file_id string ──
    # URL ise direkt link gönder (indirip göndermeyi dene ama fallback text)
    if isinstance(file, str) and _is_url(file):
        # Telegram'da URL'yi document olarak göndermeyi dene (Pyrogram indirme destekler mi?)
        # Önce document olarak dene, olmazsa text olarak gönder
        try:
            return await client.send_document(chat_id, file, caption=caption, reply_to_message_id=reply_to)
        except Exception:
            try:
                return await client.send_photo(chat_id, file, caption=caption, reply_to_message_id=reply_to)
            except Exception:
                try:
                    return await client.send_message(chat_id, f"{caption or ''}\n{file}".strip(), reply_to_message_id=reply_to)
                except Exception:
                    return None

    # Local dosya mı file_id mi ayır
    is_local_path = False
    ext = ""
    if isinstance(file, str):
        # file_id genelde 20+ karakter ve path değil, ama local path de olabilir
        # /tmp /data /app gibi path'ler kesin local
        if os.path.exists(file):
            is_local_path = True
            ext = os.path.splitext(file)[1].lower()
        else:
            # /tmp/... gibi olmayan ama uzantılı string → muhtemel olmayan path, file_id kabul et
            # Uzantı tahmini: eğer .webp .mp3 gibi bitiyorsa ve os.path.exists false ise, muhtemel file_id değil, geçici dosya silinmiş olabilir → extension yine tahmin et
            ext = os.path.splitext(file)[1].lower()
            # file_id'ler genelde uzantı içermez, ama içeriyorsa extension boş kalır
            if ext in (".webp",".tgs",".jpg",".jpeg",".png",".gif",".mp4",".mp3",".ogg",".opus",".m4a",".wav",".flac",".mkv",".mov",".avi",".webm"):
                # bu uzantıya sahip string ama dosya yok → file_id olmayabilir, yine de dene
                pass
            else:
                ext = ""
    elif isinstance(file, (bytes, bytearray)):
        # bytes → ext bilinmiyor
        pass
    else:
        # file-like object (BytesIO) → ext yok
        pass

    # mimetype tahmini
    mime = None
    if is_local_path:
        try:
            mime, _ = mimetypes.guess_type(file)
        except Exception:
            pass

    # ── Gönderim sırası: flag'lere ve uzantıya göre akıllı sırala ──
    # Her deneme try/except, başarılı olursa return
    # reply_to None ise reply_to_message_id parametresi gönderilmez (bazı send_*'lerde hata verebilir)
    def _rt():
        return reply_to if reply_to else None

    # Yardımcı: her send_* denemesi için kwargs temizle
    # caption bazı metodlarda desteklenmez (sticker, video_note)
    # Onları ayıkla

    # 1) voice_note
    if voice_note:
        # file .ogg/.opus veya voice_note flag → send_voice
        for meth in ("send_voice", "send_audio"):
            try:
                fn = getattr(client, meth, None)
                if fn:
                    # caption voice'te var, video_note'te yok
                    if meth == "send_voice":
                        return await fn(chat_id, file, caption=caption, reply_to_message_id=_rt())
                    else:
                        return await fn(chat_id, file, caption=caption, reply_to_message_id=_rt())
            except Exception as e:
                print(f"smart_send {meth} voice_note hata: {e}", flush=True)
                continue

    # 2) video_note
    if video_note:
        try:
            fn = getattr(client, "send_video_note", None)
            if fn:
                return await fn(chat_id, file, reply_to_message_id=_rt())
        except Exception as e:
            print(f"smart_send send_video_note hata: {e}", flush=True)

    # 3) Extension bazlı öncelik
    # Sıra listesi oluştur
    ordered = []
    if ext == ".webp" or ext == ".tgs":
        ordered = ["send_sticker", "send_document", "send_photo"]
    elif ext in (".jpg",".jpeg",".png",".bmp",".jfif"):
        ordered = ["send_photo", "send_document", "send_sticker"]
    elif ext == ".gif":
        ordered = ["send_animation", "send_video", "send_document", "send_photo"]
    elif ext in (".mp4",".mov",".avi",".mkv",".webm"):
        ordered = ["send_video", "send_animation", "send_document"]
    elif ext in (".mp3",".m4a",".wav",".flac",".aac"):
        ordered = ["send_audio", "send_voice", "send_document"]
    elif ext in (".ogg",".opus"):
        ordered = ["send_voice", "send_audio", "send_document"]
    elif ext == ".oga":
        ordered = ["send_voice", "send_audio", "send_document"]
    else:
        # file_id veya bilinmeyen → hint varsa ona göre öncelik, yoksa en genel cascade (photo/sticker/voice önce, document en son)
        if hint == "sticker":
            ordered = ["send_sticker", "send_document", "send_photo", "send_voice", "send_audio", "send_video", "send_animation", "send_video_note"]
        elif hint == "photo":
            ordered = ["send_photo", "send_document", "send_sticker", "send_voice", "send_audio", "send_video", "send_animation", "send_video_note"]
        elif hint == "voice":
            ordered = ["send_voice", "send_audio", "send_document", "send_photo", "send_sticker", "send_video", "send_animation", "send_video_note"]
        elif hint == "audio":
            ordered = ["send_audio", "send_voice", "send_document", "send_photo", "send_video", "send_animation", "send_sticker", "send_video_note"]
        elif hint == "video":
            ordered = ["send_video", "send_animation", "send_document", "send_photo", "send_sticker", "send_voice", "send_audio", "send_video_note"]
        else:
            # hint yok → foto/sticker/ses önce dene, document en sonda (doğru tip için)
            ordered = ["send_photo", "send_sticker", "send_voice", "send_audio", "send_video", "send_animation", "send_video_note", "send_document"]

    # Eğer local path değilse (file_id), photo ve sticker denemeleri de önemli → ordered zaten document→photo→sticker sırasındayken iyi
    # Eğer caption varsa sticker/video_note caption kabul etmez → onları caption'sız dene
    tried = set()
    for meth_name in ordered:
        if meth_name in tried:
            continue
        tried.add(meth_name)
        try:
            fn = getattr(client, meth_name, None)
            if not fn:
                continue
            if meth_name == "send_sticker":
                # sticker caption almaz
                return await fn(chat_id, file, reply_to_message_id=_rt())
            elif meth_name == "send_video_note":
                return await fn(chat_id, file, reply_to_message_id=_rt())
            elif meth_name == "send_animation":
                return await fn(chat_id, file, caption=caption, reply_to_message_id=_rt())
            elif meth_name == "send_photo":
                return await fn(chat_id, file, caption=caption, reply_to_message_id=_rt())
            elif meth_name == "send_voice":
                # duration vs. kwargs'tan al
                dur = kwargs.get("duration")
                if dur:
                    return await fn(chat_id, file, caption=caption, duration=dur, reply_to_message_id=_rt())
                return await fn(chat_id, file, caption=caption, reply_to_message_id=_rt())
            else:
                # send_document / send_audio / send_video
                return await fn(chat_id, file, caption=caption, reply_to_message_id=_rt())
        except Exception as e:
            # Eğer "wrong string length" gibi file_id tipi uyuşmazlığı ise bir sonrakini dene
            # Logla ama devam et
            # print(f"smart_send {meth_name} deneme hata: {e}", flush=True)
            continue

    # Fallback: kalan metodları dene (ordered'da olmayanlar)
    for meth_name in ["send_document","send_photo","send_sticker","send_voice","send_audio","send_video","send_animation","send_video_note"]:
        if meth_name in tried:
            continue
        try:
            fn = getattr(client, meth_name, None)
            if not fn:
                continue
            if meth_name in ("send_sticker","send_video_note"):
                return await fn(chat_id, file, reply_to_message_id=_rt())
            else:
                return await fn(chat_id, file, caption=caption, reply_to_message_id=_rt())
        except Exception:
            continue

    # Son çare: text olarak gönder
    try:
        txt = caption or ""
        if isinstance(file, str) and file:
            txt = f"{txt}\n{file}".strip() if txt else file
        if txt:
            return await client.send_message(chat_id, txt, reply_to_message_id=_rt())
    except Exception as e:
        print(f"smart_send son fallback hata: {e}", flush=True)
    return None


# ── AsenaEvent — Telethon event → Pyrogram message sarmalayıcı ──
class AsenaEvent:
    """Pyrogram Message + Client'i Telethon event gibi göster"""
    def __init__(self, client, message, pattern=None):
        self.client = client
        self._client = client
        self.message = message
        self._message = message
        # Telethon uyumlu alanlar
        self.chat_id = message.chat.id if message.chat else 0
        self.sender_id = message.from_user.id if message.from_user else 0
        self.sender = message.from_user
        self.chat = message.chat
        self.text = message.text or message.caption or ""
        self.raw_text = self.text
        self.is_group = bool(message.chat and str(getattr(message.chat.type, "value", "")).lower() in ("group","supergroup") or "group" in str(getattr(message.chat, "type", "")).lower())
        self.is_private = not self.is_group
        # is_reply — Telethon → Pyrogram
        try:
            self.is_reply = bool(message.reply_to_message)
        except Exception:
            self.is_reply = False
        # forward_from deprecated → forward_origin kullan, deprecation hatasını yut
        self.fwd_from = None
        try:
            self.fwd_from = getattr(message, "forward_origin", None)
        except Exception:
            pass
        if not self.fwd_from:
            try:
                self.fwd_from = message.__dict__.get("forward_from", None) or message.__dict__.get("fwd_from", None)
            except Exception:
                pass
        self.via_bot_id = getattr(message, "via_bot_id", None)
        self.reply_to_msg_id = message.reply_to_message.id if message.reply_to_message else None
        self.id = message.id
        self.pattern_match = None
        if pattern:
            try:
                m = re.search(pattern, self.text)
                self.pattern_match = m
            except Exception:
                self.pattern_match = None
        self.matches = self.pattern_match
        # client shims
        self._ensure_client_shim()

    def _ensure_client_shim(self):
        # e.client.inline_query → e.client.get_inline_bot_results alias (with download_media shim)
        try:
            if not hasattr(self._client, "inline_query") or True:
                from utils.inline_shim import inline_query as _iq_impl

                async def _inline_query(bot_username, query, **kw):
                    # Telethon uyumlu: liste + query_id + .click() + .download_media()
                    try:
                        return await _iq_impl(self._client, bot_username, query)
                    except Exception as e1:
                        # @ işaretiyle tekrar dene
                        try:
                            return await _iq_impl(self._client, str(bot_username).lstrip("@"), query)
                        except Exception:
                            raise e1

                self._client.inline_query = _inline_query
        except Exception:
            pass
        # e.client.send_file → smart_send alias (Telethon → Pyrogram)
        try:
            if not hasattr(self._client, "send_file"):
                async def _send_file(entity, file, caption=None, reply_to=None, voice_note=False, video_note=False, **kw):
                    # entity chat_id olabilir (int) veya peer
                    chat = entity
                    # entity string/int değilse id çıkar
                    try:
                        if not isinstance(entity, int) and not isinstance(entity, str):
                            # Telethon entity objesi → id
                            chat = getattr(entity, "id", None) or getattr(entity, "chat_id", None) or self.chat_id
                    except Exception:
                        chat = self.chat_id
                    # reply_to Telethon'da msg_id int olabilir veya Message
                    rt = reply_to
                    try:
                        if hasattr(reply_to, "id"):
                            rt = reply_to.id
                    except Exception:
                        pass
                    # caption handling
                    cap = caption
                    if cap is None:
                        cap = kw.pop("caption", None)
                    return await _smart_send(self._client, chat, file, caption=cap, reply_to=rt, voice_note=voice_note, video_note=video_note, **kw)
                self._client.send_file = _send_file
                # aliaslar
                self._client.sendFile = _send_file
        except Exception:
            pass
        # e.client.send_message shim (Telethon vs Pyrogram farkı)
        try:
            if not hasattr(self._client, "send_message"):
                # Pyrogram'da zaten var, gerek yok
                pass
        except Exception:
            pass
        # download_media alias
        try:
            if not hasattr(self._client, "download_media"):
                pass
            if not hasattr(self._client, "download_file"):
                async def _download_file(*a, **kw):
                    return await self._client.download_media(*a, **kw)
                self._client.download_file = _download_file
        except Exception:
            pass
        # send_read_acknowledge dummy (Telethon → Pyrogram)
        try:
            if not hasattr(self._client, "send_read_acknowledge"):
                async def _send_read_acknowledge(*a, **kw):
                    return None
                self._client.send_read_acknowledge = _send_read_acknowledge
        except Exception:
            pass
        # get_messages / get_messageHistory dummy + Pyrogram uyumlu shim
        try:
            # Pyrogram'da get_messages var ama Telethon çağrısı farklı: get_messages(chat_id, ids, from_user)
            # Bizim shim Pyrogram gerçek fonksiyonu bozmamalı, sadece Telethon tarzı fallback ekle
            _orig_get_messages = getattr(self._client, "get_messages", None)
            async def _get_messages(*a, **kw):
                # Telethon: get_messages(chat_id, limit=..., from_user=...)
                # Pyrogram: get_messages(chat_id, message_ids, replies=... )
                try:
                    if _orig_get_messages:
                        # Eğer Pyrogram gerçek get_messages ise, doğru çağrı yap
                        # Telethon tarzı from_user varsa onu history ile çöz
                        if "from_user" in kw:
                            # Asena mesaj sayısı pluginleri için: bot.get_messages(chat, 0, from_user=uid)
                            # Burada 0 total count için, biz get_chat_history ile sayalım
                            chat_id = a[0] if a else kw.get("chat_id") or self.chat_id
                            uid = kw.get("from_user")
                            # uid string veya int olabilir
                            try:
                                if isinstance(uid, str) and uid == "me":
                                    me = await self._client.get_me()
                                    uid = me.id
                                # count messages from user via history (max 100)
                                cnt = 0
                                async for msg in self._client.get_chat_history(chat_id, limit=100):
                                    try:
                                        f_id = getattr(msg.from_user, "id", None) if msg.from_user else None
                                        if f_id is not None and int(f_id) == int(uid):
                                            cnt += 1
                                    except:
                                        pass
                                # Telethon GetMessages total için objede .total var
                                class _R:
                                    def __init__(self, total):
                                        self.total = total
                                        self.count = total
                                return _R(cnt)
                            except Exception as e:
                                print(f"get_messages from_user shim hata: {e}", flush=True)
                                class _R:
                                    total = 0
                                return _R(0)
                        # Normal Pyrogram çağrısı
                        return await _orig_get_messages(*a, **kw)
                except Exception as e:
                    print(f"get_messages shim fallback hata: {e}", flush=True)
                return []
            # Her durumda override et (Telethon uyumu için)
            self._client.get_messages = _get_messages
            self._client.getMessages = _get_messages
        except Exception:
            pass
        # download_profile_photo shim (Telethon -> Pyrogram)
        try:
            if not hasattr(self._client, "download_profile_photo") or True:
                async def _download_profile_photo(entity, *a, **kw):
                    # entity Peer/id/user objesi olabilir
                    try:
                        uid = entity
                        if hasattr(entity, "user_id"):
                            uid = entity.user_id
                        elif hasattr(entity, "channel_id"):
                            uid = entity.channel_id
                        elif hasattr(entity, "id"):
                            # Eğer obje Message ise from_user
                            if hasattr(entity, "from_user") and getattr(entity, "from_user", None):
                                uid = entity.from_user.id
                            else:
                                uid = entity.id
                        # string username?
                        if isinstance(uid, str) and uid.startswith("@"):
                            uid = uid
                        # Pyrogram: get_chat photos? download için chat photo
                        # En basit: get_chat ve photo varsa indir
                        try:
                            chat = await self._client.get_chat(uid)
                            if getattr(chat, "photo", None):
                                # Pyrogram'da chat.photo.big_file_id vs.
                                # download_media ile indir
                                if hasattr(chat.photo, "big_file_id"):
                                    # Pyrogram chat photo id ile download?
                                    # get_chat'de photo yoksa get_users dene
                                    pass
                        except:
                            pass
                        # Alternatif: get_users / get_chat ve download
                        try:
                            # Pyrogram'da profil fotosu indirme: download_media ile user photo?
                            # get_users ile user objesi al, sonra download?
                            # Pyromod: client.download_media(user.photo)
                            # Deneyelim
                            try:
                                user = await self._client.get_users(uid)
                                if getattr(user, "photo", None):
                                    # user.photo.big_file_id var
                                    # download_media ile indir
                                    # Pyrogram'da download_media photo objesini destekler?
                                    # Dene
                                    path = await self._client.download_media(user.photo.big_file_id if hasattr(user.photo, "big_file_id") else user.photo)
                                    if path:
                                        return path
                            except:
                                pass
                        except:
                            pass
                        # Son çare: None döndür
                        # Plugin "if foto == None: return" diye kontrol ediyor, o yüzden None sorun değil
                        return None
                    except Exception as e:
                        print(f"download_profile_photo shim hata: {e}", flush=True)
                        return None
                self._client.download_profile_photo = _download_profile_photo
        except Exception:
            pass
        # get_participants / get_chat_members shim
        try:
            _orig_get_participants = getattr(self._client, "get_participants", None)
            async def _get_participants(chat_id, *a, **kw):
                try:
                    # Pyrogram'da get_chat_members
                    # chat_id int veya Peer
                    cid = chat_id
                    if hasattr(cid, "chat_id"):
                        cid = cid.chat_id
                    elif hasattr(cid, "channel_id"):
                        cid = cid.channel_id
                    elif hasattr(cid, "id"):
                        cid = cid.id
                    # get_chat_members ile liste döndür
                    members = []
                    try:
                        async for m in self._client.get_chat_members(cid, *a, **kw):
                            members.append(m)
                        return members
                    except:
                        # fallback get_chat_members count?
                        return []
                except Exception as e:
                    print(f"get_participants shim hata: {e}", flush=True)
                    return []
            self._client.get_participants = _get_participants
            self._client.getParticipants = _get_participants
            # iter_participants alias
            self._client.iter_participants = _get_participants
        except Exception:
            pass
        # get_chat_history / iter_messages shim
        try:
            if not hasattr(self._client, "iter_messages"):
                async def _iter_messages(chat_id, limit=100, *a, **kw):
                    async for msg in self._client.get_chat_history(chat_id, limit=limit):
                        yield msg
                self._client.iter_messages = _iter_messages
            if not hasattr(self._client, "iter_participants"):
                self._client.iter_participants = self._client.get_participants if hasattr(self._client, "get_participants") else _get_participants
        except Exception:
            pass
        # join_chat shim (JoinChannelRequest için)
        try:
            if not hasattr(self._client, "join_chat"):
                pass
            # delete_messages shim zaten Pyrogram'da var, ama Telethon delete_messages(chat, [ids]) için wrapper
            _orig_delete = getattr(self._client, "delete_messages", None)
            async def _delete_messages(chat_id, message_ids, *a, **kw):
                try:
                    # Telethon: delete_messages(chat, [msg.id,...])
                    # Pyrogram: delete_messages(chat_id, message_ids)
                    return await _orig_delete(chat_id, message_ids, *a, **kw) if _orig_delete else None
                except Exception as e:
                    print(f"delete_messages shim hata: {e}", flush=True)
                    return None
            # Override sadece yoksa veya uyum için
            # self._client.delete_messages = _delete_messages
        except Exception:
            pass
        # get_entity / get_input_entity shim (Telethon → Pyrogram)
        try:
            if not hasattr(self._client, "get_entity"):
                async def _get_entity(entity, **kw):
                    if entity is None:
                        return None
                    # Telethon Peer / int / str / Message
                    try:
                        # Direct int
                        if isinstance(entity, int):
                            try:
                                return await self._client.get_users(entity)
                            except Exception:
                                try:
                                    return await self._client.get_chat(entity)
                                except Exception:
                                    return None
                        # String username
                        if isinstance(entity, str):
                            ent = entity.strip()
                            if ent.startswith("@"):
                                ent = ent
                            try:
                                return await self._client.get_users(ent)
                            except Exception:
                                try:
                                    return await self._client.get_chat(ent)
                                except Exception:
                                    return None
                        # Object with user_id / channel_id / chat_id
                        if hasattr(entity, "user_id"):
                            try:
                                return await self._client.get_users(entity.user_id)
                            except Exception:
                                pass
                        if hasattr(entity, "channel_id"):
                            try:
                                return await self._client.get_chat(entity.channel_id)
                            except Exception:
                                pass
                        if hasattr(entity, "chat_id"):
                            try:
                                return await self._client.get_chat(entity.chat_id)
                            except Exception:
                                pass
                        # Generic id attribute
                        eid = getattr(entity, "id", None)
                        if eid is not None:
                            try:
                                return await self._client.get_users(eid)
                            except Exception:
                                try:
                                    return await self._client.get_chat(eid)
                                except Exception:
                                    pass
                        # Message object itself
                        if hasattr(entity, "from_user") and getattr(entity, "from_user", None):
                            return entity.from_user
                        if hasattr(entity, "sender"):
                            return entity.sender
                    except Exception as e:
                        print(f"get_entity shim hata {entity}: {e}", flush=True)
                    return None
                self._client.get_entity = _get_entity
                self._client.get_input_entity = _get_entity
                self._client.get_peer = _get_entity
        except Exception:
            pass
        # get_me shim — Pyrogram zaten var, ama Telethon bot.get_me alias için
        try:
            if not hasattr(self._client, "get_me"):
                async def _get_me(*a, **kw):
                    return await self._client.get_me(*a, **kw)
                self._client.get_me = _get_me
        except Exception:
            pass

    # Telethon event metodları → Pyrogram'a yönlendir
    async def edit(self, text=None, **kwargs):
        file = kwargs.pop("file", None)
        if file is not None:
            try:
                sent = await _smart_send(self._client, self.chat_id, file, caption=text, reply_to=self.reply_to_msg_id, **kwargs)
                if sent:
                    try:
                        await self._message.delete()
                    except BaseException as e_del:
                        if isinstance(e_del, MessageDeletedError) or _is_msg_deleted_error(str(e_del)):
                            raise MessageDeletedError(str(e_del))
                        try:
                            await self._message.edit_text(text or "")
                        except BaseException as e_edit:
                            if isinstance(e_edit, MessageDeletedError) or _is_msg_deleted_error(str(e_edit)):
                                raise MessageDeletedError(str(e_edit))
                            pass
                        except Exception:
                            pass
                    except Exception as e_del:
                        if _is_msg_deleted_error(str(e_del)):
                            raise MessageDeletedError(str(e_del))
                        try:
                            await self._message.edit_text(text or "")
                        except BaseException as e_edit:
                            if isinstance(e_edit, MessageDeletedError) or _is_msg_deleted_error(str(e_edit)):
                                raise MessageDeletedError(str(e_edit))
                            pass
                    return sent
                else:
                    print(f"edit file smart_send boş döndü file={file}", flush=True)
            except BaseException as e:
                if isinstance(e, MessageDeletedError) or _is_msg_deleted_error(str(e)):
                    raise
                print(f"edit file hata: {e}\n{traceback.format_exc()}", flush=True)
            except Exception as e:
                print(f"edit file hata: {e}\n{traceback.format_exc()}", flush=True)
        if text is None:
            text = ""
        if isinstance(text, str) and not text.strip():
            text = "​"
        if isinstance(text, str) and len(text) > 4000:
            text = text[:4000]
        try:
            kwargs.pop("parse_mode", None)
            kwargs.pop("link_preview_options", None)
            return await self._message.edit_text(text, **kwargs)
        except BaseException as e1:
            if isinstance(e1, MessageDeletedError) or _is_msg_deleted_error(str(e1)):
                raise MessageDeletedError(str(e1))
            err = str(e1)
            if "MESSAGE_NOT_MODIFIED" in err or "message not modified" in err.lower():
                return self._message
            if "MESSAGE_EMPTY" in err or "empty" in err.lower():
                print(f"edit MESSAGE_EMPTY text={repr(text[:100])} err={e1}", flush=True)
                try:
                    return await self._message.edit_text(text or "​", disable_web_page_preview=True)
                except BaseException as e_empty:
                    if isinstance(e_empty, MessageDeletedError) or _is_msg_deleted_error(str(e_empty)):
                        raise MessageDeletedError(str(e_empty))
                    pass
                except Exception:
                    pass
            if "parse" in err.lower() or "markdown" in err.lower():
                try:
                    return await self._message.edit_text(text, parse_mode=None)
                except BaseException as e_parse:
                    if isinstance(e_parse, MessageDeletedError) or _is_msg_deleted_error(str(e_parse)):
                        raise MessageDeletedError(str(e_parse))
                    pass
                except Exception:
                    pass
            try:
                return await self._message.edit_caption(caption=text, **kwargs)
            except BaseException as e2:
                if isinstance(e2, MessageDeletedError) or _is_msg_deleted_error(str(e2)):
                    raise MessageDeletedError(str(e2))
                err2 = str(e2).lower()
                if "message_not_modified" in err2 or "message not modified" in err2:
                    return self._message
                if _is_msg_deleted_error(str(e2)):
                    raise MessageDeletedError(str(e2))
                try:
                    return await self._client.send_message(self.chat_id, text or "​")
                except BaseException as e3:
                    if isinstance(e3, MessageDeletedError) or _is_msg_deleted_error(str(e3)):
                        raise MessageDeletedError(str(e3))
                    print(f"edit fallback send_message hata: {e3} text={repr(text[:50])}", flush=True)
                    return None
                except Exception as e3:
                    print(f"edit fallback send_message hata: {e3} text={repr(text[:50])}", flush=True)
                    return None
            except Exception:
                try:
                    return await self._client.send_message(self.chat_id, text or "​")
                except BaseException as e3:
                    if isinstance(e3, MessageDeletedError) or _is_msg_deleted_error(str(e3)):
                        raise MessageDeletedError(str(e3))
                    print(f"edit fallback send_message hata: {e3} text={repr(text[:50])}", flush=True)
                    return None
                except Exception as e3:
                    print(f"edit fallback send_message hata: {e3} text={repr(text[:50])}", flush=True)
                    return None
        except Exception as e1:
            if _is_msg_deleted_error(str(e1)):
                raise MessageDeletedError(str(e1))
            raise
    async def reply(self, text=None, **kwargs):
        file = kwargs.pop("file", None)
        # Telethon'da reply bazen file, caption, voice_note ile gelir
        voice_note = kwargs.pop("voice_note", False)
        video_note = kwargs.pop("video_note", False)
        # reply_to handling — Telethon'da reply_to param olabilir, biz ignore
        kwargs.pop("reply_to", None)
        if file is not None:
            try:
                cap = text or kwargs.pop("caption", None)
                # Bazı pluginler file'ı caption ile birlikte verir, text None ise cap'i kullan
                # file unwrap + smart_send
                sent = await _smart_send(self._client, self.chat_id, file, caption=cap, reply_to=self._message.id, voice_note=voice_note, video_note=video_note, **kwargs)
                if sent:
                    return sent
                else:
                    print(f"reply file smart_send boş döndü file={file} cap={cap}", flush=True)
                    # fallback: text + file path olarak gönder
                    fallback_txt = (cap or text or "") + (f"\n{file}" if isinstance(file, str) and _is_url(file) else "")
                    if fallback_txt.strip():
                        return await self._message.reply_text(fallback_txt.strip(), **kwargs)
                    return await self._message.reply_text(cap or text or " ", **kwargs)
            except Exception as e:
                print(f"Asena reply file hatası: {e}\n{traceback.format_exc()}", flush=True)
                # fallback text
                try:
                    return await self._message.reply_text(text or kwargs.get("caption", "") or " ", **kwargs)
                except Exception:
                    return None
        if text is None:
            text = ""
        # Normal text reply
        try:
            return await self._message.reply_text(text, **kwargs)
        except Exception as e:
            # FloodWait vs.
            print(f"reply_text hata: {e}", flush=True)
            try:
                return await self._client.send_message(self.chat_id, text, reply_to_message_id=self._message.id)
            except Exception as e2:
                print(f"reply send_message fallback hata: {e2}", flush=True)
                return None

    async def respond(self, text=None, **kwargs):
        return await self.reply(text, **kwargs)

    # Ultroid/Asena'da e.eor() — edit or reply
    async def eor(self, text=None, **kwargs):
        # eğer kendi mesajın ise edit, değilse reply
        # file ile eor da çağrılabilir → edit'e pasla
        try:
            if getattr(self._message, "outgoing", False) or getattr(self._message.from_user, "is_self", False):
                return await self.edit(text, **kwargs)
            else:
                try:
                    return await self.edit(text, **kwargs)
                except Exception:
                    return await self.reply(text, **kwargs)
        except Exception:
            try:
                return await self.edit(text, **kwargs)
            except Exception:
                return await self.reply(text, **kwargs)

    async def delete(self):
        try:
            return await self._message.delete()
        except Exception:
            pass

    async def get_reply_message(self):
        msg = self._message.reply_to_message
        if msg is None:
            return None
        # Telethon uyumu: from_id / sender / sender_id ekle (Pyrogram'da from_user)
        try:
            # from_id alias
            if not hasattr(msg, "from_id") or getattr(msg, "from_id", None) is None:
                try:
                    # Pyrogram Message.from_user
                    fid = getattr(msg, "from_user", None)
                    if fid is not None:
                        fid = getattr(fid, "id", None)
                    if fid is None:
                        # fallback sender
                        fid = getattr(msg, "sender_id", None)
                    if fid is not None:
                        try:
                            msg.__dict__["from_id"] = fid
                        except Exception:
                            try:
                                object.__setattr__(msg, "from_id", fid)
                            except Exception:
                                pass
                except Exception:
                    pass
            # sender alias
            if not hasattr(msg, "sender"):
                try:
                    sender = getattr(msg, "from_user", None)
                    if sender is not None:
                        try:
                            msg.__dict__["sender"] = sender
                        except Exception:
                            object.__setattr__(msg, "sender", sender)
                except Exception:
                    pass
            # sender_id alias
            if not hasattr(msg, "sender_id"):
                try:
                    sid = getattr(msg, "from_user", None)
                    sid = getattr(sid, "id", None) if sid else None
                    if sid is not None:
                        try:
                            msg.__dict__["sender_id"] = sid
                        except Exception:
                            object.__setattr__(msg, "sender_id", sid)
                except Exception:
                    pass
            # text alanları
            if not hasattr(msg, "message"):
                try:
                    txt = getattr(msg, "text", None) or getattr(msg, "caption", None) or ""
                    try:
                        msg.__dict__["message"] = txt
                    except Exception:
                        object.__setattr__(msg, "message", txt)
                except Exception:
                    pass
        except Exception:
            pass
        return msg

    async def get_chat(self):
        return self.chat

    async def get_sender(self):
        return self.sender

    def __getattr__(self, name):
        # is_reply gibi Telethon aliasları
        if name == "is_reply":
            try:
                return bool(self._message.reply_to_message)
            except Exception:
                return False
        if name in ("is_private", "is_group", "is_channel", "is_forward"):
            return self.__dict__.get(name, False)
        # Pyrogram Message attribute — deprecation hatalarını yut
        try:
            if hasattr(self._message, name):
                return getattr(self._message, name)
        except Exception as e:
            try:
                if name in self._message.__dict__:
                    return self._message.__dict__[name]
            except Exception:
                pass
            if "deprecated" in str(e).lower():
                return None
            try:
                return self._message.__dict__.get(name)
            except Exception:
                pass
        if name.startswith("is_"):
            return False
        if name in ("fwd_from", "forward_from", "via_bot_id", "reply_to_msg_id"):
            return None
        raise AttributeError(name)

def register(**args):
    """
    Asena @register(outgoing=True, pattern="^.deneme")
    Pyrogram'a çevir: pattern regex → filters.regex
    """
    pattern = args.get("pattern", None)
    if pattern:
        if "^." in pattern:
            pattern = pattern.replace("^.", "^[" + PATTERNS + "]")
        args["pattern"] = pattern
    for k in ["disable_edited","ignore_unsafe","groups_only","disable_errors","trigger_on_fwd","trigger_on_inline","incoming","outgoing","from_users","forwards"]:
        args.pop(k, None)
    def decorator(func):
        ASENA_PENDING.append((pattern, func, args))
        return func
    return decorator

class _StopPropagation(Exception):
    pass

try:
    import telethon.events as _tele_events
    _tele_events.StopPropagation = _StopPropagation
except Exception:
    pass
