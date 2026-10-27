# ✦ Log2 Alfa .sex — emojili yazışma animasyonu
#
# Kullanım:
#   .sex   → sırayla animasyon karelerini yazar (her kare 2 sn)
#
# Not: Metin sana ait; sadece emoji ve küçük yazım düzeltmeleri eklendi.
import asyncio

from userbot.events import register
from userbot.cmdhelp import CmdHelp
from utils.fonts import smalls as S

BRAND = "@Log2Alfa"

# Her kare 2 saniye arayla yazılır. İstediğin gibi düzenleyebilirsin.
ANIMASYON = [
    "🤭 Sana Bir...",
    "😏 şey söyleyeceğim...",
    "😳 çok fena...",
    "🔥 yükseliyorum...",
    "😘 sana ben...",
    "🥵 o yüzden...",
    "😈 altıma gelemeye...",
    "💋 Ne dersin?",
    "💖 Aşkım...",
    "💞 AŞKİMM...",
    "💘 AŞKİMMMMMMM!!!",
    "🫶 hElElelelelele 🤝✨",
]

STEP = 2  # kare süresi (saniye)


@register(outgoing=True, pattern=r"^\.sex(?: |$)(.*)")
async def sexanim(event):
    for anim in ANIMASYON:
        try:
            await event.edit(anim)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # Mesaj silindiyse / flood olduysa animasyonu sessizce bitir
            print(f"sexanim durdu: {e}", flush=True)
            return
        await asyncio.sleep(STEP)


Help = CmdHelp("sexanim")
Help.add_command("sex", "", "Emojili yazışma animasyonu (12 kare, 2 sn arayla).")
Help.add_info(f"{BRAND} • animasyon komutu")
Help.add()
