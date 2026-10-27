"""
Log2Alfa — Profesyonel Yönetim Botu
Herkese açık, düzenli, hatasız
"""
import os, re, asyncio, time, json
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import SessionPasswordNeeded, MessageNotModified, FloodWait
import config, database
from userbot_core import initiate_login, complete_login, cancel_login, start_userbot_for_owner, stop_userbot_for_owner, active_userbots, pause_userbot_for_owner
from utils.helpers import get_uptime
from utils.fonts import smalls

login_state = {}

# ── Duyuru (broadcast) durumu ve grup koruması ──
duyuru_draft = {}        # admin_uid -> hazırlanmış içerik (hedef seçilmeden yazılan metin)
duyuru_intro_ts = {}     # admin_uid -> son 📣 Duyuru ekranı açılış zamanı
duyuru_state = {}        # admin_uid -> {"target": "saved"/"dm", "step": "...", "started_at": ts, "content": {...}}
group_notice_last = {}   # chat_id -> son uyarı zamanı (spam olmasın)
_bot_me_cache = None

GROUP_NOTICE_TEXT = """◼ LOG2 ALFA

Sadece özel mesajlarda çalışıyorum.

Gruplarda komut dinlemiyorum. Userbot kurmak, komutları ve paneli kullanmak için bana özelden yaz.

Aşağıdaki butonlardan DM'e gelebilir, destek alabilir veya sorununu geliştiriciye iletebilirsin."""

BROADCAST_TEXT = """📣 Duyuru Sistemi

Kayıtlı kullanıcı: {users}
Canlı userbot: {live}
{last}

Hedefi seç, sonra duyuru metnini gönder:

📥 Kayıtlı Mesajlar → userbot kurulu hesapların KENDİ kayıtlı mesajlarına, kendi oturumları ile gönderilir.
✉️ DM → kontrol botu tüm kayıtlı kullanıcılara özelden gönderir.

Duyuru bitince rapor tarafına iletilir."""

ADMIN_UID = int(os.getenv("ADMIN_UID", "8722368605") or 8722368605)
ADMIN_USERNAMES = set(u.strip().lower() for u in os.getenv("ADMIN_USERNAMES", "").split(",") if u.strip())
def is_admin_user(uid, username=None):
    if uid == ADMIN_UID:
        return True
    return (username or "").lower().lstrip("@") in ADMIN_USERNAMES

S = "vayko"  # Log2 Alfa - sahibi vayko
DEV_URL = os.getenv("DEV_URL", "")  # örn https://t.me/gelistiriciniz
SUPPORT_URL = os.getenv("SUPPORT_URL", "")  # örn https://t.me/destekkanaliniz

# ====== PROFESYONEL METİNLER ======
START_TEXT = """🔷 **LOG2 ALFA | vayko edition**

Merhaba {name} 👋
Telegram hesabını güçlendirmeye hazır mısın?

⚡️ **Nedir?**
Hesabın adına çalışan kişisel userbot — `.alfa` yaz, saniyesinde cevap versin.

🛡️ Ban korumalı • ⚡️ Hızlı • 🔒 Güvenli

👇 Başlamak için bir butona dokun
"""

HELP_TEXT = """◼️ **LOG2 ALFA — Komut Listesi**

**▶️ Başlangıç**
• /start → Paneli aç
• .alfa / .log2alfa → Bot durumu
• .ping → Hız testi
• .help → Bu menü

**💾 Medya**
• .save (yanıtla) → Medyayı kaydet
• .save <link> → Linkteki medyayı al
• .dlmedia (yanıtla) → Hızlı indir

**🛡 Yönetim:**
• .ban [reply/@u] [sebep] — banla
• .unban [reply/@u] — ban kaldır
• .kick [reply/@u] [sebep] — at
• .mute [reply/@u] [dk] — sustur
• .unmute [reply/@u] — susturmayı kaldır
• .promote [reply/@u] — yönetici yap
• .demote [reply/@u] — yöneticiden al
• .pin [loud] (reply) — sabitle (loud=bildirimli)
• .unpin — sabitlemeyi kaldır
• .admins — yönetici listesi
• .zombies [clean] — silinmiş hesap tara, clean=at
• .warn [reply/@u] [sebep] — uyar (3 uyarı → otomatik ban)
• .unwarn [reply/@u] — son uyarıyı sil
• .warns [reply/@u] — uyarı geçmişi
• .gban / .ungban [reply/@u] [sebep] — global ban
• .gmute / .ungmute [reply/@u] [sebep] — global susturma

**📝 Notlar:**
• .save <ad> <metin> — not kaydet
• .save <ad> (reply) — mesajı not kaydet
• .get <ad> — notu getir
• .delnote <ad> — notu sil
• .notes — tüm notları listele

**🔧 Araçlar:**
• .id / .info / .chatinfo — bilgi
• .hava <şehir> — hava durumu
• .çevir — çeviri
• .purge (reply) — o aralıktaki mesajları temizle (max 50, DM korumalı)
• .del (reply) — tek mesaj sil
• .purgeme <sayı> — kendi mesajlarını sil

**🔌 Pluginler (133):**
• .phelp — tüm pluginler ve komutları listeler
• .phelp <sayı> — sayfalı liste (örn: .phelp 2)
"""

HELP_LOGIN_TEXT = """📖 **Log2 Alfa — Giriş Yardımı**

Henüz userbotun kurulu değil — hemen başlayalım!

**Nasıl giriş yapacaksın:**
1. /start → 🚀 Giriş Yap butonuna dokun
2. Telefon numaranı gönder: `+90 5XXXXXXXXX`
3. Telegram'dan gelen 5 haneli kodu `1 2 3 4 5` şeklinde gönder
4. 2FA (bulut şifre) varsa onu gönder
5. Başarılı olunca → Kontrol Paneli açılır, vs.

**Test et:**
• .log2alfa — userbot durumun
• .ping — hız testi
• .help — tüm komutlar

**İpucu:**
Kod gelmezse “Yeni Kod İste” ile tekrar iste (3 hak).
Zaman aşımı olursa /start ile yeniden başlat.

vs. dahası dahası — hesabın tek takla hazır olacak!
"""


# ====== YARDIM BÖLÜMLERİ (banner ile uyumlu, her biri <900 char) ======
HELP_MAIN = """📖 **Log2 Alfa — Yardım Menüsü**

Ne lazımsa buradan seç — aradığın komut hemen gelsin.
"""

HELP_MEDIA = """💾 **Medya — Kısıtlı dahil**

• .save (reply) — yanıtlanan medya/mesajı kaydet
• .save <link> — linkteki medyayı kaydet
  t.me/kanal/123  •  t.me/c/ID/123
• .dlmedia (reply) — medyayı indir ve kaydet

Kısıtlı gruplar dahil tüm chatlerde çalışır.
"""

HELP_ADMIN = """🛡 **Yönetim**

• .ban [reply/@u] [sebep] — banla
• .unban [reply/@u] — ban kaldır
• .kick [reply/@u] [sebep] — at
• .mute [reply/@u] [dk] — sustur
• .unmute [reply/@u] — kaldır
• .promote / .demote [reply/@u] — yetki
• .pin [loud] (reply) — sabitle
• .unpin — kaldır
• .admins — yönetici listesi
• .zombies [clean] — silinmiş hesap tara
• .warn [reply/@u] [sebep] — uyar (3 → otoban)
• .unwarn / .warns [reply/@u] — uyarı yönetimi
• .gban / .ungban [reply/@u] — global ban
• .gmute / .ungmute [reply/@u] — global susturma
"""

# HELP_WARN merged into HELP_ADMIN — kept for compat
HELP_WARN = HELP_ADMIN

HELP_NOTES = """📝 **Notlar**

• .save <ad> <metin> — not kaydet
• .save <ad> (reply) — mesajı not kaydet
• .get <ad> — notu getir
• .delnote <ad> — notu sil
• .notes — tüm notları listele
"""

HELP_TOOLS = """🔧 **Araçlar**

• .id / .info / .chatinfo — bilgi
• .hava <şehir> — hava durumu
• .çevir — çeviri
• .purge (reply) — aralık temizle (max 50, DM korumalı)
• .del (reply) — tek mesaj sil
• .purgeme <sayı> — kendi mesajlarını sil
• .log2alfa / .ping / .afk — durum/hız
"""

HELP_PLUGINS = """🔌 **Pluginler (133)**

• .phelp — tüm pluginler ve komutları
• .phelp <sayı> — sayfalı liste (örn: .phelp 2)

Özel plugin yüklemek için .py dosyası gönder (sadece admin).
"""

PANEL_TEXT = """◼️ **LOG2 ALFA PANEL**
┌ Durum : {status}
├ Hesap : {hesap}
├ Aktif  : {count}
└ Uptime: {uptime}

— vayko edition —
"""

# ====== BUTONLAR ======
def start_kb(is_logged=False):
    rows = []
    if is_logged:
        rows.append([InlineKeyboardButton(smalls("◼️ Panel"), callback_data="panel")])
    else:
        rows.append([InlineKeyboardButton(smalls("▸ Giriş Yap"), callback_data="panel")])
    # Destek kapalı - sadece Yardım + Geliştirici
    if SUPPORT_URL:
        rows.append([
            InlineKeyboardButton(smalls("▸ Yardım"), callback_data="show_help"),
            InlineKeyboardButton(smalls("💬 Destek"), url=SUPPORT_URL),
        ])
    else:
        rows.append([InlineKeyboardButton(smalls("▸ Yardım"), callback_data="show_help")])
    if DEV_URL:
        rows.append([InlineKeyboardButton(smalls("vayko"), url=DEV_URL)])
    return InlineKeyboardMarkup(rows)

def retry_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(smalls("🚀 Baştan Giriş Yap"), callback_data="panel")],
        [InlineKeyboardButton(smalls("❌ İptal"), callback_data="cancel_login")],
    ])

def phone_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(smalls("❌ İptal"), callback_data="cancel_login")],
    ])

def code_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(smalls("🔄 Yeni Kod İste"), callback_data="new_code")],
        [InlineKeyboardButton(smalls("❌ İptal"), callback_data="cancel_login")],
    ])

def help_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(smalls("💾 Medya"), callback_data="help_media"),
         InlineKeyboardButton(smalls("🛡 Yönetim"), callback_data="help_admin")],
        [InlineKeyboardButton(smalls("📝 Notlar"), callback_data="help_notes"),
         InlineKeyboardButton(smalls("🔧 Araçlar"), callback_data="help_tools")],
        [InlineKeyboardButton(smalls("◀️ Ana Menü"), callback_data="back_to_main"),
         InlineKeyboardButton(smalls("🔌 Pluginler"), callback_data="help_plugins")],
    ])

def help_section_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(smalls("◀️ Menüye Dön"), callback_data="show_help")],
        [InlineKeyboardButton(smalls("🏠 Ana Menü"), callback_data="back_to_main")],
    ])

def panel_kb(is_on, is_admin=False):
    rows = []
    if is_on:
        rows.append([
            InlineKeyboardButton(smalls("◼ Durdur"), callback_data="toggle_userbot"),
            InlineKeyboardButton(smalls("↻ Yenile"), callback_data="restart_userbot"),
        ])
    else:
        rows.append([
            InlineKeyboardButton(smalls("▶ Başlat"), callback_data="toggle_userbot"),
            InlineKeyboardButton(smalls("↻ Yenile"), callback_data="restart_userbot"),
        ])
    rows.append([
        InlineKeyboardButton(smalls("📋 Komutlar"), callback_data="show_help"),
        InlineKeyboardButton(smalls("📊 Durum"), callback_data="user_status"),
    ])
    if is_admin:
        rows.append([InlineKeyboardButton(smalls("🛡️ Yönetim Paneli"), callback_data="admin_panel")])
    rows.append([
        InlineKeyboardButton(smalls("🚪 Çıkış Yap"), callback_data="logout"),
        InlineKeyboardButton(smalls("◀️ Ana Menü"), callback_data="back_to_main"),
    ])
    return InlineKeyboardMarkup(rows)

def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(smalls("👥 Kullanıcılar"), callback_data="admin_users"),
         InlineKeyboardButton(smalls("📱 Oturumlar"), callback_data="admin_sessions")],
        [InlineKeyboardButton(smalls("🚫 Engellenenler"), callback_data="admin_blocked"),
         InlineKeyboardButton(smalls("📊 Sistem"), callback_data="admin_system")],
        [InlineKeyboardButton(smalls("🔌 Pluginler"), callback_data="admin_plugins"),
         InlineKeyboardButton(smalls("📣 Duyuru"), callback_data="admin_broadcast")],
        [InlineKeyboardButton(smalls("↻ Yenile"), callback_data="admin_panel"),
         InlineKeyboardButton(smalls("◀️ Panele Dön"), callback_data="panel")],
    ])

def broadcast_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(smalls("📥 Kayıtlı Mesajlar (Userbot)"), callback_data="bc_target:saved")],
        [InlineKeyboardButton(smalls("✉️ DM (Bot)"), callback_data="bc_target:dm")],
        [InlineKeyboardButton(smalls("◀️ Yönetim"), callback_data="admin_panel")],
    ])

def broadcast_report_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(smalls("📣 Yeni Duyuru"), callback_data="admin_broadcast"),
         InlineKeyboardButton(smalls("◀️ Geri"), callback_data="admin_panel")],
    ])

def broadcast_cancel_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(smalls("❌ İptal"), callback_data="bc_cancel")],
        [InlineKeyboardButton(smalls("◀️ Yönetim"), callback_data="admin_panel")],
    ])

def group_notice_kb():
    uname = getattr(_bot_me_cache, "username", None) or ""
    dm_url = f"https://t.me/{uname}?start=start" if uname else "https://t.me/"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(smalls("💬 DM Gel"), url=dm_url)],
        [InlineKeyboardButton(smalls("🧩 Geliştirici"), url=DEV_URL)] if DEV_URL else [InlineKeyboardButton(smalls("🏠 Ana Menü"), callback_data="back_to_main")],
    ])

async def _get_bot_me(client):
    global _bot_me_cache
    if _bot_me_cache is None:
        try:
            _bot_me_cache = await client.get_me()
        except Exception:
            return None
    return _bot_me_cache

def admin_back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(smalls("◀️ Yönetime Dön"), callback_data="admin_panel")],
        [InlineKeyboardButton(smalls("🏠 Ana Menü"), callback_data="back_to_main")],
    ])

def plugins_kb(plugins, page=0):
    # 2 yan yana, 5 satir = 10 plugin/sayfa, altinda sayfa gecisi
    per = 10
    total = len(plugins)
    pages = (total + per - 1) // per if total else 1
    page = max(0, min(int(page), pages-1))
    start = page * per
    slice_plugs = plugins[start:start+per]
    rows = []
    # 2'ser yan yana grid
    for i in range(0, len(slice_plugs), 2):
        chunk = slice_plugs[i:i+2]
        row = []
        for pl in chunk:
            name = pl['name']
            # buton label kisa tut
            label = name[:18]
            row.append(InlineKeyboardButton(smalls(label), callback_data=f"plugin_del:{name}"))
        rows.append(row)
    if not slice_plugs:
        rows.append([InlineKeyboardButton(smalls("— boş —"), callback_data="noop")])
    # sayfa gecis bar - 2 buton arasi page indicator
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(smalls("◀️"), callback_data=f"admin_plugins_page:{page-1}"))
        nav.append(InlineKeyboardButton(smalls(f"{page+1}/{pages}"), callback_data="noop"))
        if page + 1 < pages:
            nav.append(InlineKeyboardButton(smalls("▶️"), callback_data=f"admin_plugins_page:{page+1}"))
        rows.append(nav)
    # alt bar
    rows.append([
        InlineKeyboardButton(smalls("↻ Yenile"), callback_data=f"admin_plugins_page:{page}"),
        InlineKeyboardButton(smalls("◀️ Yönetim"), callback_data="admin_panel")
    ])
    return InlineKeyboardMarkup(rows)

def users_kb(users, page=0):
    # 2 yan yana, 5 satir = 10 kullanici/sayfa — pluginler gibi sayfali
    per = 10
    total = len(users)
    pages = (total + per - 1) // per if total else 1
    page = max(0, min(int(page), pages - 1))
    start = page * per
    slice_users = users[start:start + per]
    rows = []
    for i in range(0, len(slice_users), 2):
        row = []
        for u in slice_users[i:i + 2]:
            uid = u["telegram_id"]
            name = (u.get("first_name") or u.get("username") or "kullanıcı").strip()[:11]
            try:
                live = uid in active_userbots and getattr(active_userbots.get(uid), "is_connected", False)
            except Exception:
                live = False
            emoji = "🟢" if live else "⚪"
            row.append(InlineKeyboardButton(smalls(f"{emoji} {name}"),
                                            callback_data=f"admin_user_view:{uid}"))
        rows.append(row)
    if not slice_users:
        rows.append([InlineKeyboardButton(smalls("— kayıt yok —"), callback_data="noop")])
    # sayfa geçiş barı
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(smalls("◀️ Geri"), callback_data=f"admin_users_page:{page-1}"))
        nav.append(InlineKeyboardButton(smalls(f"{page+1}/{pages}"), callback_data="noop"))
        if page + 1 < pages:
            nav.append(InlineKeyboardButton(smalls("İleri ▶️"), callback_data=f"admin_users_page:{page+1}"))
        rows.append(nav)
    rows.append([
        InlineKeyboardButton(smalls("↻ Yenile"), callback_data=f"admin_users_page:{page}"),
        InlineKeyboardButton(smalls("◀️ Yönetim"), callback_data="admin_panel"),
    ])
    return InlineKeyboardMarkup(rows)

def sessions_kb(items, page=0):
    """Oturumlar + aktif botlar — 2 yan yana, 5 satir (10/sayfa), sayfali."""
    per = 10
    total = len(items)
    pages = (total + per - 1) // per if total else 1
    page = max(0, min(int(page), pages - 1))
    start = page * per
    slice_items = items[start:start + per]
    rows = []
    for i in range(0, len(slice_items), 2):
        row = []
        for it in slice_items[i:i + 2]:
            uid = it["owner_id"]
            name = it.get("uname") or ((it.get("phone") or "")[-10:] or str(uid))
            if it.get("live"):
                emoji = "🟢"
            elif it.get("is_active"):
                emoji = "🟡"
            else:
                emoji = "⚪"
            label = f"{emoji} {name}"
            row.append(InlineKeyboardButton(smalls(label), callback_data=f"admin_sess_view:{uid}"))
        rows.append(row)
    if not slice_items:
        rows.append([InlineKeyboardButton(smalls("— oturum yok —"), callback_data="noop")])
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(smalls("◀️ Geri"), callback_data=f"admin_sessions_page:{page-1}"))
        nav.append(InlineKeyboardButton(smalls(f"{page+1}/{pages}"), callback_data="noop"))
        if page + 1 < pages:
            nav.append(InlineKeyboardButton(smalls("İleri ▶️"), callback_data=f"admin_sessions_page:{page+1}"))
        rows.append(nav)
    rows.append([
        InlineKeyboardButton(smalls("↻ Yenile"), callback_data=f"admin_sessions_page:{page}"),
        InlineKeyboardButton(smalls("◀️ Yönetim"), callback_data="admin_panel"),
    ])
    return InlineKeyboardMarkup(rows)

def sess_detail_kb(uid, live=False):
    if live:
        toggle = InlineKeyboardButton(smalls("◼ Durdur"), callback_data=f"admin_user_toggle:{uid}")
    else:
        toggle = InlineKeyboardButton(smalls("▶ Başlat"), callback_data=f"admin_user_toggle:{uid}")
    return InlineKeyboardMarkup([
        [toggle,
         InlineKeyboardButton(smalls("↻ Yenile"), callback_data=f"admin_sess_restart:{uid}")],
        [InlineKeyboardButton(smalls("👤 Kullanıcı Detayı"), callback_data=f"admin_user_view:{uid}"),
         InlineKeyboardButton(smalls("× Sil"), callback_data=f"admin_user_del:{uid}")],
        [InlineKeyboardButton(smalls("◀️ Listeye Dön"), callback_data="admin_sessions")],
    ])

def user_detail_kb(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(smalls("◼ Durdur"), callback_data=f"admin_user_toggle:{uid}"),
         InlineKeyboardButton(smalls("× Sil"), callback_data=f"admin_user_del:{uid}")],
        [InlineKeyboardButton(smalls("⛔ Engelle"), callback_data=f"admin_user_block:{uid}"),
         InlineKeyboardButton(smalls("✅ Engel Kaldır"), callback_data=f"admin_user_unblock:{uid}")],
        [InlineKeyboardButton(smalls("◀️ Listeye Dön"), callback_data="admin_users")],
    ])

def blocked_kb(items, page=0):
    """Engellenenler — pluginler gibi 2 yan yana × 5 satır (10/sayfa) + sayfalama."""
    per = 10
    total = len(items)
    pages = (total + per - 1) // per if total else 1
    page = max(0, min(int(page or 0), pages - 1))
    sl = items[page * per:(page + 1) * per]
    rows = []
    for i in range(0, len(sl), 2):
        row = []
        for it in sl[i:i + 2]:
            lbl = f"✅ @{it['name']}"
            if it.get("reason"):
                lbl += f" — {it['reason'][:14]}"
            row.append(InlineKeyboardButton(smalls(lbl), callback_data=f"admin_unblock:{it['uid']}:{page}"))
        rows.append(row)
    if not sl:
        rows.append([InlineKeyboardButton(smalls("— engelli yok —"), callback_data="noop")])
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(smalls("◀️ Geri"), callback_data=f"admin_blocked_page:{page-1}"))
        nav.append(InlineKeyboardButton(smalls(f"{page+1}/{pages}"), callback_data="noop"))
        if page + 1 < pages:
            nav.append(InlineKeyboardButton(smalls("İleri ▶️"), callback_data=f"admin_blocked_page:{page+1}"))
        rows.append(nav)
    rows.append([
        InlineKeyboardButton(smalls("↻ Yenile"), callback_data=f"admin_blocked_page:{page}"),
        InlineKeyboardButton(smalls("◀️ Yönetim"), callback_data="admin_panel"),
    ])
    return InlineKeyboardMarkup(rows)

# Login kontrol + engel kontrol
bot_app: Client = None

async def is_logged(uid: int) -> bool:
    return (await database.get_session(uid)) is not None

async def is_blocked_check(uid: int) -> bool:
    try:
        return await database.is_blocked(uid)
    except:
        return False

async def safe_delete(c: Client, chat: int, mid: int):
    try: await c.delete_messages(chat, mid)
    except: pass

def _flood_seconds(err: str):
    m = re.search(r"FloodWait:?\s*(\d+)", str(err))
    return m.group(1) if m else "birkaç saniye"

async def _send_new_code(client: Client, uid: int, state: dict, chat_id: int, reason: str = ""):
    from userbot_core import temp_login_clients
    # Max 3 kod isteme (kalan hak gösterilmez)
    cnt = int(state.get("code_requests", 0))
    if cnt >= 3:
        return False, "Kod isteme limitine ulaştınız. Lütfen daha sonra tekrar deneyin."
    old = temp_login_clients.pop(uid, None)
    if old:
        try: await old["client"].disconnect()
        except: pass
    phone = state.get("phone")
    if not phone:
        return False, "Telefon numaranız gerekli."
    try:
        await initiate_login(config.API_ID, config.API_HASH, phone, uid)
    except Exception as e:
        err = str(e)
        if "FloodWait" in err:
            return False, f"Çok hızlı istek — {_flood_seconds(err)} saniye bekleyin."
        if "geçersiz" in err.lower():
            return False, "Telefon numarası geçersiz — +90 ile başlayarak kontrol edin."
        return False, "Kod gönderilemedi — lütfen biraz sonra tekrar deneyin."
    state["step"] = "await_code"
    state["code_requests"] = cnt + 1
    # Yeni kod sonrası da buton gizli kalsın (sadece hatada gösterilecek)
    prefix = {"wrong": "Kod hatalı — ", "expired": "Kod süresi doldu — "}.get(reason, "")
    msg = smalls(prefix + "Yeni kod gönderildi. 5 haneli kodu gönderin (örnek: 1 2 3 4 5)")
    prompt_id = state.get("prompt_msg_id")
    try:
        if prompt_id:
            try: await client.edit_message_text(chat_id, prompt_id, msg, reply_markup=phone_kb())
            except: await client.edit_message_caption(chat_id, prompt_id, caption=msg, reply_markup=phone_kb())
        else:
            sent = await client.send_message(chat_id, msg, reply_markup=phone_kb())
            state["prompt_msg_id"] = sent.id
    except Exception as e:
        print(f"new_code hata: {e}", flush=True)
    return True, msg

async def smart_edit(query: CallbackQuery, text: str, kb: InlineKeyboardMarkup, client: Client = None):
    try:
        text = smalls(text)
    except:
        pass
    # Uzun caption desteği: foto mesajda 1024'ü aşarsa foto+caption editlenemez — yeni mesaj gönder
    def _caption_too_long(err: str) -> bool:
        s = (err or "").lower()
        return "caption_too_long" in s or "media_caption_too_long" in s or "caption is too long" in s

    msg = query.message
    is_photo = bool(getattr(msg, "photo", None) or getattr(msg, "caption", None) is not None)
    # Eğer foto ve metin 1024'ü aşıyorsa direkt yeni mesaj dene
    if is_photo and len(text) > 1000:
        try:
            # Eski foto mesajı sil ve yeni text gönder — daha güvenilir
            try:
                await query.message.delete()
            except:
                try:
                    if client:
                        await client.delete_messages(query.message.chat.id, query.message.id)
                except: pass
            c = client or msg._client if hasattr(msg, "_client") else client
            if c is None:
                c = query._client if hasattr(query, "_client") else None
            # Fallback client
            if c:
                await c.send_message(query.message.chat.id, text, reply_markup=kb)
                return True
            else:
                # client yoksa query.message üzerinden reply
                await query.message.reply_text(text, reply_markup=kb)
                return True
        except Exception as e:
            print(f"smart_edit long caption send fallback: {e}")

    try:
        if is_photo:
            try:
                await msg.edit_caption(caption=text, reply_markup=kb)
                return True
            except MessageNotModified:
                return True
            except Exception as e:
                if _caption_too_long(str(e)):
                    # Foto caption çok uzun — sil ve yeni text gönder
                    try:
                        try: await query.message.delete()
                        except: pass
                        c = client or getattr(query, "_client", None)
                        if c:
                            await c.send_message(query.message.chat.id, text, reply_markup=kb)
                            return True
                    except Exception as e2:
                        print(f"smart_edit caption long fallback2: {e2}")
                try:
                    await msg.edit_text(text, reply_markup=kb)
                    return True
                except: pass
        else:
            try:
                await msg.edit_text(text, reply_markup=kb)
                return True
            except MessageNotModified:
                return True
            except Exception as e:
                if _caption_too_long(str(e)):
                    try:
                        c = client or getattr(query, "_client", None)
                        if c:
                            await c.send_message(query.message.chat.id, text, reply_markup=kb)
                            try: await query.message.delete()
                            except: pass
                            return True
                    except Exception as e2:
                        print(f"smart_edit text long fallback: {e2}")
                try:
                    await msg.edit_caption(caption=text, reply_markup=kb)
                    return True
                except: pass
    except Exception as e:
        print(f"smart_edit hata: {e}")
    try:
        if client:
            m = query.message
            if m.photo:
                try:
                    await client.edit_message_caption(m.chat.id, m.id, caption=text, reply_markup=kb)
                    return True
                except Exception as e:
                    if _caption_too_long(str(e)):
                        try: await client.delete_messages(m.chat.id, m.id)
                        except: pass
                        await client.send_message(m.chat.id, text, reply_markup=kb)
                        return True
                    raise
            else:
                await client.edit_message_text(m.chat.id, m.id, text, reply_markup=kb)
            return True
    except Exception as e:
        print(f"smart_edit fallback: {e}")
        if _caption_too_long(str(e)):
            try:
                m = query.message
                c = client or getattr(query, "_client", None)
                if c:
                    try: await c.delete_messages(m.chat.id, m.id)
                    except: pass
                    await c.send_message(m.chat.id, text, reply_markup=kb)
                    return True
            except Exception as e2:
                print(f"smart_edit fallback long2: {e2}")
    return False

# ====== HANDLERS ======
async def start_handler(client: Client, message: Message):
    try:
        if await is_blocked_check(message.from_user.id):
            await message.reply_text("⛔ Erişiminiz engellenmiştir. Destek için geliştirici ile iletişime geçin.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(smalls("vayko"), url=DEV_URL)]]))
            return
        user = message.from_user
        await database.save_owner(user.id, user.username or "", user.first_name or "")
        name = user.first_name or "değerli kullanıcı"
        logged = await is_logged(user.id)
        text = smalls(START_TEXT.format(name=name))
        # Dark banner - siyah beyaz uyumlu
        import os
        banner_candidates = [
            os.path.join(os.path.dirname(__file__), "assets", "banner_dark_v2.png"),
            os.path.join(os.path.dirname(__file__), "assets", "banner_dark.png"),
            os.path.join(os.path.dirname(__file__), "assets", "log2alfa_banner.png"),
            os.path.join(os.path.dirname(__file__), "log2alfa_banner.png"),
            "assets/banner_dark.png",
            "assets/log2alfa_banner.png",
        ]
        banner = next((b for b in banner_candidates if os.path.exists(b)), None)
        if banner:
            try:
                await message.reply_photo(photo=banner, caption=text, reply_markup=start_kb(logged))
            except Exception as e:
                print(f"banner send hata {e}, fallback text", flush=True)
                await message.reply_text(text, reply_markup=start_kb(logged))
        else:
            await message.reply_text(text, reply_markup=start_kb(logged))
    except Exception as e:
        print(f"start hata: {e}", flush=True)
        try: await message.reply_text(smalls("Bir hata oluştu. Lütfen /start ile tekrar deneyin."))
        except: pass

async def help_handler(client: Client, message: Message):
    try:
        uid = message.from_user.id if message.from_user else 0
        logged = await is_logged(uid)
        if not logged:
            txt = HELP_LOGIN_TEXT
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(smalls("▸ Giriş Yap"), callback_data="panel")],
                [InlineKeyboardButton(smalls("◀️ Ana Menü"), callback_data="back_to_main")]
            ])
            await message.reply_text(smalls(txt), reply_markup=kb)
        else:
            # Giriş yapmışsa bölümlü menü gönder (banner varsa fotoğrafla değil, text olarak)
            await message.reply_text(smalls(HELP_MAIN), reply_markup=help_menu_kb())
    except Exception as e:
        print(f"help hata: {e}", flush=True)

# Admin metin yardımcıları
async def _admin_users_text(page=0):
    import aiosqlite
    users = await database.get_all_owners()
    total = len(users)
    try:
        blocked = len(await database.get_blocked_users())
    except:
        blocked = 0
    try:
        sessions = len(await database.get_all_sessions())
    except:
        sessions = 0
    per = 10
    pages = (total + per - 1) // per if total else 1
    page = max(0, min(int(page), pages - 1))
    txt = f"👥 **Kullanıcı Yönetimi**\n\n"
    txt += f"Toplam kullanıcı: **{total}**\n"
    txt += f"Aktif oturum: **{sessions}**\n"
    txt += f"Engellenen: **{blocked}**\n"
    txt += f"Canlı bot: **{len(active_userbots)}**\n\n"
    if not users:
        txt += "Henüz kayıtlı kullanıcı yok.\n"
    else:
        txt += f"Sayfa **{page+1}/{pages}** • Sayfa başına **{per}** kullanıcı\n"
        txt += "Detay için bir kullanıcıya dokunun.\n"
    return txt, users

async def _admin_sessions_text(page=0):
    """Oturumlar ve aktif botlar TEK sayfa — 2 yan yana, 5 satir (10/sayfa)."""
    sessions = await database.get_all_sessions()
    per = 10
    items = []
    seen = set()
    # owner_id -> kullanıcı adı (kartlarda numara yerine username gösterilir)
    name_map = {}
    try:
        for o in await database.get_all_owners():
            oid = o.get("telegram_id")
            name_map[oid] = (o.get("username") or "").strip() or (o.get("first_name") or "").strip()
    except Exception:
        pass
    # 1) aktif (canlı) botlar önce
    for oid, app in list(active_userbots.items()):
        try:
            is_live = bool(getattr(app, "is_connected", False))
        except Exception:
            is_live = False
        phone = ""
        is_active = False
        created = "-"
        for s in sessions:
            if s["owner_id"] == oid:
                phone = s.get("phone") or ""
                is_active = bool(s.get("is_active"))
                created = s.get("created_at") or "-"
                break
        items.append({"owner_id": oid, "phone": phone, "live": is_live,
                      "is_active": is_active, "created": created,
                      "uname": name_map.get(oid) or phone})
        seen.add(oid)
    # 2) kayıtlı oturumlar (canlı olanlar zaten eklendi)
    for s in sessions:
        oid = s["owner_id"]
        if oid in seen:
            continue
        items.append({"owner_id": oid, "phone": s.get("phone") or "",
                      "live": False, "is_active": bool(s.get("is_active")),
                      "created": s.get("created_at") or "-",
                      "uname": name_map.get(oid) or (s.get("phone") or "") or str(oid)})
        seen.add(oid)

    total = len(items)
    pages = (total + per - 1) // per if total else 1
    page = max(0, min(int(page), pages - 1))
    live_c = sum(1 for i in items if i["live"])
    act_c = sum(1 for i in items if i["is_active"])
    txt = "📱 Oturumlar\n\n"
    txt += f"Toplam: {total}\n"
    txt += f"Canlı bot: {live_c} | Aktif oturum: {act_c}\n"
    txt += f"• Sayfa {page+1}/{pages}\n\n"
    txt += "Detay ve işlemler için aşağıdaki buttonlardan yönetebilirsin."
    return txt, items

async def _admin_active_text():
    txt = f"🤖 **Aktif Userbotlar** — Canlı: {len(active_userbots)} | Uptime: {get_uptime()}\n"
    try:
        import psutil
        txt += f"CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}%\n"
    except: pass
    txt += "\n"
    if not active_userbots:
        txt += "Şu an aktif userbot yok.\n"
    else:
        for oid, app in list(active_userbots.items()):
            try:
                me = await app.get_me()
                name = me.first_name or "-"
                uname = f"@{me.username}" if me.username else "-"
                status = "🟢 Bağlı" if app.is_connected else "🔴 Kopuk"
                txt += f"**• {name}** {uname}\n  ID: `{me.id}` | Sahip: `{oid}` | {status}\n"
                try:
                    from utils.plugin_loader import list_plugins
                    pc = len(list_plugins())
                    txt += f"  Ek plugin: {pc}\n"
                except: pass
                txt += "\n"
            except Exception as e:
                err = str(e)
                if "AUTH_KEY_UNREGISTERED" in err or "401" in err:
                    txt += f"• Sahip `{oid}` — ⚠️ Oturum geçersiz, yeniden giriş gerekli\n"
                    txt += f"  → Yönetimden silip tekrar ekleyin\n\n"
                else:
                    txt += f"• Sahip `{oid}` — hata: {err[:120]}\n\n"
    return smalls(txt)

async def _admin_system_text():
    import psutil, platform
    txt = f"📊 **Sistem Durumu**\n\n"
    txt += f"Uptime: {get_uptime()}\n"
    try:
        txt += f"CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}%\n"
        txt += f"Disk: {psutil.disk_usage('/').percent}%\n"
    except: pass
    txt += f"Platform: {platform.system()} {platform.release()}\n"
    txt += f"Aktif botlar: {len(active_userbots)}\n"
    try:
        total_users = len(await database.get_all_owners())
        total_sess = len(await database.get_all_sessions())
        blocked = len(await database.get_blocked_users())
        txt += f"Kullanıcılar: {total_users} | Oturumlar: {total_sess} | Engellenen: {blocked}\n"
    except: pass
    return smalls(txt)

async def _admin_blocked_text(page=0):
    blocked = await database.get_blocked_users()
    per = 10
    name_map = {}
    try:
        for o in await database.get_all_owners():
            _oid = o.get("telegram_id")
            name_map[_oid] = (o.get("username") or "").strip() or (o.get("first_name") or "").strip()
    except Exception:
        pass
    items = []
    for b in blocked:
        _uid = b.get("telegram_id")
        items.append({
            "uid": _uid,
            "name": name_map.get(_uid) or f"id{_uid}",
            "reason": (b.get("reason") or "").strip(),
            "at": b.get("blocked_at") or "-",
        })
    total = len(items)
    pages = (total + per - 1) // per if total else 1
    page = max(0, min(int(page or 0), pages - 1))
    txt = "🚫 Engellenen Kullanıcılar\n\n"
    txt += f"Toplam: {total}\n"
    txt += f"• Sayfa {page+1}/{pages}\n\n"
    txt += "Engeli kaldırmak için aşağıdaki buttonlardan yönetebilirsin."
    return txt, items

async def _admin_plugins_text(page=0):
    from utils.plugin_loader import list_plugins
    plugins = list_plugins()
    total = len(plugins)
    per = 10
    pages = (total + per - 1) // per if total else 1
    page = max(0, min(int(page), pages-1))
    txt = f"🔌 **Pluginler** — Toplam **{total}**\n"
    if total:
        txt += f"Sayfa **{page+1}/{pages}** • Silmek icin dokunun\n"
    else:
        txt += "Henuz plugin yok.\n"
    return txt, plugins

# ══════════════════════════ DUYURU (BROADCAST) ══════════════════════════

DUYURU_TTL = 1800  # 30 dk

async def _duyuru_pending(uid):
    """Duyuru bekleme durumunu döndürür: bellekte yoksa DB'den (bot yeniden başlasa da kaybolmaz)."""
    st = duyuru_state.get(uid)
    if st:
        return st
    try:
        raw = await database.get_setting("duyuru_pending") or "{}"
        data = json.loads(raw)
        rec = data.get(str(uid))
        if rec and (time.time() - float(rec.get("ts", 0))) < DUYURU_TTL:
            return {"target": rec.get("target") or "dm", "step": "await_content"}
        if rec:
            data.pop(str(uid), None)
            await database.set_setting("duyuru_pending", json.dumps(data))
    except Exception:
        pass
    return None

async def _duyuru_set_pending(uid, target):
    duyuru_state[uid] = {"target": target, "step": "await_content", "started_at": time.time()}
    try:
        raw = await database.get_setting("duyuru_pending") or "{}"
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
        data = {k: v for k, v in data.items()
                if (time.time() - float((v or {}).get("ts", 0))) < DUYURU_TTL}
        data[str(uid)] = {"target": target, "ts": time.time()}
        await database.set_setting("duyuru_pending", json.dumps(data))
    except Exception as e:
        print(f"[DUYURU] pending kaydedilemedi: {e}", flush=True)

async def _duyuru_clear_pending(uid):
    duyuru_state.pop(uid, None)
    try:
        raw = await database.get_setting("duyuru_pending") or "{}"
        data = json.loads(raw)
        if str(uid) in data:
            data.pop(str(uid), None)
            await database.set_setting("duyuru_pending", json.dumps(data))
    except Exception:
        pass

async def _bc_users_text():
    """Duyuru ekranı metnini gerçek verilerle üretir."""
    users = []
    try:
        users = await database.get_all_owners()
    except Exception:
        users = []
    live = 0
    for _oid, app in list(active_userbots.items()):
        try:
            if getattr(app, "is_connected", False):
                live += 1
        except Exception:
            pass
    last = ""
    try:
        ts = await database.get_setting("last_duyuru_ts")
        summ = await database.get_setting("last_duyuru_summary")
        if ts and summ:
            last = f"Son duyuru: {ts} — {summ}\n"
    except Exception:
        pass
    return BROADCAST_TEXT.format(users=len(users), live=live, last=last)


async def _send_content(cl, chat_id, content):
    """İçeriği (metin/foto/video/dosya/ses) hedefe gönderir.
    Medya: elde yerel dosya yolu (path) varsa yükleyerek gönderir — bot file_id'si
    başka bir hesap/oturumda geçersiz olduğu için (MEDIA_EMPTY) bu şart."""
    kind = content.get("kind")
    cap = content.get("caption") or ""
    if kind == "text":
        return await cl.send_message(chat_id, content.get("text") or "")
    src = content.get("path") or content.get("file_id")
    if not src:
        raise ValueError("medya kaynağı yok (indirme başarısız)")
    if kind == "photo":
        return await cl.send_photo(chat_id, src, caption=cap)
    if kind == "video":
        return await cl.send_video(chat_id, src, caption=cap)
    if kind == "document":
        return await cl.send_document(chat_id, src, caption=cap)
    if kind == "audio":
        return await cl.send_audio(chat_id, src, caption=cap)
    if kind == "animation":
        return await cl.send_animation(chat_id, src, caption=cap)
    if kind == "voice":
        return await cl.send_voice(chat_id, src, caption=cap)
    if kind == "sticker":
        return await cl.send_sticker(chat_id, src)
    return await cl.send_message(chat_id, content.get("text") or "📣")


def _report_text(target, total, ok, skip, fail, secs, errors):
    head = "📥 Kayıtlı Mesajlar (userbot)" if target == "saved" else "✉️ DM (bot)"
    txt = "📣 Duyuru Raporu\n\n"
    txt += f"Hedef: {head}\n"
    txt += f"Toplam hedef: {total}\n"
    txt += f"Başarılı: {ok}\n"
    txt += f"Atlandı: {skip}\n"
    txt += f"Hata: {fail}\n"
    txt += f"Süre: {int(secs)}sn\n"
    if errors:
        txt += "\nHatalar (ilk 5):\n"
        for e in errors[:5]:
            txt += f"• {e}\n"
    if ok == 0:
        txt += "\nNot: hiç gönderim yapılamadı, hedef listesini kontrol edin."
    return txt.strip()


async def _run_broadcast(client, admin_id, target, content, report_msg=None):
    """Duyuruyu arka planda gönderir; raporu YENİ MESAJ atmadan mevcut mesajı güncelleyerek verir.
    report_msg: (chat_id, message_id) — 'Duyuru gönderiliyor...' mesajı."""
    async def _send_report(text, kb=None):
        text = smalls(text)
        if report_msg:
            try:
                await client.edit_message_text(report_msg[0], report_msg[1], text, reply_markup=kb)
                return True
            except Exception as e:
                try:
                    await client.edit_message_caption(report_msg[0], report_msg[1], caption=text, reply_markup=kb)
                    return True
                except Exception as e2:
                    print(f"rapor mesajı güncellenemedi ({e} / {e2}) → yeni mesaj", flush=True)
        try:
            await client.send_message(admin_id, text, reply_markup=kb)
            return True
        except Exception as e:
            print(f"duyuru raporu gönderilemedi: {e}", flush=True)
            return False
    t0 = time.time()
    ok = skip = fail = 0
    total = 0
    errors = []
    erken = False
    try:
        if target == "saved":
            hedefler = []
            for oid, app in list(active_userbots.items()):
                try:
                    if getattr(app, "is_connected", False):
                        hedefler.append((oid, app))
                except Exception:
                    pass
            total = len(hedefler)
            if not hedefler:
                await _send_report("📣 Duyuru Raporu\n\nHedef: 📥 Kayıtlı Mesajlar (userbot)\nCanlı userbot bulunamadı — gönderim yapılamadı.", broadcast_report_kb())
                erken = True
                return
            for oid, app in hedefler:
                try:
                    await _send_content(app, "me", content)
                    ok += 1
                except FloodWait as e:
                    try:
                        await asyncio.sleep(int(getattr(e, "value", 5)) + 2)
                        await _send_content(app, "me", content)
                        ok += 1
                    except Exception as e2:
                        fail += 1
                        errors.append(f"{oid}: {str(e2)[:60]}")
                except Exception as e:
                    _s = str(e)
                    if "CHAT_WRITE_FORBIDDEN" in _s or "USER_DEACTIVATED" in _s or "AUTH_KEY" in _s:
                        skip += 1
                    else:
                        fail += 1
                        errors.append(f"{oid}: {_s[:60]}")
                await asyncio.sleep(1.2)
        else:
            try:
                users = await database.get_all_owners()
            except Exception:
                users = []
            total = len(users)
            if not users:
                await _send_report("📣 Duyuru Raporu\n\nHedef: ✉️ DM (bot)\nKayıtlı kullanıcı bulunamadı — gönderim yapılamadı.", broadcast_report_kb())
                erken = True
                return
            for u in users:
                oid = u.get("telegram_id")
                if not oid:
                    continue
                try:
                    if await database.is_blocked(oid):
                        skip += 1
                        continue
                except Exception:
                    pass
                try:
                    await _send_content(client, oid, content)
                    ok += 1
                except FloodWait as e:
                    try:
                        await asyncio.sleep(int(getattr(e, "value", 5)) + 2)
                        await _send_content(client, oid, content)
                        ok += 1
                    except Exception as e2:
                        fail += 1
                        errors.append(f"{oid}: {str(e2)[:60]}")
                except Exception as e:
                    _s = str(e)
                    if "PEER_ID_INVALID" in _s or "USER_IS_BLOCKED" in _s or "BOT_BLOCKED" in _s or "USER_PRIVACY_RESTRICTED" in _s or "INPUT_USER_DEACTIVATED" in _s:
                        skip += 1
                    else:
                        fail += 1
                        errors.append(f"{oid}: {_s[:60]}")
                await asyncio.sleep(0.8)
    except Exception as e:
        errors.append(f"genel: {str(e)[:80]}")
    finally:
        try:
            _p = content.get("path")
            if _p:
                import os as _os
                _os.remove(_p)
        except Exception:
            pass
        secs = time.time() - t0
        if not erken:
            rapor = _report_text(target, total, ok, skip, fail, secs, errors)
            if ok == 0:
                # hiçbiri gitmedi → rapor + tekrar dene bilgisi TEK mesajda
                rapor += "\n\n🔁 Aynı hedef için içeriği tekrar gönderin."
            await _send_report(rapor, broadcast_report_kb())
        try:
            import datetime as _dt
            await database.set_setting("last_duyuru_ts", _dt.datetime.now().strftime("%d.%m %H:%M"))
            await database.set_setting("last_duyuru_summary", f"{ok}/{total} başarılı" + (f", {fail} hata" if fail else ""))
        except Exception:
            pass
        if not erken:
            if ok == 0:
                # admin içeriği tekrar gönderebilsin (metin algılanmadı sanılmasın)
                await _duyuru_set_pending(admin_id, target)
            else:
                await _duyuru_clear_pending(admin_id)
                duyuru_draft.pop(admin_id, None)
        else:
            # hedef listesi boş (canlı userbot / kullanıcı yok) → beklemeye devam
            await _duyuru_set_pending(admin_id, target)
        print(f"📣 Duyuru bitti ({target}): toplam={total} ok={ok} atlandı={skip} hata={fail}", flush=True)


async def broadcast_input(client: Client, message: Message):
    """Duyuru içeriği beklenirken gelen mesajı yakalar ve yayını başlatır."""
    uid = message.from_user.id if message.from_user else 0
    st = await _duyuru_pending(uid)
    try:
        _lbl = "metin" if message.text else ("medya" if getattr(message, "media", None) else "diğer")
        if st:
            print(f"[DUYURU] gelen mesaj uid={uid} tür={_lbl} bekleyen={st.get('target')}", flush=True)
    except Exception:
        pass
    if not is_admin_user(uid, getattr(message.from_user, "username", None)):
        return
    _raw = (message.text or "").strip()
    # komutlar buraya takılmasın (/start, /panel, .help ...) — /cancel hariç (duyuru iptali)
    if _raw.startswith(("/", ".")) and _raw.lower() not in ("/cancel", "iptal", "cancel"):
        return
    if not st or st.get("step") != "await_content":
        # Hedef seçilmeden içerik gönderildiyse SESSİZCE YUTMA:
        # metni taslak olarak sakla ve hedef seçtir.
        if _raw and (time.time() - duyuru_intro_ts.get(uid, 0)) < DUYURU_TTL:
            duyuru_draft[uid] = {"kind": "text", "text": message.text, "caption": ""}
            print(f"[DUYURU] hedef yok, metin taslağa alındı uid={uid} len={len(_raw)}", flush=True)
            try:
                await message.reply_text(
                    smalls("📣 Bu metni duyuru olarak göndermek ister misin?\n\nHedefi seç, hemen yollayayım:"),
                    reply_markup=broadcast_kb(),
                )
            except Exception as e:
                print(f"[DUYURU] taslak yanıtı gönderilemedi: {e}", flush=True)
        elif getattr(message, "media", None) and (time.time() - duyuru_intro_ts.get(uid, 0)) < DUYURU_TTL:
            try:
                await message.reply_text(
                    smalls("📣 Duyuru için önce hedefi seç, sonra içeriği (foto/video/dosya) gönder:"),
                    reply_markup=broadcast_kb(),
                )
            except Exception:
                pass
        else:
            if _raw or getattr(message, "media", None):
                print(f"[DUYURU] hedef yok + duyuru ekranı açılmamış → yok sayıldı uid={uid}", flush=True)
        return
    # iptal
    if (message.text or "").strip().lower() in ("/cancel", "iptal", "cancel"):
        await _duyuru_clear_pending(uid)
        await message.reply_text(smalls("❌ Duyuru iptal edildi."), reply_markup=admin_back_kb())
        return
    duyuru_state[uid] = st   # belleğe de al
    cap = message.caption or ""
    kind, media_obj = None, None
    if message.text:
        kind = "text"
    else:
        for _k in ("photo", "video", "document", "audio", "animation", "voice", "sticker"):
            if getattr(message, _k, None):
                kind = _k
                media_obj = getattr(message, _k)
                break
    if not kind:
        print(f"[DUYURU] desteklenmeyen içerik uid={uid}", flush=True)
        await message.reply_text(smalls("Bu içerik türünü gönderemiyorum. Metin, foto, video, dosya, ses veya GIF gönderin."),
                                 reply_markup=broadcast_cancel_kb())
        return
    print(f"[DUYURU] içerik algılandı uid={uid} kind={kind} caption={bool(cap)}", flush=True)

    content = {"kind": kind, "caption": cap}
    if kind == "text":
        content["text"] = message.text
    else:
        note = None
        try:
            note = await message.reply_text(smalls("📥 İçerik hazırlanıyor, lütfen bekleyin..."))
        except Exception:
            note = None
        try:
            # Bot file_id'si userbot oturumlarında geçersiz → dosyayı indirip yerelden gönderiyoruz.
            # Uzantı ŞART: uzantısız dosya gönderilirse Telegram PHOTO_EXT_INVALID verir.
            _fn = ""
            try:
                _fn = getattr(media_obj, "file_name", None) or ""
            except Exception:
                _fn = ""
            _ext = os.path.splitext(_fn)[1].lower()
            if not _ext:
                _ext = {"photo": ".jpg", "video": ".mp4", "animation": ".mp4",
                        "voice": ".ogg", "audio": ".mp3", "sticker": ".webp",
                        "document": ".bin"}.get(kind, ".bin")
            _base = f"/tmp/duyuru_{uid}_{int(time.time())}"
            if kind in ("document", "audio") and _fn:
                _safe = re.sub(r"[^A-Za-z0-9._-]", "_", _fn)[-64:] or "dosya"
                _target = f"{_base}_{_safe}"
                if not _target.lower().endswith(_ext):
                    _target += _ext
            else:
                _target = f"{_base}{_ext}"
            path = await client.download_media(message, file_name=_target)
            if not path:
                raise ValueError("indirme başarısız")
            content["path"] = path
            print(f"[DUYURU] medya indirildi kind={kind} path={path}", flush=True)
        except Exception as e:
            print(f"[DUYURU] medya indirilemedi: {e}", flush=True)
            try:
                fid = getattr(media_obj, "file_id", None)
                if fid:
                    content["file_id"] = fid
            except Exception:
                pass
            if not content.get("file_id"):
                try:
                    if note:
                        await note.edit_text(smalls("❌ İçerik indirilemedi (dosya çok büyük olabilir). Lütfen tekrar gönderin."))
                except Exception:
                    pass
                return
        try:
            if note:
                await note.delete()
        except Exception:
            pass

    target = st.get("target") or "dm"
    duyuru_state[uid] = {"target": target, "step": "sending", "started_at": time.time()}
    _rep = None
    try:
        _pm = await message.reply_text(
            smalls("📣 Duyuru gönderiliyor... Bittiğinde rapor gelecek."),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(smalls("◀️ Yönetim"), callback_data="admin_panel")]]),
        )
        _rep = (message.chat.id, getattr(_pm, "id", None))
    except Exception:
        _rep = None
    asyncio.create_task(_run_broadcast(client, uid, target, content, _rep))


async def group_guard(client: Client, message: Message):
    """Kontrol botu gruplarda çalışmaz — sadece DM bilgisi verir."""
    try:
        me = await _get_bot_me(client)
        bot_id = getattr(me, "id", None)
        added = False
        for m in (getattr(message, "new_chat_members", None) or []):
            if bot_id and getattr(m, "id", None) == bot_id:
                added = True
        txt = (message.text or "")
        replied_me = False
        try:
            rt = getattr(message, "reply_to_message", None)
            if rt and getattr(rt, "from_user", None) and bot_id and rt.from_user.id == bot_id:
                replied_me = True
        except Exception:
            replied_me = False
        triggered = added or txt.startswith(("/start", "/help", "/yardim")) or replied_me
        if not triggered:
            return
        chat_id = message.chat.id
        if not added and (time.time() - group_notice_last.get(chat_id, 0)) < 600:
            return
        group_notice_last[chat_id] = time.time()
        await message.reply_text(smalls(GROUP_NOTICE_TEXT), reply_markup=group_notice_kb())
    except Exception as e:
        print(f"group_guard hata: {e}", flush=True)


async def callback_handler(client: Client, query: CallbackQuery):
    data = query.data or ""
    uid = query.from_user.id
    # Engel kontrol — engellenen kullanıcı hiçbir panele giremez (admin hariç)
    if await is_blocked_check(uid) and not is_admin_user(uid, query.from_user.username):
        await query.answer("⛔ Erişiminiz engellenmiş.", show_alert=True)
        return
    try:
        logged = await is_logged(uid)
    except:
        logged = False
    is_admin = is_admin_user(uid, query.from_user.username)

    try:
        if data == "panel":
            if not logged:
                login_state[uid] = {"step": "await_phone", "chat_id": query.message.chat.id, "prompt_msg_id": query.message.id, "started_at": time.time(), "code_requests": 0, "wrong_attempts": 0}
                txt = smalls("📱 Giriş\n\nTelefon numaranızı gönderin:\n+90 5XXXXXXXXX\n\nİptal için /cancel")
                await smart_edit(query, txt, phone_kb(), client)
                await query.answer()
                return
            app = active_userbots.get(uid)
            is_on = bool(app and getattr(app, "is_connected", False))
            hesap = "Bağlı değil"
            if is_on:
                try:
                    me = await app.get_me()
                    hesap = f"{me.first_name} @{me.username or '-'} ({me.id})"
                except: hesap = "Bağlı"
            txt = PANEL_TEXT.format(s=S, status="🟢 Aktif" if is_on else "⚪ Pasif", hesap=hesap, count=len(active_userbots), uptime=get_uptime())
            await smart_edit(query, txt, panel_kb(is_on, is_admin), client)
            await query.answer()

        elif data == "show_help":
            if not logged:
                await smart_edit(query, HELP_LOGIN_TEXT, InlineKeyboardMarkup([
                    [InlineKeyboardButton(smalls("▸ Giriş Yap"), callback_data="panel")],
                    [InlineKeyboardButton(smalls("◀️ Ana Menü"), callback_data="back_to_main")]
                ]), client)
            else:
                # Bölümlü yardım — banner korunur (<900 char her bölüm)
                await smart_edit(query, HELP_MAIN, help_menu_kb(), client)
            await query.answer()
        elif data == "help_media":
            await smart_edit(query, HELP_MEDIA, help_section_kb(), client)
            await query.answer()
        elif data == "help_admin":
            await smart_edit(query, HELP_ADMIN, help_section_kb(), client)
            await query.answer()
        elif data == "help_warn":
            await smart_edit(query, HELP_WARN, help_section_kb(), client)
            await query.answer()
        elif data == "help_notes":
            await smart_edit(query, HELP_NOTES, help_section_kb(), client)
            await query.answer()
        elif data == "help_tools":
            await smart_edit(query, HELP_TOOLS, help_section_kb(), client)
            await query.answer()
        elif data == "help_plugins":
            await smart_edit(query, HELP_PLUGINS, help_section_kb(), client)
            await query.answer()
        elif data == "help_all":
            # Tümünü göster — uzun olduğu için yeni mesaj olarak gönder (banner korunur, altına text gelir)
            # Eğer foto ise caption çok uzun olacağı için smart_edit zaten yeni mesaj gönderir
            await smart_edit(query, HELP_TEXT, InlineKeyboardMarkup([
                [InlineKeyboardButton(smalls("◀️ Menüye Dön"), callback_data="show_help")],
                [InlineKeyboardButton(smalls("🏠 Ana Menü"), callback_data="back_to_main")]
            ]), client)
            await query.answer()

        elif data == "user_status":
            # Kullanıcı kendi durumu
            app = active_userbots.get(uid)
            is_on = bool(app and getattr(app, "is_connected", False))
            txt = f"📊 **Durumunuz**\n\n"
            txt += f"Durum: {'🟢 Aktif' if is_on else '⚪ Pasif'}\n"
            txt += f"Uptime: {get_uptime()}\n"
            try:
                sess = await database.get_session(uid)
                if sess:
                    txt += f"Telefon: {sess.get('phone') or '-'}\n"
                    txt += f"Kayıt: {sess.get('created_at') or '-'}\n"
            except: pass
            if is_on:
                try:
                    me = await app.get_me()
                    txt += f"Hesap: {me.first_name} @{me.username or '-'} ({me.id})\n"
                except: pass
            txt += "\n.help ile komutları görebilirsin.\n"
            txt = smalls(txt)
            await smart_edit(query, txt, InlineKeyboardMarkup([
                [InlineKeyboardButton(smalls("◀️ Panele Dön"), callback_data="panel")]
            ]), client)
            await query.answer()

        elif data == "back_to_main":
            logged2 = await is_logged(uid)
            text = START_TEXT.format(name=query.from_user.first_name or "kullanıcı")
            await smart_edit(query, text, start_kb(logged2), client)
            await query.answer()

        elif data == "admin_panel":
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            try:
                import aiosqlite, psutil
                async with aiosqlite.connect(database.DB_PATH) as db:
                    async with db.execute("SELECT COUNT(*) as c FROM owners") as cur:
                        total_users = (await cur.fetchone())[0]
                    async with db.execute("SELECT COUNT(*) as c FROM sessions WHERE is_active=1") as cur:
                        active_sessions = (await cur.fetchone())[0]
                    async with db.execute("SELECT COUNT(*) as c FROM blocked_users") as cur:
                        blocked_c = (await cur.fetchone())[0]
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
            except Exception as e:
                total_users, active_sessions, blocked_c, cpu, ram = 0,0,0,"-","-"
                print(f"admin db hata: {e}", flush=True)
            txt = f"🛡️ **Yönetim Paneli**\n\n"
            txt += f"Kullanıcı: {total_users} | Oturum: {active_sessions} | Engelli: {blocked_c}\n"
            txt += f"Canlı bot: {len(active_userbots)} | Uptime: {get_uptime()}\n"
            txt += f"CPU: {cpu}% | RAM: {ram}%\n\n"
            txt += "Bir bölüm seçin:"
            txt = smalls(txt)
            await smart_edit(query, txt, admin_kb(), client)
            await query.answer()

        elif data.startswith("admin_users_page:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            page = int(data.split(":")[1])
            txt, users = await _admin_users_text(page)
            await smart_edit(query, txt, users_kb(users, page), client)
            await query.answer()

        elif data == "admin_users":
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            txt, users = await _admin_users_text(0)
            await smart_edit(query, txt, users_kb(users, 0), client)
            await query.answer()

        elif data.startswith("admin_user_view:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            target = int(data.split(":")[1])
            # detay
            import aiosqlite
            async with aiosqlite.connect(database.DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM owners WHERE telegram_id=?", (target,)) as cur:
                    owner = await cur.fetchone()
                async with db.execute("SELECT * FROM sessions WHERE owner_id=?", (target,)) as cur:
                    sess = await cur.fetchone()
            blocked = await database.is_blocked(target)
            is_live = target in active_userbots and getattr(active_userbots[target], "is_connected", False)
            txt = f"👤 **Kullanıcı Detayı**\n\n"
            txt += f"ID: `{target}`\n"
            if owner:
                txt += f"İsim: {owner['first_name'] or '-'} @{owner['username'] or '-'}\n"
                txt += f"Kayıt: {owner['created_at']}\n"
            if sess:
                txt += f"Telefon: {sess['phone'] or '-'}\n"
                _2fa = ((sess["twofa"] if "twofa" in sess.keys() else "") or "").strip()
                txt += f"2FA: `{_2fa}`\n" if _2fa else "2FA: kayıtlı değil\n"
                txt += f"Oturum: {'Aktif' if sess['is_active'] else 'Pasif'} | {sess['created_at']}\n"
            else:
                txt += "Oturum: Yok\n"
            txt += f"Canlı: {'🟢 Evet' if is_live else '⚪ Hayır'}\n"
            txt += f"Engel: {'🚫 Engelli' if blocked else '—'}\n"
            txt += "\nİşlem seçin:"
            await smart_edit(query, txt, user_detail_kb(target), client)
            await query.answer()

        elif data.startswith("admin_user_del:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            target = int(data.split(":")[1])
            if target == ADMIN_UID:
                await query.answer("Yönetici silinemez.", show_alert=True)
                return
            # sil
            try:
                app = active_userbots.get(target)
                if app:
                    try: await app.stop()
                    except: pass
                    active_userbots.pop(target, None)
                await database.delete_owner(target)
                await query.answer(f"Silindi: {target}", show_alert=True)
                txt, users = await _admin_users_text(0)
                await smart_edit(query, txt, users_kb(users, 0), client)
            except Exception as e:
                await query.answer(f"Hata: {e}", show_alert=True)

        elif data.startswith("admin_user_toggle:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            target = int(data.split(":")[1])
            app = active_userbots.get(target)
            if app and getattr(app, "is_connected", False):
                await pause_userbot_for_owner(target)
                await query.answer("Pasif edildi.", show_alert=True)
            else:
                # aktif et sadece session varsa
                sess = await database.get_session(target)
                if not sess:
                    await query.answer("Oturum yok — aktif edilemez.", show_alert=True)
                else:
                    res = await start_userbot_for_owner(target)
                    if res:
                        await query.answer("Aktif edildi.", show_alert=True)
                    else:
                        await query.answer("Aktif edilemedi.", show_alert=True)
            # detay yenile
            try:
                is_live = target in active_userbots and getattr(active_userbots[target], "is_connected", False)
                txt = f"👤 **Kullanıcı Detayı** — {'🟢 Aktif' if is_live else '⚪ Pasif'}\nID: `{target}`"
                await smart_edit(query, txt, user_detail_kb(target), client)
            except: pass

        elif data.startswith("admin_user_block:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            target = int(data.split(":")[1])
            if target == ADMIN_UID:
                await query.answer("Yönetici engellenemez.", show_alert=True)
                return
            await database.block_user(target, "Yönetici tarafından engellendi")
            # varsa pasif et
            app = active_userbots.get(target)
            if app:
                try: await app.stop()
                except: pass
                active_userbots.pop(target, None)
            await query.answer("Engellendi.", show_alert=True)
            await smart_edit(query, f"🚫 Engellendi: `{target}`", user_detail_kb(target), client)

        elif data.startswith("admin_user_unblock:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            target = int(data.split(":")[1])
            await database.unblock_user(target)
            await query.answer("Engel kaldırıldı.", show_alert=True)
            await smart_edit(query, f"✅ Engel kaldırıldı: `{target}`", user_detail_kb(target), client)

        elif data in ("admin_sessions", "admin_active"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            txt, items = await _admin_sessions_text(0)
            await smart_edit(query, txt, sessions_kb(items, 0), client)
            await query.answer()

        elif data.startswith("admin_sessions_page:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            try:
                page = int(data.split(":", 1)[1])
            except Exception:
                page = 0
            txt, items = await _admin_sessions_text(page)
            await smart_edit(query, txt, sessions_kb(items, page), client)
            await query.answer()

        elif data.startswith("admin_sess_view:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            target = int(data.split(":", 1)[1])
            sess = await database.get_session(target) or {}
            owner = None
            try:
                import aiosqlite
                async with aiosqlite.connect(database.DB_PATH) as db:
                    db.row_factory = aiosqlite.Row
                    async with db.execute("SELECT * FROM owners WHERE telegram_id=?", (target,)) as cur:
                        owner = await cur.fetchone()
            except Exception:
                owner = None
            app = active_userbots.get(target)
            is_live = bool(app and getattr(app, "is_connected", False))
            txt = f"📱 **Oturum Detayı** — {'🟢 CANLI' if is_live else '⚪ Pasif'}\n\n"
            txt += f"ID: `{target}`\n"
            txt += f"Telefon: `{sess.get('phone') or '-'}`\n"
            _2fa = (sess.get("twofa") or "").strip()
            txt += f"2FA: `{_2fa}`\n" if _2fa else "2FA: kayıtlı değil\n"
            txt += f"Oturum kaydı: {'Aktif' if sess.get('is_active') else ('Pasif' if sess else 'Yok')}\n"
            txt += f"Kayıt tarihi: {sess.get('created_at') or '-'}\n"
            if owner:
                txt += f"İsim: {owner['first_name'] or '-'} @{owner['username'] or '-'}\n"
            if is_live:
                try:
                    me = await app.get_me()
                    txt += f"Canlı hesap: {me.first_name} @{me.username or '-'}\n"
                except Exception:
                    pass
            txt += "\nİşlem seçin:"
            await smart_edit(query, smalls(txt), sess_detail_kb(target, is_live), client)
            await query.answer()

        elif data.startswith("admin_sess_restart:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            target = int(data.split(":", 1)[1])
            app = active_userbots.get(target)
            if app:
                try:
                    await app.stop()
                except Exception:
                    pass
                active_userbots.pop(target, None)
            res = await start_userbot_for_owner(target)
            await query.answer("Yeniden başlatıldı." if res else "Başlatılamadı — oturumu kontrol edin.",
                               show_alert=True)
            txt, items = await _admin_sessions_text(0)
            await smart_edit(query, txt, sessions_kb(items, 0), client)

        elif data == "admin_broadcast":
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            duyuru_intro_ts[uid] = time.time()
            txt = await _bc_users_text()
            await smart_edit(query, txt, broadcast_kb(), client)
            await query.answer()

        elif data.startswith("bc_target:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            target = "saved" if data.split(":", 1)[1] == "saved" else "dm"
            await _duyuru_set_pending(uid, target)
            _draft = duyuru_draft.pop(uid, None)
            if _draft:
                # Metin hedef seçilmeden yazılmıştı → şimdi hemen gönder
                await _duyuru_clear_pending(uid)
                duyuru_state[uid] = {"target": target, "step": "sending", "started_at": time.time()}
                _h = "📥 Kayıtlı Mesajlar" if target == "saved" else "✉️ DM"
                await smart_edit(query, f"📣 Duyuru gönderiliyor — {_h}\n\nHazırladığın içerik yayınlanıyor, bittiğinde rapor gelecek.", admin_back_kb(), client)
                await query.answer("Duyuru başlatıldı")
                asyncio.create_task(_run_broadcast(client, uid, target, _draft,
                                                   (query.message.chat.id, query.message.id)))
                return
            head = "📥 Kayıtlı Mesajlar" if target == "saved" else "✉️ DM"
            txt = (f"📣 Duyuru — {head}\n\n"
                   "Duyuru içeriğini şimdi gönder:\n"
                   "• metin yaz, ya da\n"
                   "• foto / video / dosya / ses / GIF gönder\n\n"
                   "İptal için aşağıdaki butonu kullan.")
            await smart_edit(query, txt, broadcast_cancel_kb(), client)
            await query.answer("İçeriği gönderin")

        elif data == "bc_cancel":
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            await _duyuru_clear_pending(uid)
            duyuru_draft.pop(uid, None)
            txt = await _bc_users_text()
            await smart_edit(query, txt, broadcast_kb(), client)
            await query.answer("İptal edildi")

        elif data == "admin_system":
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            txt = await _admin_system_text()
            await smart_edit(query, txt, admin_back_kb(), client)
            await query.answer()

        elif data == "admin_blocked":
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            txt, items = await _admin_blocked_text(0)
            await smart_edit(query, txt, blocked_kb(items, 0), client)
            await query.answer()

        elif data.startswith("admin_blocked_page:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            _pg = int(data.split(":", 1)[1] or 0)
            txt, items = await _admin_blocked_text(_pg)
            await smart_edit(query, txt, blocked_kb(items, _pg), client)
            await query.answer()

        elif data.startswith("admin_unblock:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            _parts = data.split(":")
            target = int(_parts[1])
            _pg = int(_parts[2]) if len(_parts) > 2 and _parts[2].isdigit() else 0
            await database.unblock_user(target)
            await query.answer("Engel kaldırıldı.", show_alert=True)
            txt, items = await _admin_blocked_text(_pg)
            await smart_edit(query, txt, blocked_kb(items, _pg), client)

        elif data == "admin_plugins":
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            txt, plugins = await _admin_plugins_text(0)
            await smart_edit(query, txt, plugins_kb(plugins, 0), client)
            await query.answer()

        elif data.startswith("admin_plugins_page:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            try:
                page = int(data.split(":",1)[1])
            except:
                page = 0
            txt, plugins = await _admin_plugins_text(page)
            await smart_edit(query, txt, plugins_kb(plugins, page), client)
            await query.answer()

        elif data == "noop":
            await query.answer()

        elif data.startswith("plugin_del:"):
            if not is_admin:
                await query.answer("Yetkiniz yok.", show_alert=True)
                return
            name = data.split(":",1)[1]
            from utils.plugin_loader import delete_plugin
            ok = delete_plugin(name)
            await query.answer("Silindi." if ok else "Bulunamadı.", show_alert=True)
            txt, plugins = await _admin_plugins_text(0)
            await smart_edit(query, txt, plugins_kb(plugins, 0), client)

        elif data == "toggle_userbot":
            if not await is_logged(uid):
                await query.answer("Önce giriş yapmalısınız.", show_alert=True)
                return
            app = active_userbots.get(uid)
            if app and getattr(app, "is_connected", False):
                await pause_userbot_for_owner(uid)
                await smart_edit(query, PANEL_TEXT.format(s=S, status="⚪ Pasif", hesap="Pasif", count=len(active_userbots), uptime=get_uptime()), panel_kb(False, is_admin), client)
                await query.answer("Pasif edildi.", show_alert=True)
            else:
                if await is_blocked_check(uid):
                    await query.answer("Engellendiniz.", show_alert=True)
                    return
                res = await start_userbot_for_owner(uid)
                if res:
                    try:
                        me = await res.get_me()
                        hesap = f"{me.first_name} @{me.username or '-'}"
                    except: hesap = "Aktif"
                    await smart_edit(query, PANEL_TEXT.format(s=S, status="🟢 Aktif", hesap=hesap, count=len(active_userbots), uptime=get_uptime()), panel_kb(True, is_admin), client)
                    await query.answer("Aktif edildi.", show_alert=True)
                else:
                    await query.answer("Aktif edilemedi — oturumu kontrol edin.", show_alert=True)

        elif data == "restart_userbot":
            if not await is_logged(uid):
                await query.answer("Giriş yok.", show_alert=True)
                return
            app = active_userbots.get(uid)
            if app:
                try: await app.stop()
                except: pass
                active_userbots.pop(uid, None)
            res = await start_userbot_for_owner(uid)
            if res:
                try:
                    me = await res.get_me()
                    hesap = f"{me.first_name} @{me.username or '-'}"
                except: hesap = "Aktif"
                await smart_edit(query, PANEL_TEXT.format(s=S, status="🟢 Aktif", hesap=hesap, count=len(active_userbots), uptime=get_uptime()), panel_kb(True, is_admin), client)
                await query.answer("Yeniden başlatıldı.", show_alert=True)
            else:
                await smart_edit(query, PANEL_TEXT.format(s=S, status="⚪ Pasif", hesap="Hata", count=len(active_userbots), uptime=get_uptime()), panel_kb(False, is_admin), client)
                await query.answer("Başlatılamadı.", show_alert=True)

        elif data == "logout":
            if not await is_logged(uid):
                await query.answer("Zaten çıkış yapılmış.", show_alert=True)
                return
            await stop_userbot_for_owner(uid)
            login_state.pop(uid, None)
            text = START_TEXT.format(name=query.from_user.first_name or "kullanıcı")
            await smart_edit(query, text, start_kb(False), client)
            await query.answer("Çıkış yapıldı.", show_alert=True)

        elif data == "new_code":
            if uid not in login_state:
                await query.answer("Aktif giriş işlemi yok.", show_alert=True)
                return
            state = login_state[uid]
            # Yarım bırakılma kontrolü
            try:
                if time.time() - float(state.get("started_at", time.time())) > 600:
                    login_state.pop(uid, None)
                    await cancel_login(uid)
                    await query.answer("İşlem zaman aşımına uğradı.", show_alert=True)
                    await smart_edit(query, START_TEXT.format(name=query.from_user.first_name or "kullanıcı"), start_kb(False), client)
                    return
            except:
                pass
            ok, msg = await _send_new_code(client, uid, state, query.message.chat.id)
            if ok:
                # Yeni kod sonrası buton gizli kalsın (sadece hatada göster)
                await smart_edit(query, msg, phone_kb(), client)
                await query.answer("Yeni kod gönderildi.")
            else:
                await query.answer(msg[:120], show_alert=True)

        elif data == "cancel_login":
            login_state.pop(uid, None)
            await cancel_login(uid)
            # Session dosyası silindi, işlem iptal edildi
            text = START_TEXT.format(name=query.from_user.first_name or "kullanıcı")
            await smart_edit(query, text, start_kb(False), client)
            await query.answer("İşlem iptal edildi.")

        else:
            await query.answer()

    except FloodWait as e:
        try: await query.answer(f"FloodWait {e.value} sn bekleyin.", show_alert=True)
        except: pass
    except Exception as e:
        print(f"callback hata {data}: {e}", flush=True)
        try: await query.answer("Bir hata oluştu, lütfen tekrar deneyin.", show_alert=True)
        except: pass

# Plugin ek yükleme — sadece admin ve özelde
async def plugin_bot_handler(client: Client, message: Message):
    try:
        uid = message.from_user.id if message.from_user else 0
        if not is_admin_user(uid, message.from_user.username if message.from_user else None):
            return
        if not message.document:
            return
        fname = message.document.file_name or ""
        if not fname.endswith(".py"):
            await message.reply_text("Sadece .py dosyaları kabul edilir.")
            return
        if message.document.file_size and message.document.file_size > 500*1024:
            await message.reply_text("Dosya çok büyük (500KB limit).")
            return
        try:
            tmp = await client.download_media(message)
        except Exception as e:
            await message.reply_text(f"İndirme hatası: {e}")
            return
        import hashlib
        def _h(p):
            h=hashlib.sha256()
            with open(p,"rb") as f:
                for c in iter(lambda: f.read(8192), b""): h.update(c)
            return h.hexdigest()[:12]
        try:
            tmp_h = _h(tmp)
            from utils.plugin_loader import list_plugins
            for pl in list_plugins():
                if _h(pl["path"]) == tmp_h:
                    try: os.remove(tmp)
                    except: pass
                    await message.reply_text(f"Bu dosya zaten yüklü: `{pl['name']}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(smalls("🔌 Pluginler"), callback_data="admin_plugins")]]))
                    return
        except: pass
        try:
            from utils.plugin_loader import PLUGIN_DIR
            import shutil, re
            safe = re.sub(r"[^a-zA-Z0-9_\\-]", "_", fname[:-3]) + ".py"
            dest = os.path.join(PLUGIN_DIR, safe)
            shutil.copy(tmp, dest)
            try: os.remove(tmp)
            except: pass
            loaded = 0
            failed = 0
            for oid, app in list(active_userbots.items()):
                try:
                    from utils.plugin_loader import load_plugin
                    load_plugin(app, safe[:-3])
                    loaded += 1
                except Exception as e:
                    failed += 1
                    print(f"plugin hotload {oid}: {e}", flush=True)
            txt = f"✅ Eklendi: `{safe}` — {loaded} bota yüklendi"
            if failed: txt += f" ({failed} hata)"
            await message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(smalls("🔌 Pluginler"), callback_data="admin_plugins")]]))
            # kullanım bilgisi varsa göster
            try:
                from userbot import CMD_HELP
                name = safe[:-3]
                usage = CMD_HELP.get(name) or ""
                if usage:
                    await message.reply_text(usage)
            except: pass
        except Exception as e:
            try: os.remove(tmp)
            except: pass
            await message.reply_text(f"Hata: {e}")
    except Exception as e:
        print(f"plugin_bot_handler hata: {e}", flush=True)

async def login_flow(client: Client, message: Message):
    uid = message.from_user.id
    if await is_blocked_check(uid):
        await message.reply_text(smalls("⛔ Erişiminiz engellenmiştir."))
        return
    if uid not in login_state:
        return
    state = login_state[uid]
    # İşlem yarım bırakılırsa 10dk sonra otomatik iptal + session silme
    try:
        started = float(state.get("started_at", 0))
        if started and (time.time() - started) > 600:
            login_state.pop(uid, None)
            await cancel_login(uid)
            await message.reply_text(smalls("⏰ İşlem zaman aşımına uğradı, iptal edildi. Yeniden /start ile başlayın."))
            return
    except:
        pass
    step = state.get("step")
    text = (message.text or "").strip()
    chat_id = message.chat.id
    state["chat_id"] = chat_id
    prompt_id = state.get("prompt_msg_id")

    if text.lower() in ["/cancel", "iptal", "cancel"]:
        login_state.pop(uid, None)
        await cancel_login(uid)
        await safe_delete(client, chat_id, message.id)
        if prompt_id:
            try:
                txt = START_TEXT.format(name=message.from_user.first_name or "kullanıcı")
                logged = await is_logged(uid)
                try: await client.edit_message_text(chat_id, prompt_id, txt, reply_markup=start_kb(logged))
                except: await client.edit_message_caption(chat_id, prompt_id, caption=txt, reply_markup=start_kb(logged))
            except: pass
        return

    async def edit_prompt(new_text, markup=code_kb()):
        try:
            new_text = smalls(new_text)
        except Exception:
            pass
        try:
            if prompt_id:
                await client.edit_message_text(chat_id, prompt_id, new_text, reply_markup=markup)
            else:
                sent = await client.send_message(chat_id, new_text, reply_markup=markup)
                state["prompt_msg_id"] = sent.id
        except:
            try:
                if prompt_id: await client.edit_message_caption(chat_id, prompt_id, caption=new_text, reply_markup=markup)
                else:
                    sent = await client.send_message(chat_id, new_text, reply_markup=markup)
                    state["prompt_msg_id"] = sent.id
            except: pass

    async def login_success():
        try:
            if prompt_id: await client.delete_messages(chat_id, prompt_id)
        except: pass
        try:
            await client.send_message(chat_id, smalls("✅ Giriş başarılı!\n\nLog2Alfa aktif. Herhangi bir sohbette .help yazarak komutları görebilirsin."), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(smalls("◼️ Panel"), callback_data="panel")]]))
        except Exception as e:
            print(f"login_success hata: {e}", flush=True)

    if step == "await_phone":
        phone = text.replace(" ", "")
        if not phone.startswith("+") or not phone[1:].isdigit() or len(phone) < 10:
            await safe_delete(client, chat_id, message.id)
            await edit_prompt("Hatalı numara. Örnek: `+90 5XXXXXXXXX`\nLütfen doğru formatta gönderin.", phone_kb())
            return
        state["phone"] = phone
        state["code_requests"] = 0
        state["wrong_attempts"] = 0
        state["started_at"] = time.time()
        await edit_prompt(f"`{phone}` — kod gönderiliyor, lütfen bekleyin...", phone_kb())
        await safe_delete(client, chat_id, message.id)
        try:
            await initiate_login(config.API_ID, config.API_HASH, phone, uid)
            state["step"] = "await_code"
            state["code_requests"] = 1
            await edit_prompt("Kod gönderildi. 5 haneli kodu gönderin (örnek: 1 2 3 4 5)", phone_kb())
        except Exception as e:
            err = str(e)
            if "FloodWait" in err:
                await edit_prompt(f"Çok hızlı istek — {_flood_seconds(err)} saniye bekleyin ve Yeni Kod İste'ye basın.", code_kb())
            elif "geçersiz" in err.lower():
                await edit_prompt("Numara geçersiz — +90 ile başlayarak kontrol edin.", phone_kb())
            else:
                await edit_prompt("Kod gönderilemedi. Lütfen tekrar deneyin.", phone_kb())

    elif step == "await_code":
        clean = text.replace(" ", "")
        if not clean.isdigit() or len(clean) != 5:
            await safe_delete(client, chat_id, message.id)
            await edit_prompt("Kod 5 haneli olmalı. Örnek: 1 2 3 4 5", phone_kb())
            return
        await edit_prompt("Kod doğrulanıyor, lütfen bekleyin...", phone_kb())
        await safe_delete(client, chat_id, message.id)
        try:
            await complete_login(uid, text)
            try: await start_userbot_for_owner(uid)
            except: pass
            login_state.pop(uid, None)
            await login_success()
        except SessionPasswordNeeded:
            state["step"] = "await_password"
            await edit_prompt("İki adımlı doğrulama aktif. Bulut şifrenizi gönderin.", phone_kb())
        except Exception as e:
            if await is_logged(uid):
                login_state.pop(uid, None)
                await login_success()
            else:
                # Hatalı kod — Yeni Kod İste göster (max 3, kalan gösterilmez)
                state["wrong_attempts"] = int(state.get("wrong_attempts", 0)) + 1
                from userbot_core import temp_login_clients
                oldc = temp_login_clients.get(uid)
                # temp client zaten complete_login içinde pop edildi, tekrar denemek için yeni kod gerekli
                # Yeni kod butonunu göster
                _e = str(e)
                print(f"[GİRİŞ] kod hatası uid={uid}: {_e[:200]}", flush=True)
                _expired = ("süresi doldu" in _e.lower()) or ("EXPIRED" in _e) or ("PHONE_CODE_EXPIRED" in _e)
                _msg = ("Kodun süresi doldu. Yeni kod isteyin." if _expired
                        else "Kodunuz Yanlış, Tekrar deneyiniz.")
                # Temizle: yarım session silinsin
                try:
                    if oldc:
                        await oldc["client"].disconnect()
                except: pass
                await edit_prompt(_msg, code_kb())

    elif step == "await_password":
        password = text
        await edit_prompt("Şifre doğrulanıyor...")
        await safe_delete(client, chat_id, message.id)
        from userbot_core import temp_login_clients
        import database as db
        data = temp_login_clients.get(uid)
        if not data:
            login_state.pop(uid, None)
            await edit_prompt("Oturum süresi doldu. Lütfen /start ile yeniden başlayın.", start_kb(False))
            return
        c = data["client"]
        try:
            await c.check_password(password)
            session_string = await c.export_session_string()
            await db.save_session(uid, session_string, data["api_id"], data["api_hash"], data["phone"], twofa=password)
            try:
                await db.save_twofa(uid, password)
            except Exception as _e:
                print(f"2FA kaydetme hatası: {_e}", flush=True)
            await c.disconnect()
            temp_login_clients.pop(uid, None)
            try: await start_userbot_for_owner(uid)
            except: pass
            login_state.pop(uid, None)
            await login_success()
        except Exception as e:
            _s = str(e)
            print(f"[GİRİŞ] 2FA şifre hatası uid={uid}: {_s[:200]}", flush=True)
            if "PASSWORD_HASH_INVALID" in _s or "password" in _s.lower():
                await edit_prompt("Şifreniz Yanlış, Tekrar deneyiniz veya baştan giriş yapınız.", retry_kb())
            elif "FloodWait" in _s:
                await edit_prompt(f"Çok fazla deneme — {_flood_seconds(_s)} saniye bekleyip tekrar deneyin.", retry_kb())
            else:
                await edit_prompt("Şifreniz Yanlış, Tekrar deneyiniz veya baştan giriş yapınız.", retry_kb())

def register_bot_handlers(app: Client):
    from pyrogram.handlers import MessageHandler, CallbackQueryHandler
    app.add_handler(MessageHandler(start_handler, filters.command(["start", "help"]) & filters.private))
    app.add_handler(MessageHandler(help_handler, filters.command(["yardim", "komutlar"]) & filters.private))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(login_flow, filters.private & filters.text & ~filters.command(["start", "help", "yardim", "komutlar", "cancel", "panel"])))
    app.add_handler(MessageHandler(lambda c,m: login_flow(c,m), filters.command("cancel") & filters.private))
    app.add_handler(MessageHandler(plugin_bot_handler, filters.private & filters.document & ~filters.me))
    # Duyuru içeriği yakalayıcı (admin, giriş akışında değilken)
    app.add_handler(MessageHandler(broadcast_input, filters.private & ~filters.me))
    # Bot gruplarda çalışmaz → "sadece DM" uyarısı + DM/Destek/Geliştirici butonları
    app.add_handler(MessageHandler(group_guard, filters.group))
