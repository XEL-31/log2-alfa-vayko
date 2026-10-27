# ✦ Log2 Alfa Özel Efekt Paketi — @Log2Alfa
# 15 metin efekti + 13 görsel efekt (hepsi offline, hatasız)
#
# Komutlar:
#   .fx             → metin efekti listesi  (alias: .fx liste)
#   .fx <efekt> <metin>  ya da  (bir mesajı yanıtla) .fx <efekt>
#   .efekt          → görsel efekt listesi  (alias: .efekt liste)
#   .efekt <ad>     → (fotoğrafa/kişiye yanıtla) efekt uygular
#   .efekt rastgele → rastgele efekt
import asyncio

from userbot.events import register
from userbot.cmdhelp import CmdHelp
from utils.fonts import smalls
from utils.canvas import apply_effect, is_gif_effect, FX_LIST, target_media, cleanup

S = smalls
BRAND = "@Log2Alfa"


# ───────────────────────── metin efektleri ─────────────────────────

_EXC = {
    "script": {"B": "ℬ", "E": "ℰ", "F": "ℱ", "H": "ℋ", "I": "ℐ", "L": "ℒ", "M": "ℳ", "R": "ℛ",
               "e": "ℯ", "g": "ℊ", "o": "ℴ"},
    "fraktur": {"C": "ℭ", "H": "ℌ", "I": "ℑ", "R": "ℜ", "Z": "ℨ"},
    "double": {"C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ", "R": "ℝ", "Z": "ℤ"},
}


def _map_alpha(text, up_base, lo_base, exc=None, digits=None):
    out = []
    for ch in text:
        o = ord(ch)
        if 65 <= o <= 90:
            out.append((exc or {}).get(ch) or chr(up_base + o - 65))
        elif 97 <= o <= 122:
            out.append((exc or {}).get(ch) or chr(lo_base + o - 97))
        elif digits and 48 <= o <= 57:
            out.append(chr(digits + o - 48))
        else:
            out.append(ch)
    return "".join(out)


_FLIP = {"a": "ɐ", "b": "q", "c": "ɔ", "d": "p", "e": "ǝ", "f": "ɟ", "g": "ƃ", "h": "ɥ", "i": "ᴉ",
         "j": "ɾ", "k": "ʞ", "l": "l", "m": "ɯ", "n": "u", "o": "o", "p": "d", "q": "b", "r": "ɹ",
         "s": "s", "t": "ʇ", "u": "n", "v": "ʌ", "w": "ʍ", "x": "x", "y": "ʎ", "z": "z",
         "A": "∀", "B": "𐐒", "C": "Ɔ", "D": "ᗡ", "E": "Ǝ", "F": "Ⅎ", "G": "⅁", "H": "H", "I": "I",
         "J": "ſ", "K": "ʞ", "L": "˥", "M": "W", "N": "N", "O": "O", "P": "Ԁ", "Q": "Ό", "R": "ᴚ",
         "S": "S", "T": "⊥", "U": "∩", "V": "Λ", "W": "M", "X": "X", "Y": "⅄", "Z": "Z",
         "!": "¡", "?": "¿", ".": "˙", ",": "'", "'": ",", '"': "„", ";": "؛", "(": ")", ")": "(",
         "[": "]", "]": "[", "{": "}", "}": "{", "_": "‾"}
_BUBBLE = {"a": "ⓐ", "b": "ⓑ", "c": "ⓒ", "d": "ⓓ", "e": "ⓔ", "f": "ⓕ", "g": "ⓖ", "h": "ⓗ", "i": "ⓘ",
           "j": "ⓙ", "k": "ⓚ", "l": "ⓛ", "m": "ⓜ", "n": "ⓝ", "o": "ⓞ", "p": "ⓟ", "q": "ⓠ", "r": "ⓡ",
           "s": "ⓢ", "t": "ⓣ", "u": "ⓤ", "v": "ⓥ", "w": "ⓦ", "x": "ⓧ", "y": "ⓨ", "z": "ⓩ"}
_SCRIPT_LOWER = dict(_BUBBLE)
for _k, _v in list(_BUBBLE.items()):
    _BUBBLE[_k.upper()] = _v.upper().replace("ⓐ", "Ⓐ")


def fx_kalin(t):
    return _map_alpha(t, 0x1D400, 0x1D41A, None, 0x1D7CE)


def fx_egik(t):
    # eğik 'h' boşluk: ℎ ile doldur
    return _map_alpha(t, 0x1D434, 0x1D44E, {"h": "ℎ"})


def fx_kalin_egik(t):
    return _map_alpha(t, 0x1D468, 0x1D482)


def fx_script(t):
    return _map_alpha(t, 0x1D49C, 0x1D4B6, _EXC["script"])


def fx_fraktur(t):
    return _map_alpha(t, 0x1D504, 0x1D51E, _EXC["fraktur"])


def fx_cift(t):
    return _map_alpha(t, 0x1D538, 0x1D552, _EXC["double"], 0x1D7D8)


def fx_mono(t):
    return _map_alpha(t, 0x1D670, 0x1D68A, None, 0x1D7F6)


def fx_genis(t):
    return "".join(chr(ord(c) + 0xFEE0) if 0x21 <= ord(c) <= 0x7E else
                   ("　" if c == " " else c) for c in t)


def fx_smalls(t):
    return smalls(t)


def fx_ters(t):
    return "".join(_FLIP.get(c, c) for c in reversed(t))


def fx_balon(t):
    return "".join(_BUBBLE.get(c, c) for c in t)


def fx_karali(t):
    return "".join((c + "\u0336") if c != " " else " " for c in t)


def fx_alt_cizgi(t):
    return "".join(c + "\u0332" for c in t)


def fx_kutu(t):
    return "「 " + t + " 」"


def fx_yildiz(t):
    return "✦ " + t + " ✦"


TEXT_FX = {
    "kalin": (fx_kalin, "Kalın harfler"),
    "egik": (fx_egik, "Eğik harfler"),
    "kalegik": (fx_kalin_egik, "Kalın eğik"),
    "script": (fx_script, "El yazısı"),
    "fraktur": (fx_fraktur, "Gotik"),
    "cift": (fx_cift, "Çift çizgi (matematik)"),
    "mono": (fx_mono, "Eş aralıklı"),
    "genis": (fx_genis, "Geniş (full-width)"),
    "smalls": (fx_smalls, "ᴋüçüᴋ ᴋᴀᴘs"),
    "ters": (fx_ters, "ǝʇsǝɹʇ"),
    "balon": (fx_balon, "Balon harf"),
    "karali": (fx_karali, "Üstü çizili"),
    "altcizgi": (fx_alt_cizgi, "Altı çizili"),
    "kutu": (fx_kutu, "Çerçeveli"),
    "yildiz": (fx_yildiz, "Yıldızlı"),
}
TEXT_ALIASES = {
    "bold": "kalin", "italic": "egik", "kalın": "kalin", "eğik": "egik",
    "el": "script", "gotik": "fraktur", "matematik": "cift", "büyük": "genis",
    "upside": "ters", "çiz": "karali", "cerceve": "kutu", "çerçeve": "kutu",
}


# ───────────────────────── .fx metin efekti ─────────────────────────

@register(outgoing=True, pattern=r"^\.fx(?: |$)(.*)")
async def fx_cmd(event):
    raw = (event.pattern_match.group(1) or "").strip() if event.pattern_match else ""
    if not raw:
        lines = [S("✦ ᴍᴇᴛɪɴ ᴇғᴇᴋᴛʟᴇʀɪ") + f"  ({len(TEXT_FX)})", "━━━━━━━━━━━━━━━━"]
        for name, (_fn, desc) in TEXT_FX.items():
            lines.append(f"• `.{'fx ' + name}` — {desc}")
        lines += ["━━━━━━━━━━━━━━━━",
                  S("ᴋᴜʟʟᴀɴɪᴍ: ") + "`.fx kalin merhaba`",
                  S("ᴠᴇʏᴀ: ʙɪʀ ᴍᴇsᴀᴊᴀ ʏᴀɴɪᴛʟᴀʏɪᴘ ") + "`.fx ters`"]
        return await event.edit("\n".join(lines))

    parts = raw.split(maxsplit=1)
    name = TEXT_ALIASES.get(parts[0].lower(), parts[0].lower())
    fn = TEXT_FX.get(name, (None, ""))[0]
    if not fn:
        return await event.edit(S("✦ ʙɪʟɪɴᴍᴇʏᴇɴ ᴇғᴇᴋᴛ: ") + f"`{parts[0]}`\n" + S("ʟɪsᴛᴇ ɪçɪɴ: ") + "`.fx`")

    text = parts[1] if len(parts) > 1 else ""
    if not text:
        reply = await event.get_reply_message()
        if reply:
            text = (getattr(reply, "text", None) or getattr(reply, "caption", None) or "").strip()
    if not text:
        return await event.edit(S("✦ ᴍᴇᴛɪɴ ɢᴇʀᴇᴋ: ") + f"`.fx {name} merhaba`")

    try:
        out = fn(text)[:1000]
    except Exception as e:
        return await event.edit(f"`fx hata: {e}`")
    try:
        await event.edit(out)
    except Exception:
        await event.client.send_message(event.chat_id, out)


# ───────────────────────── .efekt görsel efekt ─────────────────────────

def _efekt_list_text():
    lines = [S("✦ ᴠɪᴢʏᴏɴ ᴇғᴇᴋᴛʟᴇʀɪ") + f"  ({len(FX_LIST)})", "━━━━━━━━━━━━━━━━"]
    for name, desc, kind in FX_LIST:
        tag = "🎞" if kind == "gif" else "🖼"
        lines.append(f"{tag} `.{'efekt ' + name}` — {desc}")
    lines += ["━━━━━━━━━━━━━━━━",
              S("ᴋᴜʟʟᴀɴɪᴍ: ғᴏᴛᴏğʀᴀғᴀ/ᴋɪşɪʏᴇ ʏᴀɴɪᴛʟᴀʏɪᴘ ") + "`.efekt neon`",
              S("ʀᴀsᴛɢᴇʟᴇ ɪçɪɴ: ") + "`.efekt rastgele`"]
    return "\n".join(lines)


@register(outgoing=True, pattern=r"^\.efekt(?: |$)(.*)")
async def efekt_cmd(event):
    import random
    arg = ((event.pattern_match.group(1) or "") if event.pattern_match else "").strip().lower()
    if arg in ("liste", "list", "yardim", "yardım", "help"):
        arg = ""
    if not arg:
        return await event.edit(_efekt_list_text())

    names = [n for n, _d, _k in FX_LIST]
    if arg in ("rastgele", "random"):
        arg = random.choice(names)
    if arg not in names:
        return await event.edit(S("✦ ʙɪʟɪɴᴍᴇʏᴇɴ ᴇғᴇᴋᴛ: ") + f"`{arg}`\n" + S("ʟɪsᴛᴇ ɪçɪn: ") + "`.efekt`")

    reply = await event.get_reply_message()
    if not reply:
        return await event.edit(S("✦ ʙɪʀ ғᴏᴛᴏğʀᴀғᴀ ᴠᴇʏᴀ ᴋɪşɪʏᴇ ʏᴀɴɪᴛʟᴀʏɪɴ."))

    await event.edit(S("✦ ᴇғᴇᴋᴛ ᴜʏɢᴜʟᴀɴɪʏᴏʀ: ") + f"`{arg}`")
    uid = getattr(getattr(reply, "from_user", None), "id", None) or getattr(reply, "from_id", None)
    path = await target_media(event.client, reply, uid)
    if not path:
        return await event.edit(S("✦ ɢöʀsᴇʟ ʙᴜʟᴜɴᴀᴍᴀᴅɪ (ғᴏᴛᴏğʀᴀғᴀ ʏᴀɴɪᴛʟᴀ)."))
    out = apply_effect(arg, path)
    if not out:
        cleanup(path)
        return await event.edit(S("✦ ᴇғᴇᴋᴛ ᴜʏɢᴜʟᴀɴᴀᴍᴀᴅɪ, ᴛᴇᴋʀᴀʀ ᴅᴇɴᴇ."))
    cap = f"✨ {arg.upper()}  •  {BRAND}"
    try:
        if is_gif_effect(arg):
            await event.client.send_animation(event.chat_id, out, caption=cap,
                                              reply_to_message_id=getattr(reply, "id", None))
        else:
            await event.client.send_photo(event.chat_id, out, caption=cap,
                                          reply_to_message_id=getattr(reply, "id", None))
        await event.delete()
    except Exception as e:
        await event.edit(f"`Gönderilemedi: {e}`")
    finally:
        cleanup(path, out)


# ───────────────────────── yardım kayıtları ─────────────────────────

Help = CmdHelp("log2alfa")
Help.add_command("fx", "[efekt] [metin]", "Metin efektleri (15 çeşit).")
Help.add_command("efekt", "[ad|rastgele]", "Görsel efektler (12 çeşit, offline).")
Help.add_info("@Log2Alfa • Gösterişli efekt paketi")
Help.add()