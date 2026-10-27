# Yönetim Paneli — Yeni Düzen (2026-09-23)

Deploy: **b87d88ea-26b1-45f9-9404-107ac7186c48** (SUCCESS 08:21:56 UTC)

## Yapılan değişiklikler (bot_controller.py)

| Bölüm | Önce | Sonra |
|---|---|---|
| 👥 Kullanıcılar (`users_kb`) | 8/sayfa, tek sütun | **2 yan yana × 5 satır = 10/sayfa** + ◀️ Geri / x/y / İleri ▶️ |
| 📱 Oturumlar & 🤖 Aktif Botlar | 2 ayrı buton/sayfa | **TEK sayfa** (`_admin_sessions_text` + `sessions_kb`), aynı 2×5 grid + sayfalama |
| Oturum detayı | yok | Yeni `sess_detail_kb`: ⏸️ pasif et · 🔄 yeniden başlat · 👤 kullanıcı detayı · 🗑️ sil |
| Ana menü | Oturumlar ve Aktif Botlar ayrı | `📱 Oturumlar & Botlar` tek buton |

Sıralama: **canlı botlar önce**, sonra kayıtlı oturumlar. Durum ikonları: 🟢 CANLI / 🟡 aktif-oturum / ⚪ pasif.

## Callback adları

- Mevcut: `admin_users`, `admin_user_view:`, `admin_user_del:`, `admin_user_toggle:`, `admin_user_block:`, `admin_user_unblock:`, `admin_blocked`, `admin_unblock:`, `admin_plugins`, `admin_plugins_page:`, `plugin_del:`, `restart_userbot`
- Yeni: `admin_users_page:<n>`, `admin_sessions_page:<n>`, `admin_sess_view:<uid>`, `admin_sess_restart:<uid>`
- `admin_active` geriye dönük uyumluluk için duruyor (eski mesajlardaki buton çalışsın diye).

## Doğrulama (konteynerde çalıştırıldı)

- `tests/panel_test.py` → 10/sayfa grid, 5 satır sınırı, boş liste, detay klavyeleri: **hepsi geçti**
- `tests/panel_callback_test.py` → 12/12 callback edit üretti (admin_panel, users, users_page, user_view, sessions, sessions_page, sess_view, blocked, system, plugins, plugins_page, panel)
- Canlı veri: 5 kullanıcı, 4 oturum (hepsi aktif kv). Loglarda hata yok: "✅ 4 userbot aktif", 134 plugin, watchdog OK.

## Nasıl test edilir

Bot'a `/start` → 🛡️ Yönetim Paneli → 👥 Kullanıcılar / 📱 Oturumlar & Botlar → kart/dokun ve ◀️ ▶️ ile sayfa gez.
