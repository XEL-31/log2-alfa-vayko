import os
from dotenv import load_dotenv

load_dotenv()

# Zorunlu
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")

# Opsiyonel
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)  # Botu sadece bu ID kullanabilir, 0 ise herkese açık ama giriş yapan kişi owner olur
SESSION_STRING = os.getenv("SESSION_STRING", "")
OWNER_NAME = os.getenv("OWNER_NAME", "vayko")
OWNER_URL = os.getenv("OWNER_URL", "https://t.me/vaykoo")
SUDO_USERS = os.getenv("SUDO_USERS", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "log2alfa.db")
WORKDIR = os.getenv("WORKDIR", "./sessions")

SUPPORT_CHAT_ID = os.getenv("SUPPORT_CHAT_ID", "")  # aktif mesajı gidecek chat @ veya -100...
LOG_CHANNEL = os.getenv("LOG_CHANNEL", "")  # alternatif

# AI (OpenRouter / DeepSeek) — kullanıcı anahtarı
OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    "",
)
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash-0731:free")
# eski groq (yedek, kullanılmıyor)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "")

# Bot Ayarları
BOT_PREFIX = "."
COMMANDS = [".log2alfa", ".alive", ".help", ".menu", ".ping", ".id", ".info", ".yaz", ".afk", ".hava"]

# Güvenlik
# Ban riski azaltma için FloodWait otomatik handle edilir, spam koruması vardır
FLOOD_SLEEP_THRESHOLD = 60  # FloodWait 60 saniyeden uzunsa bekle
MAX_CONCURRENT_TRANSMISSIONS = 2

def validate_config():
    errors = []
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN eksik! BotFather'dan al ve .env'e ekle")
    if not API_ID or API_ID == 0:
        errors.append("API_ID eksik! my.telegram.org'dan al")
    if not API_HASH:
        errors.append("API_HASH eksik! my.telegram.org'dan al")
    if errors:
        print("⚠️  Config Hataları:")
        for e in errors:
            print(f" - {e}")
        print("Not: Bot giriş akışı ile de API_ID/HASH girebilirsin, ama .env'de olması önerilir.")
    return len(errors) == 0
