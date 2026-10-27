"""Müzik indirme — .indir <şarkı ismi veya youtube linki>
Railway IP YouTube bot-check'e takıldığı için loader.to API birincil yol.
Komut silinir, parça metinsiz gönderilir (sanatçı: Log2Alfa).
"""
import os, re, json, time, tempfile, urllib.request, urllib.parse, shutil
from pyrogram import Client, filters
from utils.security import rate_limit
from utils.helpers import respond
from utils.fonts import smalls

YT_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([a-zA-Z0-9_-]{11})",
    re.I,
)
VID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
PERFORMER = "Log2Alfa"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://loader.to/",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _http_json(url: str, timeout: int = 30) -> dict:
    return json.loads(_http_get(url, timeout=timeout).decode("utf-8", "ignore"))


def _extract_video_id(text: str) -> str | None:
    m = YT_RE.search(text or "")
    if m:
        return m.group(1)
    t = (text or "").strip()
    if VID_RE.match(t):
        return t
    return None


def _search_video_id(query: str) -> tuple[str | None, str | None]:
    """(video_id, title_hint) — YouTube results HTML"""
    q = query.strip()
    try:
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            page = r.read().decode("utf-8", "ignore")
        ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', page)
        titles = re.findall(r'"title":\{"runs":\[\{"text":"(.*?)"\}', page)
        seen, ordered = set(), []
        for i in ids:
            if i not in seen:
                seen.add(i)
                ordered.append(i)
        if ordered:
            tip = None
            if titles:
                try:
                    tip = titles[0].encode("utf-8").decode("unicode_escape", "ignore")
                except Exception:
                    tip = titles[0]
            return ordered[0], tip
    except Exception as e:
        print(f"yt search hata: {e}", flush=True)
    return None, None


def _loader_to_download(video_id: str, tmpdir: str) -> tuple[str, str]:
    """
    loader.to AJAX API — YouTube bot-check'ten bağımsız.
    (filepath, title)
    """
    yt = f"https://www.youtube.com/watch?v={video_id}"
    title = "şarkı"
    last_err = None
    for fmt in ("mp3", "m4a"):
        try:
            start_url = (
                "https://loader.to/ajax/download.php?"
                + urllib.parse.urlencode({"format": fmt, "url": yt})
            )
            data = _http_json(start_url, timeout=25)
            if not data.get("success"):
                last_err = str(data)
                continue
            title = (
                (data.get("info") or {}).get("title")
                or data.get("title")
                or title
            )[:120]
            prog = data.get("progress_url")
            if not prog:
                last_err = "progress_url yok"
                continue
            dl_url = None
            for _ in range(40):  # ~60sn
                time.sleep(1.5)
                try:
                    p = _http_json(prog, timeout=20)
                except Exception as e:
                    last_err = f"progress: {e}"
                    continue
                dl_url = p.get("download_url") or p.get("url")
                prog_n = int(p.get("progress") or 0)
                ok = p.get("success")
                if dl_url and (ok == 1 or ok is True or prog_n >= 1000):
                    break
                if ok == 0 and prog_n == 0 and p.get("text") and "error" in str(p.get("text")).lower():
                    last_err = str(p.get("text"))
                    dl_url = None
                    break
            if not dl_url:
                last_err = last_err or "indirme linki gelmedi"
                continue
            raw = _http_get(dl_url, timeout=120)
            if not raw or len(raw) < 2048:
                last_err = f"dosya küçük ({len(raw) if raw else 0})"
                continue
            ext = "mp3" if fmt == "mp3" else "m4a"
            # content-type ipucu
            if raw[:3] == b"ID3" or raw[:2] == b"\xff\xfb":
                ext = "mp3"
            fpath = os.path.join(tmpdir, f"{video_id}.{ext}")
            with open(fpath, "wb") as f:
                f.write(raw)
            print(f"loader.to OK {title} {len(raw)}B fmt={fmt}", flush=True)
            return fpath, title
        except Exception as e:
            last_err = str(e)
            print(f"loader.to {fmt} hata: {e}", flush=True)
    raise RuntimeError(last_err or "loader.to başarısız")


def _ydl_download(video_id: str, tmpdir: str) -> tuple[str, str]:
    """yt-dlp yedek (android_sdkless) — bazı ortamlarda çalışır."""
    import yt_dlp

    target = f"https://www.youtube.com/watch?v={video_id}"
    outtmpl = os.path.join(tmpdir, "%(id)s.%(ext)s")
    for clients in (["android_sdkless"], ["tv_embedded"], ["android_sdkless", "tv_embedded"]):
        opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "restrictfilenames": True,
            "geo_bypass": True,
            "retries": 3,
            "extractor_args": {"youtube": {"player_client": clients}},
        }
        if shutil.which("ffmpeg"):
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "0",
            }]
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(target, download=True)
            if isinstance(info, dict) and info.get("_type") == "playlist":
                entries = [e for e in (info.get("entries") or []) if e]
                info = entries[0] if entries else {}
            title = (info.get("title") or "şarkı")[:120] if isinstance(info, dict) else "şarkı"
            files = [
                f for f in os.listdir(tmpdir)
                if os.path.isfile(os.path.join(tmpdir, f)) and not f.startswith(".")
            ]
            if not files:
                raise RuntimeError("dosya yok")
            files.sort(key=lambda f: os.path.getsize(os.path.join(tmpdir, f)), reverse=True)
            fpath = os.path.join(tmpdir, files[0])
            if os.path.getsize(fpath) < 2048:
                raise RuntimeError("dosya küçük")
            return fpath, title
        except Exception as e:
            print(f"ydl {clients} hata: {e}", flush=True)
            for f in list(os.listdir(tmpdir)):
                try:
                    os.remove(os.path.join(tmpdir, f))
                except Exception:
                    pass
    raise RuntimeError("yt-dlp başarısız")


def _download_audio_file(video_id: str, tmpdir: str) -> tuple[str, str]:
    # 1) loader.to (Railway'de çalışır)
    try:
        return _loader_to_download(video_id, tmpdir)
    except Exception as e1:
        print(f".indir loader fail: {e1}", flush=True)
    # 2) yt-dlp yedek
    return _ydl_download(video_id, tmpdir)


@rate_limit(5)
async def download_music_handler(client: Client, message):
    args = " ".join(message.command[1:]).strip()
    if not args:
        await respond(client, message, smalls("kullanım: .indir <şarkı ismi veya youtube linki>"))
        return

    video_id = _extract_video_id(args)
    title_hint = None
    if not video_id:
        if len(args) < 2:
            await respond(client, message, smalls("şarkı ismi veya youtube linki ver"))
            return
        try:
            await message.edit_text(smalls(f"🔎 aranıyor — {args[:50]}"))
        except Exception:
            pass
        video_id, title_hint = _search_video_id(args)
        if not video_id:
            await respond(client, message, smalls("şarkı bulunamadı — başka isim dene"))
            return

    try:
        await message.edit_text(smalls(f"⬇️ indiriliyor — {(title_hint or args)[:50]}"))
    except Exception:
        pass

    tmpdir = tempfile.mkdtemp(prefix="indir_")
    sent = False
    err_msg = None
    try:
        fpath, title = _download_audio_file(video_id, tmpdir)
        chat_id = message.chat.id
        try:
            await message.delete()
        except Exception:
            pass
        ext = fpath.rsplit(".", 1)[-1].lower()
        try:
            if ext in ("m4a", "mp3", "ogg", "opus", "flac", "wav", "aac", "webm", "mp4"):
                await client.send_audio(
                    chat_id,
                    fpath,
                    title=(title or "şarkı")[:120],
                    performer=PERFORMER,
                )
            else:
                await client.send_document(chat_id, fpath)
            sent = True
            print(f".indir tamam: {title} ({os.path.getsize(fpath)}B) vid={video_id}", flush=True)
        except Exception as e:
            try:
                await client.send_document(chat_id, fpath)
                sent = True
            except Exception as e2:
                err_msg = f"gönderim: {e} / {e2}"
                print(f".indir gönderim hatası: {err_msg}", flush=True)
    except Exception as e:
        err_msg = str(e)
        print(f".indir hata: {err_msg[:300]}", flush=True)
    finally:
        try:
            for f in os.listdir(tmpdir):
                try:
                    os.remove(os.path.join(tmpdir, f))
                except Exception:
                    pass
            os.rmdir(tmpdir)
        except Exception:
            pass

    if not sent:
        tip = "indirmede hata — tekrar dene"
        el = (err_msg or "").lower()
        if "not available" in el or "private" in el or "unavailable" in el:
            tip = "video yok / gizli — başka isim dene"
        elif "bulunamadı" in el:
            tip = "şarkı bulunamadı — başka isim dene"
        try:
            await respond(client, message, smalls(tip))
        except Exception:
            try:
                await client.send_message(message.chat.id, smalls(tip))
            except Exception:
                pass


def register_handlers(app: Client):
    from pyrogram.handlers import MessageHandler
    app.add_handler(MessageHandler(
        download_music_handler,
        filters.command(["indir", "download"], prefixes=".") & (filters.me | filters.outgoing),
    ))
