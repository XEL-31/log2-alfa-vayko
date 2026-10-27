# Log2 Alfa - VS Code Kurulum (Windows/Mac/Linux)

## HIZLI ÇÖZÜM (Senin hatan için - tgcrypto Windows derleme hatası)

### Sorun: `Microsoft Visual C++ 14.0 is required` ve `No module named 'aiosqlite'`
Sebep: venv'i aktive etmeden pip kurdun, tgcrypto derlenemediği için tüm kurulum yarım kaldı.

### Doğru adımlar (PowerShell'i KAPATıp YENİDEN AÇ):

**1) VS Code'da terminali aç: CTRL + `**

```powershell
# 1 - venv oluştur (zaten varsa sil: rmdir venv -Recurse -Force)
python -m venv venv

# 2 - AKTİVE ET (BU ADIMI ATLADIN - ÖNEMLİ!)
.\venv\Scripts\Activate.ps1
# Eğer hata verirse: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 3 - Pip güncelle
python -m pip install --upgrade pip

# 4 - Kur (Windows için tgcrypto'suz)
pip install -r requirements_windows.txt
# veya tek tek:
pip install PyroTGFork aiosqlite python-dotenv psutil yt-dlp emoji==1.7.0 requests beautifulsoup4 pillow lxml pytz sqlalchemy==1.4.46 aiohttp qrcode pybase64 GitPython speedtest-cli cowpy pylast pydub numpy lyricsgenius==3.0.1

# 5 - Çalıştır (venv aktifken)
python main.py
```

**Neden tgcrypto yok?** tgcrypto sadece hızlandırma için, olmadan da bot %100 çalışır. İstersen sonra kurarsın:
```powershell
# İsteğe bağlı (Visual Studio Build Tools gerekir):
pip install tgcrypto
```

---

## Normal Linux/Mac

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## .env zaten hazır
`log2_alfa/.env` içinde:
- BOT_TOKEN=884677...
- API_ID=33889261
- API_HASH=05476b...
- OWNER_ID=8722368605 (vayko)

Boşsa: `copy .env.example .env` (Windows) / `cp .env.example .env`

## Test
Bot: https://t.me/Log2userbot -> /start -> Giriş Yap -> .alfa
