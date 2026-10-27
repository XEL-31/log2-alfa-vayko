"""Log2 Alfa Canvas — görsel efekt motoru (Pillow, TAMAMEN OFFLINE)

Eski Asena pluginleri Telegraph'a fotoğraf yüklüyordu → "Profil fotoğrafı
Telegrapha yüklenemedi!" hatası. Artık efektler cihaz içinde Pillow ile
üretiliyor: internet, API, upload yok → hata yok.

Üretilenler:
  render_triggered_gif()  → animasyonlu "TRIGGERED" GIF
  render_lgbt()           → gökkuşağı bayraklı avatar PNG
  render_comment_card()   → Twitter / YouTube / yorum kartı PNG
  render_trap_card()      → Yu-Gi-Oh tarzı kart PNG

Ayrıca: avatar indirme (Pyrogram) + yedekli dosya upload (kart/phub gibi
API isteyen pluginler için, hepsi başarısız olursa offline render'a düşer).
"""
from __future__ import annotations

import io
import math
import os
import tempfile

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except Exception:  # Pillow yoksa modül yine import edilebilsin
    Image = None

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"),
    "Accept": "image/*,*/*;q=0.8",
}


def available() -> bool:
    return Image is not None


def font(size: int, bold: bool = True):
    if Image is None:
        return None
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def tmp_path(suffix: str) -> str:
    d = tempfile.mkdtemp(prefix="log2alfa_canvas_")
    return os.path.join(d, "out" + suffix)


# ───────────────────────── avatar ─────────────────────────

async def get_avatar(client, user_id, tmpdir: str = None) -> str | None:
    """Kullanıcının (veya sohbetin) profil fotoğrafını indirir. Yoksa None."""
    if not tmpdir:
        tmpdir = tempfile.mkdtemp(prefix="log2alfa_ava_")
    os.makedirs(tmpdir, exist_ok=True)
    target = os.path.join(tmpdir, "avatar.jpg")
    # 1) Pyrogram native: get_profile_photos → download_media
    try:
        photos = await client.get_profile_photos(user_id, limit=1)
        if photos:
            path = await client.download_media(photos[0], file_name=target)
            if path and os.path.exists(str(path)):
                return str(path)
    except Exception:
        pass
    # 2) sohbet fotoğrafı
    try:
        chat = await client.get_chat(user_id)
        photo = getattr(chat, "photo", None)
        if photo is not None:
            fid = getattr(photo, "big_file_id", None) or getattr(photo, "small_file_id", None)
            if fid:
                path = await client.download_media(fid, file_name=target)
                if path and os.path.exists(str(path)):
                    return str(path)
    except Exception:
        pass
    # 3) reply mesajındaki fotoğraf (varsa) — çağıran taraf halleder
    return None


async def resolve_username(client, user_id, fallback: str = "kullanici") -> str:
    """Kullanıcı adı (yoksa ilk ad) — Pyrogram native, hata fırlatmaz."""
    try:
        u = await client.get_users(user_id)
        return (getattr(u, "username", None) or getattr(u, "first_name", None) or fallback)
    except Exception:
        return fallback


async def target_media(client, reply, user_id=None, tmpdir: str = None) -> str | None:
    """Efekt için görsel bul: önce yanıtlanan medya, sonra profil fotoğrafı."""
    if not tmpdir:
        tmpdir = tempfile.mkdtemp(prefix="log2alfa_media_")
    os.makedirs(tmpdir, exist_ok=True)
    # 1) yanıtlanan mesajın kendi medyası (foto/sticker/video)
    for attr in ("photo", "sticker", "document", "video", "animation"):
        try:
            obj = getattr(reply, attr, None)
            if obj is None:
                continue
            path = await client.download_media(reply, file_name=os.path.join(tmpdir, "media_"))
            if path and os.path.exists(str(path)) and os.path.getsize(str(path)) > 512:
                return str(path)
        except Exception:
            pass
    # 2) kullanıcının profil fotoğrafı
    if user_id:
        try:
            p = await get_avatar(client, user_id, tmpdir)
            if p:
                return p
        except Exception:
            pass
    return None


def cleanup(*paths):
    """Üretilen geçici dosyaları/temp dizinlerini sessizce temizle."""
    import shutil
    for p in paths:
        try:
            if not p:
                continue
            p = str(p)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                os.remove(p)
                parent = os.path.dirname(p)
                if "log2alfa_" in parent:
                    shutil.rmtree(parent, ignore_errors=True)
        except Exception:
            pass


def _square(img, size: int):
    w, h = img.size
    side = min(w, h)
    img = img.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2))
    return img.resize((size, size), Image.LANCZOS)


def _load_image(path, fallback_color=(70, 70, 90)):
    try:
        img = Image.open(path)
        img.load()
        return img.convert("RGBA")
    except Exception:
        return Image.new("RGBA", (320, 320), fallback_color + (255,))


def _fit_text(draw, text, fnt, max_width):
    """Uzun metni satırlara böler."""
    words = str(text).split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        try:
            width = draw.textlength(test, font=fnt)
        except Exception:
            width = len(test) * 8
        if width <= max_width or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:6]


def _circle(img, size: int):
    img = _square(img, size).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    img.putalpha(mask)
    return img


# ───────────────────────── efektler ─────────────────────────

def render_triggered_gif(avatar_path: str, out_path: str = None, size: int = 300) -> str | None:
    """Sallanan avatar + kırmızı TRIGGERED bandı (animasyonlu GIF)."""
    if Image is None:
        return None
    out_path = out_path or tmp_path(".gif")
    base = _square(_load_image(avatar_path), size)
    W = size + 30
    H = size + 80
    frames = []
    for i in range(18):
        zoom = 1.0 + 0.06 * abs(math.sin(i * 1.1))
        dx = int(9 * math.sin(i * 1.7))
        dy = int(7 * math.cos(i * 1.3))
        img = base.resize((int(size * zoom), int(size * zoom)), Image.LANCZOS)
        fr = Image.new("RGB", (W, H), (14, 14, 16))
        fr.paste(img, ((W - img.width) // 2 + dx, 12 + dy), img)
        d = ImageDraw.Draw(fr)
        # efektif kırmızı band
        d.rectangle([0, H - 54, W, H], fill=(206, 17, 38))
        d.rectangle([0, H - 58, W, H - 54], fill=(255, 60, 60))
        txt = "TRIGGERED"
        f = font(34, True)
        try:
            tw = d.textlength(txt, font=f)
        except Exception:
            tw = 170
        d.text(((W - tw) / 2, H - 47), txt, font=f, fill=(255, 255, 255))
        frames.append(fr)
    frames[0].save(out_path, save_all=True, append_images=frames[1:], duration=55, loop=0, optimize=True)
    return out_path


def render_lgbt(avatar_path: str, out_path: str = None, size: int = 420) -> str | None:
    """Gökkuşağı bayrağı bindirilmiş avatar."""
    if Image is None:
        return None
    out_path = out_path or tmp_path(".png")
    base = _square(_load_image(avatar_path), size)
    colors = [(228, 3, 3), (255, 140, 0), (255, 237, 0), (0, 128, 38), (0, 77, 255), (117, 7, 135)]
    band = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    step = size / len(colors)
    for i, c in enumerate(colors):
        bd.rectangle([0, int(i * step), size, int((i + 1) * step) + 1], fill=c + (118,))
    merged = Image.alpha_composite(base, band)
    merged = _circle(merged, size)
    W = size + 40
    card = Image.new("RGB", (W, W + 46), (16, 16, 20))
    card.paste(merged, (20, 20), merged)
    d = ImageDraw.Draw(card)
    ring = ImageDraw.Draw(card)
    ring.ellipse([18, 18, 18 + size + 1, 18 + size + 1], outline=(255, 255, 255), width=4)
    f = font(30, True)
    label = "L G B T +"
    try:
        tw = d.textlength(label, font=f)
    except Exception:
        tw = 150
    card_w = W
    d.text(((card_w - tw) / 2, W + 6), label, font=f, fill=(255, 255, 255))
    card.save(out_path)
    return out_path


def render_comment_card(avatar_path: str, username: str, text: str, out_path: str = None,
                        platform: str = "youtube") -> str | None:
    """Offline yorum kartı (YouTube / Twitter / PH)."""
    if Image is None:
        return None
    out_path = out_path or tmp_path(".png")
    themes = {
        "youtube": {"bg": (15, 15, 15), "card": (24, 24, 24), "accent": (255, 0, 0), "label": "YouTube"},
        "twitter": {"bg": (21, 32, 43), "card": (25, 39, 52), "accent": (29, 161, 242), "label": "Twitter"},
        "ph": {"bg": (12, 12, 12), "card": (22, 22, 22), "accent": (255, 153, 0), "label": "PH"},
    }
    th = themes.get(platform, themes["youtube"])
    W, H = 1000, 600
    card = Image.new("RGB", (W, H), th["bg"])
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([24, 24, W - 24, H - 24], radius=26, fill=th["card"])
    d.rounded_rectangle([24, 24, W - 24, 92], radius=26, fill=th["accent"])
    d.rectangle([24, 70, W - 24, 92], fill=th["accent"])
    fl = font(30, True)
    d.text((50, 42), th["label"], font=fl, fill=(255, 255, 255))

    av = _circle(_load_image(avatar_path), 96)
    card.paste(av, (56, 126), av)

    fuser = font(34, True)
    d.text((176, 132), "@" + str(username)[:28], font=fuser, fill=(255, 255, 255))
    fsmall = font(24, True)
    d.text((176, 178), "az önce • Log2Alfa", font=fsmall, fill=(150, 150, 155))

    fbody = font(32, False)
    y = 246
    for line in _fit_text(d, text, fbody, W - 200):
        d.text((56, y), line, font=fbody, fill=(232, 232, 236))
        y += 46
        if y > H - 130:
            break

    # alt aksiyon satırı
    y = H - 96
    d.line([56, y - 16, W - 56, y - 16], fill=(60, 60, 64), width=2)
    fact = font(26, True)
    d.text((56, y), "Begen     Yanitla     Paylas", font=fact, fill=(150, 150, 155))
    d.text((W - 300, y), "verified  @Log2Alfa", font=font(26, False), fill=(th["accent"]))
    card.save(out_path)
    return out_path


def render_trap_card(avatar_path: str, author: str, name: str, out_path: str = None) -> str | None:
    """Yu-Gi-Oh tarzı efekt kartı (offline)."""
    if Image is None:
        return None
    out_path = out_path or tmp_path(".png")
    W, H = 620, 860
    card = Image.new("RGB", (W, H), (24, 16, 40))
    d = ImageDraw.Draw(card)
    # çerçeve
    d.rounded_rectangle([12, 12, W - 12, H - 12], radius=22, fill=(46, 26, 78))
    d.rounded_rectangle([34, 34, W - 34, H - 34], radius=16, fill=(250, 246, 232))
    # başlık bandı
    d.rounded_rectangle([52, 52, W - 52, 122], radius=12, fill=(120, 60, 190))
    ft = font(34, True)
    d.text((72, 68), "TRAP CARD", font=ft, fill=(255, 255, 255))
    d.text((W - 220, 68), author[:14], font=font(28, True), fill=(230, 220, 255))
    # görsel alanı
    box = (72, 148, W - 72, H - 250)
    art = _load_image(avatar_path).convert("RGB")
    aw, ah = box[2] - box[0], box[3] - box[1]
    img = _square(art, min(aw, ah)).resize((aw, aw), Image.LANCZOS)
    card.paste(img, (box[0], box[1] + (ah - aw) // 2))
    d.rectangle(box, outline=(40, 30, 20), width=4)
    # isim
    fn = font(40, True)
    nm = str(name)[:22]
    try:
        nw = d.textlength(nm, font=fn)
    except Exception:
        nw = 200
    d.text(((W - nw) / 2, H - 232), nm, font=fn, fill=(40, 30, 20))
    d.text((72, H - 170), "Efekt: /kart  •  @Log2Alfa", font=font(24, False), fill=(90, 80, 70))
    card.save(out_path)
    return out_path


# ───────────────────────── internet (sadece gerekirse) ─────────────────────────

def fetch_url(url: str, timeout: int = 25, binary: bool = True):
    """UA'lı indirme. Hata olursa None (exception YOK)."""
    try:
        import requests
        r = requests.get(url, headers=UA, timeout=timeout)
        if r.status_code != 200:
            return None
        ct = r.headers.get("content-type", "")
        if binary and "image" not in ct and "gif" not in ct and "octet-stream" not in ct:
            return None
        return r.content if binary else r.text
    except Exception:
        return None


def upload_public(path: str, timeout: int = 40) -> str | None:
    """Dosyayı public URL'e yükler. Sırayla dener, hiçbiri olmazsa None."""
    try:
        import requests
    except Exception:
        return None
    if not path or not os.path.exists(path):
        return None
    providers = []

    def uguu():
        with open(path, "rb") as f:
            r = requests.post("https://uguu.se/upload.php", headers=UA,
                              files={"files[]": (os.path.basename(path), f)}, timeout=timeout)
        j = r.json()
        return j["files"][0]["url"]

    def catbox():
        with open(path, "rb") as f:
            r = requests.post("https://catbox.moe/user/api.php", headers=UA,
                              data={"reqtype": "fileupload"},
                              files={"fileToUpload": (os.path.basename(path), f)}, timeout=timeout)
        t = (r.text or "").strip()
        return t if t.startswith("http") else None

    def tmpfiles():
        with open(path, "rb") as f:
            r = requests.post("https://tmpfiles.org/api/v1/upload", headers=UA,
                              files={"file": (os.path.basename(path), f)}, timeout=timeout)
        j = r.json()
        url = j["data"]["url"]
        return url.replace("tmpfiles.org/", "tmpfiles.org/dl/")

    def telegraph():
        from telegraph import upload_file
        res = upload_file(path)
        return "https://telegra.ph" + res[0]

    providers = [uguu, catbox, tmpfiles, telegraph]
    for p in providers:
        try:
            url = p()
            if url and str(url).startswith("http"):
                return str(url)
        except Exception as e:
            print(f"upload sağlayıcı hata ({p.__name__}): {e}", flush=True)
            continue
    return None


# ───────────────────────── gösterişli foto efektleri (offline) ─────────────────────────

def _fx_base(path, size: int = 720):
    img = _load_image(path).convert("RGB")
    w, h = img.size
    if max(w, h) < size:
        ratio = size / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    elif max(w, h) > 1500:
        ratio = 1500 / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    return img


def _fx_neon(img, out):
    from PIL import ImageChops, ImageOps
    g = ImageOps.grayscale(img)
    edges = ImageOps.autocontrast(g.filter(ImageFilter.FIND_EDGES))
    thick = edges.filter(ImageFilter.MaxFilter(3))
    cyan = ImageOps.colorize(thick, black=(0, 0, 25), white=(0, 255, 230))
    glow = thick.filter(ImageFilter.GaussianBlur(6))
    pink = ImageOps.colorize(glow, black=(0, 0, 0), white=(255, 0, 190))
    out_img = ImageChops.add(cyan, pink)
    ImageChops.add(out_img, ImageOps.colorize(edges.filter(ImageFilter.GaussianBlur(14)),
                                              black=(0, 0, 0), white=(60, 90, 255))).save(out)
    return out


def _fx_glitch(img, out):
    from PIL import ImageChops
    import random as _r
    w, h = img.size
    r, g, b = img.split()
    r = ImageChops.offset(r, 9, 0)
    b = ImageChops.offset(b, -9, 0)
    img2 = Image.merge("RGB", (r, g, b))
    d = ImageDraw.Draw(img2)
    for y in range(0, h, 4):
        d.line([0, y, w, y], fill=(0, 0, 0), width=1)
    for _ in range(14):
        y = _r.randint(0, h - 20)
        hh = _r.randint(3, 18)
        band = img2.crop((0, y, w, y + hh)).copy()
        img2.paste(band, (_r.randint(-25, 25), y))
    img2.save(out)
    return out


def _fx_pixel(img, out, block: int = 18):
    w, h = img.size
    small = img.resize((max(8, w // block), max(8, h // block)), Image.NEAREST)
    small.resize((w, h), Image.NEAREST).save(out)
    return out


def _fx_cizim(img, out):
    from PIL import ImageChops, ImageOps
    g = ImageOps.grayscale(img)
    inv = ImageOps.invert(g).filter(ImageFilter.GaussianBlur(9))
    try:
        sketch = ImageChops.dodge(inv, g)
    except Exception:
        sketch = ImageOps.autocontrast(ImageChops.subtract(g, inv))
    sketch.convert("RGB").save(out)
    return out


def _fx_negatif(img, out):
    from PIL import ImageOps
    ImageOps.invert(img).save(out)
    return out


def _fx_ates(img, out):
    from PIL import ImageOps
    g = ImageOps.autocontrast(ImageOps.grayscale(img))
    heat = ImageOps.colorize(g, black=(8, 0, 0), white=(255, 255, 220),
                             mid=(255, 70, 0), blackpoint=20, whitepoint=235)
    heat.save(out)
    return out


def _fx_altin(img, out):
    from PIL import ImageOps
    g = ImageOps.autocontrast(ImageOps.grayscale(img))
    gold = ImageOps.colorize(g, black=(35, 20, 0), white=(255, 236, 170), mid=(212, 160, 40))
    gold.save(out)
    return out


def _fx_vapor(img, out):
    w, h = img.size
    g = img.convert("L")
    base = Image.merge("RGB", (g.point(lambda v: min(255, int(v * 1.15) + 30)),
                               g.point(lambda v: int(v * 0.75)),
                               g.point(lambda v: min(255, int(v * 1.1) + 60))))
    d = ImageDraw.Draw(base, "RGBA")
    for y in range(0, h, 3):
        d.line([0, y, w, y], fill=(255, 0, 160, 26), width=1)
    d.ellipse([w * 0.55, -h * 0.15, w * 1.15, h * 0.35], fill=(255, 120, 40, 90))
    d.line([0, h * 0.72, w, h * 0.72], fill=(0, 255, 240, 120), width=3)
    base.save(out)
    return out


def _fx_yumusak(img, out):
    from PIL import ImageChops
    soft = img.filter(ImageFilter.GaussianBlur(6))
    bloom = ImageChops.screen(img, soft).filter(ImageFilter.GaussianBlur(1.2))
    bloom.save(out)
    return out


def _fx_sallan_gif(path, out=None, size: int = 360, frames: int = 16):
    """Renkli sallanan GIF (triggered'ın şen versiyonu)."""
    out = out or tmp_path(".gif")
    base = _square(_load_image(path), size)
    W, H = size + 24, size + 24
    fr_list = []
    for i in range(frames):
        zoom = 1.0 + 0.05 * abs(math.sin(i * 0.9))
        dx = int(7 * math.sin(i * 1.8))
        dy = int(5 * math.cos(i * 1.4))
        img = base.resize((int(size * zoom), int(size * zoom)), Image.LANCZOS)
        fr = Image.new("RGB", (W, H), (18, 8, 30))
        fr.paste(img, ((W - img.width) // 2 + dx, (H - img.height) // 2 + dy), img)
        ImageDraw.Draw(fr).rectangle([0, 0, W - 1, H - 1],
                                     outline=(255, 0, 150) if i % 2 else (0, 230, 255), width=6)
        fr_list.append(fr)
    fr_list[0].save(out, save_all=True, append_images=fr_list[1:], duration=70, loop=0, optimize=True)
    return out


def _fx_aura_gif(path, out=None, size: int = 360, frames: int = 20):
    """Nefes alan neon aura efekti (animasyonlu)."""
    out = out or tmp_path(".gif")
    base = _square(_load_image(path), size)
    fr_list = []
    W = size + 60
    for i in range(frames):
        t = i / frames
        glow_size = int(14 + 12 * (0.5 + 0.5 * math.sin(t * 2 * math.pi)))
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        ring = Image.new("RGB", (W, W), (10, 8, 18))
        halo = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        hd = ImageDraw.Draw(halo)
        hue = int(120 + 120 * math.sin(t * 2 * math.pi))
        hd.ellipse([(W - size) // 2 - glow_size, (W - size) // 2 - glow_size,
                    (W + size) // 2 + glow_size, (W + size) // 2 + glow_size],
                   fill=(255, 0, hue, 150))
        halo = halo.filter(ImageFilter.GaussianBlur(glow_size * 1.6))
        ring = Image.alpha_composite(ring.convert("RGBA"), halo)
        av = base.copy()
        av.putalpha(mask)
        ring.paste(av, ((W - size) // 2, (W - size) // 2), av)
        fr_list.append(ring.convert("RGB"))
    fr_list[0].save(out, save_all=True, append_images=fr_list[1:], duration=80, loop=0, optimize=True)
    return out


def _fx_zoom_gif(path, out=None, size: int = 400, frames: int = 16):
    out = out or tmp_path(".gif")
    base = _square(_load_image(path), size)
    fr_list = []
    for i in range(frames):
        t = i / frames
        z = 1.0 + 0.22 * (0.5 + 0.5 * math.sin(t * 2 * math.pi))
        img = base.resize((int(size * z), int(size * z)), Image.LANCZOS)
        off = (img.width - size) // 2
        crop = img.crop((off, off, off + size, off + size))
        fr = Image.new("RGB", (size, size), (0, 0, 0))
        fr.paste(crop, (0, 0), crop)
        d = ImageDraw.Draw(fr)
        d.rectangle([0, 0, size - 1, size - 1], outline=(255, 255, 255), width=3)
        fr_list.append(fr)
    fr_list[0].save(out, save_all=True, append_images=fr_list[1:], duration=60, loop=0, optimize=True)
    return out


def _mesh_warp(img, phase: float, amp: int = 13, grid: int = 8):
    """Izgara tabanlı dalga bükülmesi (magik efekti)."""
    w, h = img.size
    boxes = []
    for i in range(grid):
        for j in range(grid):
            x0, y0 = i * w / grid, j * h / grid
            x1, y1 = (i + 1) * w / grid, (j + 1) * h / grid
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            dx = amp * math.sin(phase + (cy / h) * math.pi * 2)
            dy = amp * math.cos(phase + (cx / w) * math.pi * 2)
            boxes.append(((x0, y0, x1, y1), (x0 + dx, y0 + dy, x1 + dx, y1 + dy)))
    try:
        return img.transform((w, h), Image.MESH, boxes)
    except Exception:
        return img


def _fx_magik_gif(path, out=None, size: int = 400, frames: int = 14):
    """Magik: büyüleyici dalga bükülmesi (animasyonlu GIF, offline)."""
    out = out or tmp_path(".gif")
    base = _square(_load_image(path).convert("RGB"), size)
    fr_list = []
    for i in range(frames):
        phase = (i / frames) * math.pi * 2
        amp = int(size * 0.035 * (1 + abs(math.sin(phase))))
        img = _mesh_warp(base, phase, amp=amp)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, size - 1, size - 1], outline=(150, 80, 255), width=4)
        fr_list.append(img)
    fr_list[0].save(out, save_all=True, append_images=fr_list[1:], duration=90, loop=0, optimize=True)
    return out


FX_LIST = [
    ("neon", "Neon ışıklı kenar efekti", "img"),
    ("magik", "Sihirli dalga bükülmesi GIF", "gif"),
    ("glitch", "Bozulma / RGB kayması", "img"),
    ("pixel", "Piksel mozaik", "img"),
    ("cizim", "Kurşun kalem çizimi", "img"),
    ("negatif", "Renk negatifi", "img"),
    ("ates", "Alev renkleri", "img"),
    ("altin", "Altın ton", "img"),
    ("vapor", "Vaporwave / retro", "img"),
    ("yumusak", "Rüya gibi yumuşak", "img"),
    ("sallan", "Renkli sallanan GIF", "gif"),
    ("aura", "Nefes alan neon aura GIF", "gif"),
    ("zoom", "Zoom nabız GIF", "gif"),
]

_EFFECTS = {
    "neon": _fx_neon, "glitch": _fx_glitch, "pixel": _fx_pixel, "cizim": _fx_cizim,
    "negatif": _fx_negatif, "ates": _fx_ates, "altin": _fx_altin, "vapor": _fx_vapor,
    "yumusak": _fx_yumusak,
}
_GIF_EFFECTS = {"sallan": _fx_sallan_gif, "aura": _fx_aura_gif, "zoom": _fx_zoom_gif,
                "magik": _fx_magik_gif}


def apply_effect(name: str, path: str) -> str | None:
    """Efekti uygular, çıktı dosya yolunu döner. Hata olursa None."""
    if Image is None or not path:
        return None
    name = (name or "").lower().strip()
    try:
        if name in _GIF_EFFECTS:
            return _GIF_EFFECTS[name](path)
        fn = _EFFECTS.get(name)
        if not fn:
            return None
        img = _fx_base(path)
        out = tmp_path(".png")
        return fn(img, out)
    except Exception as e:
        print(f"efekt hata ({name}): {e}", flush=True)
        return None


def is_gif_effect(name: str) -> bool:
    return (name or "").lower().strip() in _GIF_EFFECTS

# ───────────────────────── Log2 Alfa tanıtım banner'ı (offline, efektli) ─────────────────────────

def render_log2alfa_banner(out_path: str = None, slogan: str = None, brand: str = "@Log2Alfa",
                          user_name: str = None) -> str | None:
    """Neon ışıklı, gradyanlı gösterişli Log2 Alfa banner'ı (PNG)."""
    if Image is None:
        return None
    import random as _r
    out_path = out_path or tmp_path(".png")
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), (6, 4, 16))
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line([0, y, W, y], fill=(int(8 + 30 * k), int(4 + 10 * k), int(26 + 70 * k)))
    _r.seed(7)
    for _ in range(260):
        x, y = _r.randint(0, W), _r.randint(0, H)
        r = _r.choice([1, 1, 1, 2, 2, 3])
        c = _r.choice([(255, 255, 255), (150, 220, 255), (255, 160, 240)])
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-180, H - 340, 460, H + 180], outline=(0, 230, 255, 200), width=7)
    gd.ellipse([W - 420, -200, W + 220, 320], outline=(255, 0, 170, 200), width=7)
    gd.ellipse([W // 2 - 300, H // 2 - 190, W // 2 + 300, H // 2 + 230],
               outline=(140, 60, 255, 130), width=4)
    glow = glow.filter(ImageFilter.GaussianBlur(9))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img)

    f_title = font(132, True)
    title = "LOG2 ALFA"
    try:
        tw = d.textlength(title, font=f_title)
    except Exception:
        tw = 620
    tx, ty = (W - tw) / 2, H / 2 - 168
    for off, col in ((10, (255, 0, 170)), (-10, (0, 220, 255))):
        d.text((tx + off, ty), title, font=f_title, fill=col)
    d.text((tx, ty), title, font=f_title, fill=(255, 255, 255))

    f_sub = font(46, True)
    sub = "ᴜ s ᴇ ʀ ʙ ᴏ ᴛ   •   ᴋ ı ʟ ı ᴄ  ʙ ᴏ ᴛ s"
    try:
        sw = d.textlength(sub, font=f_sub)
    except Exception:
        sw = 560
    d.text(((W - sw) / 2, H / 2 - 20), sub, font=f_sub, fill=(180, 240, 255))

    f_slo = font(34, False)
    text = slogan or "ɴᴇᴏɴ ᴇғᴇᴋᴛʟᴇʀ • ᴀɴɪᴍᴀsʏᴏɴʟᴀʀ • sıᴄᴀᴋ ᴛᴀᴋıᴍ ʀᴜʜᴜ"
    try:
        lw = d.textlength(text, font=f_slo)
    except Exception:
        lw = 700
    d.text(((W - lw) / 2, H / 2 + 70), text, font=f_slo, fill=(225, 225, 240))

    d.rectangle([0, H - 74, W, H], fill=(255, 0, 120))
    d.rectangle([0, H - 78, W, H - 74], fill=(0, 230, 255))
    f_br = font(36, True)
    label = brand if not user_name else f"{brand}   •   {user_name}"
    try:
        bw = d.textlength(label, font=f_br)
    except Exception:
        bw = 380
    d.text(((W - bw) / 2, H - 62), label, font=f_br, fill=(255, 255, 255))
    img.save(out_path, quality=95)
    return out_path

def render_banner_intro_gif(banner_path: str, out_path: str = None, frames: int = 18) -> str | None:
    """Banner'a kayan neon ışık + nabız efekti ekleyip tanıtım GIF'i üretir."""
    if Image is None or not banner_path or not os.path.exists(banner_path):
        return None
    out_path = out_path or tmp_path(".gif")
    base = Image.open(banner_path).convert("RGB")
    W, H = base.size
    fr_list = []
    band_w = 260
    for i in range(frames):
        t = i / frames
        fr = base.copy()
        # kayan neon ışık bandı
        band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bd = ImageDraw.Draw(band)
        x = int(-band_w + (W + band_w * 2) * t)
        bd.polygon([(x, 0), (x + band_w, 0), (x + band_w - 180, H), (x - 180, H)],
                   fill=(120, 235, 255, 58))
        bd.polygon([(x + 40, 0), (x + band_w - 40, 0), (x + band_w - 220, H), (x - 140, H)],
                   fill=(255, 120, 220, 42))
        band = band.filter(ImageFilter.GaussianBlur(26))
        fr = Image.alpha_composite(fr.convert("RGBA"), band).convert("RGB")
        # nabız (hafif zoom)
        z = 1.0 + 0.012 * math.sin(t * 2 * math.pi)
        if z > 1.0:
            fz = fr.resize((int(W * z), int(H * z)), Image.LANCZOS)
            ox, oy = (fz.width - W) // 2, (fz.height - H) // 2
            fr = fz.crop((ox, oy, ox + W, oy + H))
        # açılıp kapanan alt şerit parlaklığı
        d = ImageDraw.Draw(fr)
        glow_a = int(120 + 120 * abs(math.sin(t * 2 * math.pi)))
        d.rectangle([0, H - 5, W, H - 1], fill=(glow_a, 240, 255))
        fr_list.append(fr)
    fr_list[0].save(out_path, save_all=True, append_images=fr_list[1:],
                    duration=80, loop=0, optimize=True)
    return out_path
