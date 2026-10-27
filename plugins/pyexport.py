# ✦ Log2 Alfa .py — metni/kodu .py dosyasına çevirip gönderir
#
# Kullanım:
#   .py                  → yanıtlanan mesajdaki kodu/metni .py dosyası yapıp gönderir
#   .py dosyaadi.py      → dosya adını sen belirlersin
#   .py print("selam")   → yanıt yoksa komuttan sonrası kod kabul edilir
#
# Yanıtlanan mesaj metin, açıklama (caption) veya bir belge (.py/.txt/...) olabilir.
import os
import re
import time
import textwrap

from userbot.events import register
from userbot.cmdhelp import CmdHelp
from utils.fonts import smalls as S

BRAND = "@Log2Alfa"
MAX_BYTES = 400 * 1024  # belge yanıtı için üst sınır

USAGE = (S("✦ .ᴘʏ — ᴀʀᴀᴄ̧ʟᴀʀ") + "\n\n"
         "`.py` (mesaja yanıtla)\n"
         "`.py dosyaadi.py` (mesaja yanıtla)\n"
         "`.py <kod>`\n")


def _clean_code(text: str) -> str:
    """Markdown ``` bloklarını temizler ve girintiyi düzeltir."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for ln in text.split("\n"):
        if ln.strip().startswith("```"):
            continue
        out.append(ln)
    code = "\n".join(out)
    try:
        ded = textwrap.dedent(code)
        if ded.strip():
            code = ded
    except Exception:
        pass
    return code.strip("\n")


def _default_name() -> str:
    return f"log2alfa_{time.strftime('%Y%m%d_%H%M%S')}.py"


def _safe_name(arg: str, fallback: str) -> str:
    """Kullanıcı argümanını güvenli dosya adına çevirir, .py uzantısını garanti eder."""
    name = (arg or "").strip().strip("`\"'")
    if not name:
        return fallback
    name = os.path.basename(name.replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9_.\-]", "_", name)
    if not base:
        return fallback
    if base.lower().endswith(".py"):
        base = base[:-3]
    base = (base or "log2alfa").strip("._-") or "log2alfa"
    return (base[:56] + ".py")


def _looks_like_filename(arg: str) -> bool:
    a = (arg or "").strip()
    return bool(a) and "\n" not in a and len(a) <= 64 and not re.search(r"[^\w\-.\s]", a)


async def _from_reply(rep):
    """Yanıtlanan mesajdan kodu çıkarır → (kod|None, kaynak/uyarı)."""
    if getattr(rep, "text", None):
        return _clean_code(rep.text), "metin"
    if getattr(rep, "caption", None):
        return _clean_code(rep.caption), "açıklama"
    doc = getattr(rep, "document", None)
    if doc is not None:
        size = getattr(doc, "file_size", 0) or 0
        if size and size > MAX_BYTES:
            return None, f"belge çok büyük ({size // 1024} KB > {MAX_BYTES // 1024} KB)"
        path = None
        try:
            path = await rep.download()
        except Exception:
            try:
                path = await rep.download_media()
            except Exception:
                path = None
        if not path:
            return None, "belge indirilemedi"
        try:
            with open(path, "rb") as f:
                raw = f.read()
        finally:
            try:
                os.remove(path)
            except Exception:
                pass
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return _clean_code(raw.decode(enc)), "belge"
            except Exception:
                continue
        return None, "belge metne çevrilemedi (binary dosya)"
    return None, "yanıtlanan mesajda metin/kod yok"


@register(outgoing=True, pattern=r"^\.py(?: |$)(.*)")
async def py_export(event):
    arg = ((event.pattern_match.group(1) or "") if event.pattern_match else "").strip()
    rep = await event.get_reply_message()

    if rep is not None:
        code, src = await _from_reply(rep)
        if not code or not code.strip():
            return await event.edit(S("✦ ᴅᴏsʏᴀ ʏᴀᴘıʟᴀᴍᴀᴅı: ") + f"`{src}`\n\n" + USAGE)
        fname = _safe_name(arg, _default_name()) if arg else _default_name()
        kaynak = src
    else:
        if not arg:
            return await event.edit(USAGE)
        if _looks_like_filename(arg) and arg.lower().endswith(".py"):
            return await event.edit(
                S("✦ ɪᴄᴇʀɪᴋ ɢᴇʀᴇᴋʟɪ: ") + "`.py " + arg + "` "
                + S("ɪᴄɪɴ ʙɪʀ ᴋᴏᴅ/ᴍᴇᴛɪɴ ᴍᴇsᴀᴊıɴı ʏᴀɴıᴛʟᴀ."))
        code = _clean_code(arg)
        fname = _default_name()
        kaynak = "komut"

    lines = code.count("\n") + 1
    size = len(code.encode("utf-8"))
    path = os.path.join("/tmp", fname)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(code if code.endswith("\n") else code + "\n")
    except Exception as e:
        return await event.edit(f"`Dosya yazılamadı: {e}`")

    cap = (f"📄 `{fname}`\n"
           + S(f"{lines} satır") + " • " + f"{max(1, round(size / 1024))} KB"
           + ("" if kaynak == "komut" else " • " + S(kaynak))
           + f"\n✦ {BRAND}")

    try:
        try:
            await event.reply(cap, file=path)
        except Exception:
            client = getattr(event, "client", None) or getattr(event, "_client", None)
            await client.send_document(event.chat_id, path, caption=cap,
                                       reply_to_message_id=getattr(getattr(event, "_message", None), "id", None))
        try:
            await event.delete()
        except Exception:
            pass
    except Exception as e:
        try:
            await event.edit(f"`Gönderilemedi: {e}`")
        except Exception:
            pass
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


Help = CmdHelp("pyexport")
Help.add_command("py", "[dosya adı]",
                 "Yanıtlanan mesajdaki kodu/metni .py dosyası yapıp gönderir.")
Help.add_info("@Log2Alfa • kod/metin → .py dosyası")
Help.add()
