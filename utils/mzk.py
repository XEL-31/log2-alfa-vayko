"""Log2 Alfa MZK — inline bot ile şarkı gönderme motoru (Pyrogram native, hatasız)

Eski Asena pluginleri `inline_query` + `result.download_media()` kullanıyordu.
Pyrogram tarafında bu yol FILE_ID / FILE_REFERENCE hataları veriyordu.

Bu modül strateji zinciri kullanır:
  1) Telegram'ın kendi inline mekanizması  → client.send_inline_bot_result
     (dosya indirilmez, doğrudan botun sonucu sohbete düşer → hata riski yok)
  2) Sonuç düşmezse: file_id ile indir → send_audio / send_document
  3) Hepsi başarısızsa: kullanıcıya net, kısa bir hata metni döner (asla traceback basmaz)

Kullanım:
    from utils.mzk import play_music, search_song
    ok, info = await play_music(event, "Ceza Suspus", match="Ceza")
"""
from __future__ import annotations

import asyncio
import os
import random
import shutil
import tempfile

# Şarkı botu (env ile değiştirilebilir: MZK_BOT=deezermusicbot)
DEFAULT_BOT = os.getenv("MZK_BOT", "deezermusicbot")
# Yedek botlar — ilki boş sonuç verirse sırayla denenir
FALLBACK_BOTS = [b.strip().lstrip("@") for b in os.getenv("MZK_BOTS", "").split(",") if b.strip()]

_MEDIA_ATTRS = ("audio", "document", "voice", "video", "photo", "sticker", "animation")


def _txt(obj, *names) -> str:
    for n in names:
        v = getattr(obj, n, None)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _result_file_id(result):
    """InlineQueryResult içinden kullanılabilir file_id çıkar."""
    for attr in _MEDIA_ATTRS:
        obj = getattr(result, attr, None)
        if obj is None:
            continue
        fid = getattr(obj, "file_id", None)
        if fid:
            return fid, attr
    return None, None


async def _fetch_results(client, query: str, bot: str):
    """(results, query_id) döner. Bot boşsa (None, None)."""
    for attempt in range(3):
        try:
            res = await client.get_inline_bot_results(bot, query)
        except Exception as e:
            msg = str(e).upper()
            if "FLOOD" in msg:
                await asyncio.sleep(2 + attempt * 2)
                continue
            # bot kullanılamıyor → sonuç yok
            return None, None
        results = getattr(res, "results", None)
        if results is None and isinstance(res, (list, tuple)):
            results = list(res)
            query_id = None
        else:
            query_id = getattr(res, "query_id", None)
        if results:
            return list(results), query_id
        # boş sonuç → biraz bekle, sonra yedek bot
        await asyncio.sleep(1)
    return None, None


async def search_song(client, query: str, bot: str = None, match: str = None):
    """(results, query_id, bot) döner. match verilirse başlık/açıklamaya göre öncelikli sıralar."""
    bots = [bot or DEFAULT_BOT] + [b for b in FALLBACK_BOTS if b != (bot or DEFAULT_BOT)]
    for b in bots:
        b = b.lstrip("@")
        results, query_id = await _fetch_results(client, query, b)
        if not results:
            continue
        if match:
            key = match.lower()
            good = [r for r in results if key in (_txt(r, "title", "description") + " " + _txt(r, "type")).lower()]
            if good:
                random.shuffle(good)
                rest = [r for r in results if r not in good]
                random.shuffle(rest)
                return good + rest, query_id, b
        results = results[:]
        random.shuffle(results)
        return results, query_id, b
    return None, None, None


async def _download_result(client, result) -> str | None:
    """Inline sonucunu indirir, dosya yolunu döner (başarısızsa None)."""
    tmpdir = tempfile.mkdtemp(prefix="log2alfa_mzk_")
    fid, kind = _result_file_id(result)
    path = None
    for target in (fid, getattr(result, "document", None), getattr(result, "audio", None), result):
        if not target:
            continue
        try:
            path = await client.download_media(target, file_name=tmpdir + "/")
        except Exception:
            path = None
        if path and os.path.exists(str(path)) and os.path.getsize(str(path)) > 1024:
            return str(path)
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass
    return None


def _caption(result, credit: str = "@Log2Alfa") -> str:
    title = _txt(result, "title") or "Şarkı"
    desc = _txt(result, "description")
    base = f"{desc} - {title}" if desc and desc.lower() not in title.lower() else title
    return f"🎧 {base}\n✨ {credit}"


async def _cleanup(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
    try:
        if path:
            parent = os.path.dirname(path)
            if "log2alfa_mzk_" in parent:
                shutil.rmtree(parent, ignore_errors=True)
    except Exception:
        pass


async def play_music(event, query: str, match: str = None, bot: str = None,
                     credit: str = "@Log2Alfa", wait_text: str = "🎧 Şarkı aranıyor..."):
    """Şarkıyı bulur ve sohbete gönderir.

    Dönüş: (ok: bool, info: str)
    """
    client = event.client
    chat_id = getattr(event, "chat_id", None)
    reply_to = getattr(event, "reply_to_msg_id", None)

    async def say(text):
        try:
            await event.edit(text)
        except Exception:
            pass

    await say(wait_text)
    results, query_id, used_bot = await search_song(client, query, bot=bot, match=match)
    if not results:
        await say("😔 Şarkı botu yanıt vermedi — birkaç saniye sonra tekrar dene.")
        return False, "bos-sonuc"

    # 1) Telegram inline ile doğrudan gönder (en sağlam yol)
    last = None
    if query_id:
        for r in results[:4]:
            rid = getattr(r, "id", None)
            if not rid:
                continue
            try:
                await client.send_inline_bot_result(chat_id, query_id, rid)
                try:
                    await event.delete()
                except Exception:
                    pass
                return True, "inline:" + str(used_bot)
            except Exception as e:
                last = e
                await asyncio.sleep(0.3)

    # 2) İndirip tekrar gönder
    await say("⬇️ Dosya hazırlanıyor...")
    for r in results[:4]:
        path = await _download_result(client, r)
        if not path:
            continue
        cap = _caption(r, credit)
        sent = False
        # süre bilgisi varsa audio olarak gönder (daha şık)
        for sender, kwargs in (
            ("send_audio", {"caption": cap}),
            ("send_document", {"caption": cap}),
            ("send_video", {"caption": cap}),
        ):
            fn = getattr(client, sender, None)
            if not fn:
                continue
            try:
                if reply_to and sender == "send_audio":
                    kwargs["reply_to_message_id"] = reply_to
                await fn(chat_id, path, **kwargs)
                sent = True
                break
            except Exception as e:
                last = e
                kwargs.pop("reply_to_message_id", None)
                continue
        if sent:
            await _cleanup(path)
            try:
                await event.delete()
            except Exception:
                pass
            return True, "download:" + str(used_bot)
        await _cleanup(path)

    # 3) Hiçbiri olmadı → kısa, anlaşılır mesaj
    await say("😔 Şarkı gönderilemedi (bot dosyayı paylaşmıyor). Birazdan tekrar dene.")
    return False, str(last)


async def play_by_url(event, url: str, credit: str = "@Log2Alfa"):
    """Doğrudan medya linkinden gönderim (yt-dlp olmadan, Telegram URL fetch)."""
    client = event.client
    try:
        await event.client.send_audio(event.chat_id, url, caption=f"🎧 {credit}")
        try:
            await event.delete()
        except Exception:
            pass
        return True, "url"
    except Exception as e:
        return False, str(e)
