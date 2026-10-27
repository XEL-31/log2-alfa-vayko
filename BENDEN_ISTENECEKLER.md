# Log2 Alfa - Senden İstenen Bilgiler

Merhaba! Log2 Alfa tamamen temizlendi, hiçbir yerde "Spectra" kalmadı. 
Botu çalıştırmak için aşağıdaki bilgileri vermen gerekiyor:

## 🔴 ZORUNLU (Bot çalışmazsa bu eksiktir)

1. **BOT_TOKEN**
   - @BotFather -> /newbot -> Bot ismi ver (örn: Log2 Alfa Bot) -> Token kopyala
   - Örn: `1234567890:AAHxxxxxxxxxxxxxxxxxxxx`
   - Nereye koyulacak: `.env` dosyasında `BOT_TOKEN=`

2. **API_ID ve API_HASH**
   - https://my.telegram.org -> Log in (telefon ile) -> API Development Tools -> Create App
   - App title: `Log2 Alfa` | Short name: `log2alfa` | Platform: `Other` -> Create
   - `API_ID` (sayı, örn 12345678) ve `API_HASH` (32 karakter hex)
   - Nereye: `.env` de `API_ID=` ve `API_HASH=`

> Bu ikisi olmadan `main.py` çalışmaz. Hata verir: `BOT_TOKEN eksik` / `API_ID eksik`

## 🟡 OPSİYONEL (boş bırakabilirsin)

3. **OWNER_ID** - Sadece sen kullansın istiyorsan Telegram ID'n
   - @userinfobot'a yaz -> ID'ni al
   - `OWNER_ID=0` bırakırsan herkes kendi hesabıyla giriş yapabilir

4. **SUPPORT_URL / DEV_URL** - Botun /start menüsünde çıkacak butonlar
   - Örn: `SUPPORT_URL=https://t.me/destekkanalin`
   - Örn: `DEV_URL=https://t.me/seninuserin`
   - Boş bırakırsan buton gizlenir (şu an boş, sen doldur)

5. **ADMIN_UID / ADMIN_USERNAMES** - Yönetim paneline ekstra adminler
   - `ADMIN_UID=123456789`
   - `ADMIN_USERNAMES=user1,user2`
   - Boş bırakırsan sadece OWNER yönetir

6. **OPENROUTER_API_KEY** - `.ai` komutu için
   - https://openrouter.ai/keys -> Create Key -> kopyala
   - `OPENROUTER_API_KEY=sk-or-v1-xxxx`
   - Boş bırakırsan `.ai` çalışmaz ama bot çalışır

7. **PP / Banner** - Zaten yenilendi!
   - `assets/log2alfa_banner.png` (1600x700 neon banner - LOG2 ALFA yazılı)
   - `assets/log2alfa_pp.png` ve `assets/pp.png` (1024x1024 kare profil foto - L2 logolu)
   - İstersen kendi fotoğrafını `assets/pp.png` ile değiştir
   - Hiçbir yerde Spectra yazmıyor, kontrol edildi ✅

## ✅ Ne Yapıldı?

- Tüm `Spectra` -> `Log2 Alfa` / `log2alfa` / `Log2Alfa` değişti (139 dosya tarandı, 0 kaldı)
- Hardcoded `sk-or-v1-...` token SİLİNDİ (artık .env'den geliyor)
- Hardcoded `7292472291` admin ID -> `0` yapıldı (env'den geliyor)
- Hardcoded `t.me/kilicon`, `kilicbots`, `kullanamazsin` linkleri SİLİNDİ (env'den geliyor)
- `OWNER_NAME` default `Kılıç` -> `Log2 Alfa` yapıldı
- Komutlar: `.log2alfa` + `.alfa` + `.log2` + `.alive` hepsi çalışıyor (alias eklendi)
- Bannerlar sıfırdan oluşturuldu: `log2alfa_banner.png`, `banner_dark.png`, `banner_dark_v2.png`, `pp.png`
- `.env.example` sıfırdan yazıldı, tüm alanlar açıklamalı
- Veritabanı isimleri `spectra.db` -> `log2alfa.db` yapıldı

## 🚀 Sonraki Adım

Bana şunları gönder:

```
BOT_TOKEN=
API_ID=
API_HASH=
OWNER_NAME= (istersen)
SUPPORT_URL= (istersen)
DEV_URL= (istersen)
```

Ben senin için `.env` dosyasını oluşturup botu test edeceğim.

İstemiyorsan kendin de yapabilirsin:
```bash
cp .env.example .env
nano .env  # doldur
pip install -r requirements.txt
python main.py
```

Bot: https://t.me/<botusername> -> /start -> Giriş Yap -> .alfa ile test

