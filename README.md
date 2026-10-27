# 🚀 Log2 Alfa Userbot v2.0 - Pro

**Profesyonel Telegram Userbot + Bot Yönetim Paneli**

Kişisel Telegram hesabına giriş yap, `.log2alfa` gibi komutları sadece **senin hesabın** algılasın. Tamamen buttonlu yönetim paneli, ban korumalı altyapı.

---

## ✨ Özellikler

### 🤖 Bot Yönetim Paneli (`/start`)
- 🔑 **Hesaba Giriş Yap** - API_ID / API_HASH / Telefon ile adım adım
- 📊 **Userbot Paneli** - Durum, Uptime, Aktif sayısı
- 📖 **Yardım** - Kurulum rehberi
- 📋 **Komut Menüsü** - Tüm komutlar
- 👨‍💻 **Geliştirici** - Proje bilgisi
- 🛡️ **Güvenlik** - Ban riski azaltma rehberi
- 🔴 **Oturumu Kapat** - Userbotu durdur & sil

### 🛰️ Userbot Komutları (sadece giren hesapta çalışır)
| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `.alfa` / `.log2alfa` / `.alive` | Efendim? Buyrun, Aktifim! | `.log2alfa` |
| `.help` / `.menu` | Yardım menüsü | `.help` |
| `.ping` | Ping ölçer | `.ping` |
| `.id` | Chat/Kullanıcı ID | `.id` (yanıtla) |
| `.info` | Kullanıcı bilgisi | `.info` (yanıtla) |
| `.yaz <metin>` | Daktilo efekti | `.yaz merhaba` |
| `.caps <metin>` | BÜYÜK HARF | `.caps selam` |
| `.afk <sebep>` | AFK modu | `.afk yemekteyim` |
| `.hava <şehir>` | Hava durumu | `.hava Istanbul` |

> **Güvenlik:** Tüm komutlar `filters.me` ile korunuyor. Başkası yazınca **asla** yanıt vermez.

### 🛡️ Ban Koruması
- ✅ `FloodWait` otomatik `await asyncio.sleep(e.value)`
- ✅ `Rate-limit` (2 sn'de 1 komut)
- ✅ Sadece kendi mesajını `edit` eder, spam mesaj atmaz
- ✅ Toplu işlemlerde `human_delay`
- ✅ Kayıtlı Mesajlara bilgilendirme + uyarı

---

## 🚂 Railway Kurulumu

### 1. Bot Token Al
- @BotFather -> `/newbot` -> İsim ver -> Token kopyala

### 2. API_ID / API_HASH Al
- https://my.telegram.org -> Log in -> API Development Tools
- App title: `Log2 Alfa`, Short name: `log2alfa`, Platform: `Other` -> Create
- `API_ID` (sayı) ve `API_HASH` (32 karakter) kopyala

### 3. Railway'e Deploy
```bash
# Railway CLI ile (zaten giriş yaptın)
railway link  # Log2 Alfa projesini seç
railway up    # veya GitHub'dan deploy
```

**Railway Variables (Environment):**
```
BOT_TOKEN=123456789:AAH...
API_ID=12345678
API_HASH=abcdef...
OWNER_ID=0  # opsiyonel, 0 = herkese açık, ID girersen sadece sen
```

### 4. Giriş Yap
- Botuna git -> `/start` -> `🔑 Hesaba Giriş Yap`
- API_ID -> API_HASH -> Telefon (+90...) -> Kod (1 2 3 4 5) -> 2FA varsa şifre
- ✅ Başarılı -> **Kayıtlı Mesajlarına** bildirim gelecek
- Test: Herhangi bir chatte `.alfa` yaz

---

## 💻 Lokal Çalıştırma

```bash
git clone <repo>
cd log2alfa-userbot
pip install -r requirements.txt
cp .env.example .env  # doldur
python main.py
```

---

## 📁 Yapı

```
log2alfa-userbot/
├── main.py              # Ana çalıştırıcı (Bot + Userbot)
├── config.py            # Ayarlar
├── database.py          # SQLite (aiosqlite)
├── bot_controller.py    # /start, login flow, paneller
├── userbot_core.py      # Userbot oluşturma, ban koruması, Saved Messages
├── handlers/
│   ├── alive.py         # .log2alfa, .ping, .yaz, .caps
│   ├── help_menu.py     # .help, .menu, .id, .info
│   └── tools.py         # .afk, .hava
├── utils/
│   ├── helpers.py       # ALIVE, HELP metinleri, uptime
│   └── security.py      # FloodWait, rate-limit
├── sessions/            # Pyrogram session dosyaları (gitignore)
├── log2alfa.db           # SQLite DB (gitignore)
├── requirements.txt
├── railway.json
├── Procfile
└── .env.example
```

---

## ⚠️ Önemli Uyarılar

- **Spam yapma:** Userbot'u spam için kullanırsan Telegram hesabın kısıtlanabilir. Günde 1-2 tag, saniyede 1 komut ideal.
- **Yeni hesap:** İlk 24 saat sadece `.log2alfa` ve `.ping` test et.
- **2FA açık tut:** Ayarlar -> Gizlilik ve Güvenlik -> İki Adımlı Doğrulama
- **Token'ları paylaşma:** `BOT_TOKEN` ve `API_HASH` gizli tut.

---

## 🔧 Sorun Giderme

| Hata | Çözüm |
|------|-------|
| `BOT_TOKEN eksik` | .env'e doğru token ekle, Railway Variables kontrol et |
| `API_ID eksik` | my.telegram.org'dan al |
| `PhoneNumberInvalid` | +90 ile dene, başında + olsun |
| `PhoneCodeInvalid` | Kodu boşluklu dene: `1 2 3 4 5` |
| `FloodWait` | Bot otomatik bekler, sen bekle |
| `.log2alfa` çalışmıyor | Başkası değil, **kendi hesabından** yazdığından emin ol, giriş yaptın mı? /start -> Durum kontrol |

---

## 👨‍💻 Geliştirici

**Log2 Alfa Projects** - Log2 Alfa Pro v2.0
Railway + Pyrogram 2.0 + TGCrypto

Komut eklemek için `handlers/` altına yeni dosya ekle ve `userbot_core.py`'de `register_handlers` yap.

---

**Hazır mısın?** Botuna `/start` de ve `🔑 Hesaba Giriş Yap` ile başla! 🚀
