"""Telethon ↔ Pyrogram inline köprüsü.

Asena pluginleri şu kalıbı kullanır:

    sonuclar = await event.client.inline_query("bot", "sorgu")
    await sonuclar[0].click(chat_id, reply_to=..., hide_via=True)      # waifu/honk
    mesaj = await sonuclar[0].click("me", hide_via=True)               # inlinefun
    indir = await sonuclar[0].download_media()                         # müzik pluginleri

Pyrogram'da InlineQueryResult nesnelerinde `.click()` ve `.download_media()` YOK.
Bu modül ikisini de sağlar: sonuçlar normal liste gibi davranır, her öğe bir
proxy'dir ve `click()` çağrısı Telegram'ın gerçek inline mekanizmasına gider
(FILE_ID indirme hatası çıkmaz).
"""
from __future__ import annotations

import random

_MEDIA_ATTRS = ("audio", "document", "voice", "video", "photo", "sticker", "animation")


class _SentMessage:
    """Telethon'un döndürdüğü mesaj yerine minimal taklit."""

    def __init__(self, raw=None, msg_id=None):
        self.raw = raw
        self.id = msg_id if msg_id is not None else getattr(raw, "id", None)
        self.message_id = self.id

    async def delete(self):
        return True

    async def edit(self, *a, **kw):
        return True


class ResultProxy:
    """Tek bir inline sonuç — Telethon Result uyumlu."""

    def __init__(self, raw, query_id, bot_name, client):
        self._raw = raw
        self._query_id = query_id
        self._bot = bot_name
        self._client = client

    # ── attribute geçişi ──
    def __getattr__(self, name):
        raw = object.__getattribute__(self, "_raw")
        try:
            val = getattr(raw, name)
            if val is not None:
                return val
        except AttributeError:
            pass
        if name in ("description", "desc") and hasattr(raw, "title"):
            return raw.title
        if name in ("title", "name") and hasattr(raw, "description"):
            return raw.description
        raise AttributeError(name)

    def __repr__(self):
        try:
            return f"<ResultProxy {getattr(self._raw, 'id', '?')}>"
        except Exception:
            return "<ResultProxy>"

    # ── Telethon API'leri ──
    async def click(self, chat_id=None, reply_to=None, silent=False, hide_via=False, **kw):
        """Sonucu sohbete gönderir (Telegram inline)."""
        result_id = getattr(self._raw, "id", None)
        if not result_id or not self._query_id:
            raise RuntimeError("inline sonuç gönderilemedi (query_id yok)")
        target = chat_id
        if target in ("me", None):
            try:
                me = await self._client.get_me()
                target = me.id
            except Exception:
                target = "me"
        kwargs = {}
        if reply_to:
            kwargs["reply_to_message_id"] = reply_to
        if silent:
            kwargs["disable_notification"] = True
        try:
            sent = await self._client.send_inline_bot_result(target, self._query_id, result_id, **kwargs)
        except TypeError:
            sent = await self._client.send_inline_bot_result(target, self._query_id, result_id)
        return _SentMessage(sent)

    async def download_media(self, *a, **kw):
        """Sonucu indirir (file_id → dosya). Bulunamazsa None."""
        target = None
        for attr in _MEDIA_ATTRS:
            obj = getattr(self._raw, attr, None)
            if obj is not None:
                target = getattr(obj, "file_id", None) or obj
                break
        if target is None:
            target = self._raw
        try:
            return await self._client.download_media(target, *a, **kw)
        except Exception as e:
            print(f"result download_media hata: {e}", flush=True)
            return None


class InlineResults(list):
    """Telethon'da liste gibi davranır + query_id taşır."""

    query_id = None
    bot = None

    def shuffled(self):
        out = InlineResults(self)
        out.query_id = self.query_id
        out.bot = self.bot
        random.shuffle(out)
        return out


def wrap_inline_results(raw_results, query_id, bot_name, client):
    """Pyrogram sonuçlarını Telethon uyumlu proxy'lere çevirir."""
    out = InlineResults()
    out.query_id = query_id
    out.bot = str(bot_name).lstrip("@") if bot_name else None
    for r in raw_results or []:
        out.append(ResultProxy(r, query_id, out.bot, client))
    return out


async def inline_query(client, bot_username, query, **kw):
    """client.inline_query(bot, query) — Telethon imzası."""
    name = str(bot_username).lstrip("@")
    try:
        res = await client.get_inline_bot_results(name, query)
    except Exception as e:
        print(f"inline_query hata ({name}): {e}", flush=True)
        raise
    results = getattr(res, "results", None)
    if results is None and isinstance(res, (list, tuple)):
        return wrap_inline_results(list(res), None, name, client)
    return wrap_inline_results(list(results or []), getattr(res, "query_id", None), name, client)
