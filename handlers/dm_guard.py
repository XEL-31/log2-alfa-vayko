"""Süreli / bir-kez-görüntüle foto-video → Kayıtlı Mesajlar (tek kayıt)
Süreli (ttl) + tek görüntülemelik (view-once, süre biçmeden) hepsi.
"""
import os
import traceback
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler, RawUpdateHandler
from pyrogram import raw
from utils.fonts import smalls

_saved: set = set()

def _key(chat_id: int, msg_id: int) -> str:
    return f"{chat_id}:{msg_id}"

def _priv(chat) -> bool:
    ct = getattr(chat, "type", None)
    if ct is None:
        return False
    s = str(getattr(ct, "value", None) or getattr(ct, "name", None) or ct).lower()
    return "private" in s

def _ttl_of(message) -> int | None:
    for name in ("photo", "video", "voice", "video_note", "animation", "document", "audio"):
        m = getattr(message, name, None)
        if m is None:
            continue
        t = getattr(m, "ttl_seconds", None)
        if t is not None:
            try:
                v = int(t)
                return v if v > 0 else 1
            except Exception:
                return 1
    for name in ("ttl_seconds", "ttl_period"):
        t = getattr(message, name, None)
        if t is not None:
            try:
                v = int(t)
                if v > 0:
                    return v
            except Exception:
                pass
    if getattr(message, "media_unread", None):
        return 1
    r = getattr(message, "_raw", None)
    if r is not None:
        t = getattr(r, "ttl_period", None)
        if t:
            try:
                return int(t)
            except Exception:
                pass
        media = getattr(r, "media", None)
        if media is not None:
            t = getattr(media, "ttl_seconds", None)
            if t is not None:
                try:
                    v = int(t)
                    return v if v > 0 else 1
                except Exception:
                    return 1
    return None

def _is_view_once(message) -> bool:
    """Süre biçmeden tek görüntülemelik için ek tespit"""
    # 1) ttl zaten varsa view-once de sayılır (0x7fffffff)
    if _ttl_of(message) is not None:
        return True
    # 2) media_unread true → view-once
    if getattr(message, "media_unread", None):
        return True
    r = getattr(message, "_raw", None)
    if r is not None:
        if getattr(r, "media_unread", None):
            return True
        # noforwards + photo/video → genelde view-once / korumalı
        # normal foto noforwards=False, view-once noforwards=True olabilir
        if getattr(r, "noforwards", None):
            # photo/video var mı?
            if getattr(message, "photo", None) or getattr(message, "video", None):
                return True
        media = getattr(r, "media", None)
        if media is not None:
            # raw media tipi Photo/Document ve ttl yok ama view-once olabilir
            # Ek: MessageMediaPhoto ttl_seconds None ama view-once flag'i pyrogram parse etmemiş olabilir
            # Bu durumda ham bytes içinde 0x7fffffff var mı kontrol et (view_once = 2147483647)
            try:
                b = r.write()
                # 2147483647 = 0x7FFFFFFF little endian: FF FF FF 7F
                if b"\xff\xff\xff\x7f" in b:
                    return True
            except Exception:
                pass
    return False

def _has_media(message) -> bool:
    return bool(
        message.photo or message.video or message.voice
        or message.video_note or message.animation
        or message.document or message.audio
    )

def _caption(who: str) -> str:
    txt = f"- Süreli Medya Kaydedildi\n- Kimden: {who}\nCr:Log2Alfa"
    s = smalls(txt)
    # sayılar subscript olmasın - düz kalsın
    s = s.translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789"))
    return s

async def _save(client: Client, message, who: str, ttl: int) -> bool:
    cap = _caption(who)
    path = None
    try:
        try:
            path = await client.download_media(message)
        except Exception as e:
            print(f"→ ttl download hata: {e}", flush=True)
            path = None
        if path and os.path.exists(path):
            try:
                if message.photo:
                    await client.send_photo("me", path, caption=cap)
                elif message.video:
                    await client.send_video("me", path, caption=cap)
                elif message.voice:
                    await client.send_voice("me", path, caption=cap)
                elif message.video_note:
                    await client.send_video_note("me", path)
                    await client.send_message("me", cap)
                elif message.animation:
                    await client.send_animation("me", path, caption=cap)
                elif message.audio:
                    await client.send_audio("me", path, caption=cap)
                else:
                    await client.send_document("me", path, caption=cap)
                print(f"→ TTL SAVED dl {who} ttl={ttl}", flush=True)
                return True
            except Exception as e:
                print(f"→ ttl upload hata: {e}", flush=True)
        try:
            await client.copy_message("me", message.chat.id, message.id)
            await client.send_message("me", cap)
            print(f"→ TTL SAVED copy {who}", flush=True)
            return True
        except Exception as e:
            print(f"→ ttl copy fail: {e}", flush=True)
        try:
            await message.forward("me")
            await client.send_message("me", cap)
            print(f"→ TTL SAVED fwd {who}", flush=True)
            return True
        except Exception as e:
            print(f"→ ttl fwd fail: {e}", flush=True)
        return False
    finally:
        if path:
            try:
                os.remove(path)
            except Exception:
                pass

async def on_private(client: Client, message):
    try:
        if not message.chat or not _priv(message.chat):
            return
        if getattr(message, "outgoing", False):
            return
        fu = message.from_user
        if fu is None or getattr(fu, "is_self", False) or getattr(fu, "is_bot", False):
            return
        has = _has_media(message)
        ttl = _ttl_of(message) if has else None
        is_once = _is_view_once(message) if has else False

        if has:
            r = getattr(message, "_raw", None)
            rm = getattr(r, "media", None) if r else None
            # detay log — view-once teşhis için
            try:
                raw_bytes = r.write().hex()[:200] if r else ""
            except Exception:
                raw_bytes = ""
            print(
                f"→ DM-MEDIA from={fu.id} mid={message.id} "
                f"ttl={ttl} is_once={is_once} unread={getattr(message,'media_unread',None)} raw_unread={getattr(r,'media_unread',None) if r else None} "
                f"noforwards={getattr(r,'noforwards',None) if r else None} "
                f"photo={bool(message.photo)} video={bool(message.video)} doc={bool(message.document)} "
                f"photo_ttl={getattr(getattr(message,'photo',None),'ttl_seconds',None)} "
                f"video_ttl={getattr(getattr(message,'video',None),'ttl_seconds',None)} "
                f"raw={type(rm).__name__ if rm else None} raw_ttl={getattr(rm,'ttl_seconds',None) if rm else None} has_7fffffff={('ffff7f' in raw_bytes.lower())}",
                flush=True,
            )

        if not has:
            return
        # ttl VEYA view-once ise kaydet — süre biçmeden tek görüntülemelik de dahil
        if ttl is None and not is_once:
            return

        k = _key(message.chat.id, message.id)
        if k in _saved:
            print(f"→ TTL SKIP duplicate {k}", flush=True)
            return
        _saved.add(k)
        if len(_saved) > 2000:
            _saved.clear()

        who = f"{fu.first_name or '?'} @{fu.username or '-'} ({fu.id})"
        use_ttl = ttl if ttl is not None else 1
        ok = await _save(client, message, who, use_ttl)
        if not ok:
            print(f"→ TTL FAIL {who} mid={message.id}", flush=True)
    except Exception as e:
        print(f"→ dm_guard hata: {e}\n{traceback.format_exc()}", flush=True)

async def on_raw(client: Client, update, users, chats):
    try:
        if not isinstance(update, raw.types.UpdateNewMessage):
            return
        msg = update.message
        if not isinstance(msg, raw.types.Message):
            return
        if getattr(msg, "out", False):
            return
        peer = msg.peer_id
        if not isinstance(peer, raw.types.PeerUser):
            return
        media = getattr(msg, "media", None)
        if media is None:
            # view-once'te media bazen None olabilir, media_unread ile yakala
            if not getattr(msg, "media_unread", False):
                return
            ttl = None
        else:
            ttl = getattr(media, "ttl_seconds", None)
        # view-once ham bytes + media_unread kontrolü
        has_view_once_bytes = False
        is_unread = bool(getattr(msg, "media_unread", False))
        try:
            has_view_once_bytes = b"\xff\xff\xff\x7f" in msg.write()
        except Exception:
            pass
        if ttl is None and not has_view_once_bytes and not is_unread:
            return
        uid = int(peer.user_id)
        mid = int(msg.id)
        k = _key(uid, mid)
        if k in _saved:
            return
        import asyncio
        await asyncio.sleep(0.85)
        if k in _saved:
            return
        _saved.add(k)
        u = users.get(uid) if isinstance(users, dict) else None
        who = f"{getattr(u,'first_name',None) or '?'} ({uid})"
        print(f"→ RAW-TTL ttl={ttl} view_once_bytes={has_view_once_bytes} from={uid} mid={mid} (fallback)", flush=True)
        try:
            m = await client.get_messages(uid, mid)
            if m and _has_media(m):
                use_ttl = int(ttl) if ttl and int(ttl) > 0 else 1
                await _save(client, m, who, use_ttl)
        except Exception as e:
            print(f"→ raw fallback fail: {e}", flush=True)
    except Exception as e:
        print(f"→ on_raw hata: {e}", flush=True)

def register_handlers(app: Client):
    app.add_handler(
        MessageHandler(on_private, filters.private & ~filters.outgoing & ~filters.bot),
        group=1,
    )
    try:
        app.add_handler(RawUpdateHandler(on_raw), group=3)
        print("→ dm_guard: private+RAW view_once destekli OK", flush=True)
    except Exception as e:
        print(f"→ dm_guard RAW fail: {e}", flush=True)
