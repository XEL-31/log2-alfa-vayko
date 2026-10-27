import time
start_time = time.time()

def get_uptime():
    s = int(time.time() - start_time)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = []
    if d: parts.append(f"{d}g")
    if h: parts.append(f"{h}s")
    if m: parts.append(f"{m}d")
    parts.append(f"{s}sn")
    return " ".join(parts)

# Log2Alfa
ALIVE_MSGS = [
    "🟢 Log2Alfa aktif",
    "⚡ Buradayım, emrindeyim",
    "🤖 Çalışıyorum, her şey yolunda",
    "👑 Hazırım, emir bekliyorum",
    "🔥 Hazırım, test et",
    "📡 Tüm sistemler çalışıyor",
    "🛡 Stabil mod — ban korumalı",
    "💤 Uyumuyorum, her an hazır",
    "⚙️ Sistem hazır",
    "🚀 Hızlı ve stabilim",
]

from utils.fonts import smalls as _smalls

_HELP_RAW = """✦ Log2Alfa • Yardım
━━━━━━━━━━━━━━━━

• .log2alfa — durum
• .ping — hız
• .help — bu menü
• .phelp — tüm pluginler ve komutları
• .afk <sebep> — afk aç/kapat

Yönetim (gruplarda):
• .ban (yanıtla/@) — ban
• .unban — kaldır
• .kick — at
• .mute / .unmute — sustur/aç
• .promote / .demote — yetki ver/al
• .pin — sabitle (yanıtla)
• .purge/.del — sil (yanıtla)
• .tagall [yazı] — herkesi etiketle
• .dur — tagall durdur
• .gban / .gmute (yanıtla/@) — global yasak / sustur
• .ungban / .ungmute — kaldır

Bilgi:
• .id — id göster
• .info / .whois — kişi bilgisi
• .chatinfo — grup bilgisi

Notlar:
• .nsave <ad> (mesaja yanıtla) — not kaydet
• .not <ad> — notu göster
• .notlar — notları listele
• .notsil <ad|hepsi> — not sil
• #ad — notu çağır

Araçlar:
• .hava <sehir> — hava durumu
• .hesap <islem> — hesap makinesi
• .ai <soru> — yapay zeka
• .py (mesaja yanıtla) — .py dosyası olarak gönder
• .save <link> — medya kaydet (yanıtla)
• .fx <efekt> <metin>
• .fx liste
• .efekt <ad> (fotoğrafa yanıtla)
• .efekt rastgele
• .efekt liste

━━━━━━━━━━━━━━━━
→ .help <komut> ile detay — örnek: .help ban
→ Pluginler için .phelp yazın
"""

HELP_TEXT = _smalls(_HELP_RAW)

MENU_TEXT = """**Log2Alfa • Menu**

• .log2alfa • .help • .ping • .id
• .ban • .purge • .tagall

→ .help ile detay
"""

SAVED_MSG_TEXT = """🎉 Sevgili {name}, Log2Alfa Kurulumunuz Başarıyla tamamlanmıştır. daha fazla bilgi için .help Komutunu kullanınız.

➥ vayko • t.me/vaykoo ✨
"""

LOG2ALFA_RESPONSES = []
COMPAT_RESPONSES = LOG2ALFA_RESPONSES  # eski kod uyumu

async def respond(client, message, text):
    try:
        await message.edit_text(text)
        return "edit"
    except Exception:
        try:
            await message.reply_text(text)
            return "reply"
        except Exception as e:
            print(f"respond hata: {e}", flush=True)
            return None
