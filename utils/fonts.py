"""
Smalls font — Telegram'da küçük görünen yazı tipi
Unicode small caps mapping ile estetik, sanki sen yapmışsın gibi
Not: Sayılar normal kalır (düzenli, okunabilir olsun diye)
"""
SMALLS_MAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ', 'h': 'ʜ',
    'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ',
    'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
    'y': 'ʏ', 'z': 'ᴢ',
    'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ғ', 'G': 'ɢ', 'H': 'ʜ',
    'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ',
    'Q': 'ǫ', 'R': 'ʀ', 'S': 's', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x',
    'Y': 'ʏ', 'Z': 'ᴢ',
    # Türkçe karakterler — small caps uyumlu
    'ş': 'ş', 'Ş': 'ş', 'ğ': 'ɢ', 'Ğ': 'ɢ', 'ü': 'ᴜ', 'Ü': 'ᴜ', 'ö': 'ᴏ', 'Ö': 'ᴏ',
    'ç': 'ᴄ', 'Ç': 'ᴄ', 'ı': 'ı', 'İ': 'ɪ',
    # Sayılar bilerek dönüştürülmüyor — düzenli kalsın
}

def smalls(text: str) -> str:
    """Metni small caps'e çevir — sayılar normal kalır"""
    return ''.join(SMALLS_MAP.get(c, c) for c in text)

def smalls_bold(text: str) -> str:
    """Small + bold markdown"""
    return f"**{smalls(text)}**"

# Hazır estetik başlıklar
def title(text: str) -> str:
    return f"**{smalls(text)}**"

def mono_small(text: str) -> str:
    return f"`{smalls(text)}`"
