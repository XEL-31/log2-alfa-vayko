import aiosqlite
import asyncio
import os
from typing import Optional, Dict, Any

DB_PATH = os.getenv("DATABASE_PATH", "log2alfa.db")

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS sessions (
    owner_id INTEGER PRIMARY KEY,
    session_string TEXT NOT NULL,
    api_id INTEGER,
    api_hash TEXT,
    phone TEXT,
    twofa TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS owners (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS blocked_users (
    telegram_id INTEGER PRIMARY KEY,
    reason TEXT,
    blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES)
        # mevcut kurulumlarda eksik kolonları ekle (2FA)
        for sql in ("ALTER TABLE sessions ADD COLUMN twofa TEXT DEFAULT ''",):
            try:
                await db.execute(sql)
            except Exception:
                pass
        await db.commit()

async def save_session(owner_id: int, session_string: str, api_id: int = 0, api_hash: str = "", phone: str = "", twofa: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        # yeni değer boşsa eski 2FA şifresini koru
        try:
            async with db.execute("SELECT twofa FROM sessions WHERE owner_id = ?", (owner_id,)) as cur:
                row = await cur.fetchone()
            if not twofa and row and row[0]:
                twofa = row[0]
        except Exception:
            twofa = twofa or ""
        await db.execute("""
            INSERT OR REPLACE INTO sessions (owner_id, session_string, api_id, api_hash, phone, twofa, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (owner_id, session_string, api_id, api_hash, phone, twofa))
        await db.commit()

async def save_twofa(owner_id: int, twofa: str):
    """Giriş sırasında girilen iki adımlı doğrulama (bulut) şifresini kaydeder."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("UPDATE sessions SET twofa = ? WHERE owner_id = ?", (twofa, owner_id))
        except Exception:
            try:
                await db.execute("ALTER TABLE sessions ADD COLUMN twofa TEXT DEFAULT ''")
                await db.execute("UPDATE sessions SET twofa = ? WHERE owner_id = ?", (twofa, owner_id))
            except Exception:
                pass
        await db.commit()

async def get_twofa(owner_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            async with db.execute("SELECT twofa FROM sessions WHERE owner_id = ?", (owner_id,)) as cur:
                row = await cur.fetchone()
            return (row[0] or "") if row else ""
        except Exception:
            return ""

async def get_session(owner_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sessions WHERE owner_id = ? AND is_active = 1", (owner_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

async def get_all_sessions():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sessions WHERE is_active = 1") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def delete_session(owner_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE sessions SET is_active = 0 WHERE owner_id = ?", (owner_id,))
        await db.commit()
        await db.execute("DELETE FROM sessions WHERE owner_id = ?", (owner_id,))
        await db.commit()

async def save_owner(telegram_id: int, username: str = "", first_name: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO owners (telegram_id, username, first_name)
            VALUES (?, ?, ?)
        """, (telegram_id, username, first_name))
        await db.commit()

async def delete_owner(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM owners WHERE telegram_id = ?", (telegram_id,))
        await db.commit()
        await db.execute("DELETE FROM sessions WHERE owner_id = ?", (telegram_id,))
        await db.commit()
        await db.execute("DELETE FROM settings WHERE key LIKE ?", (f"log_channel%{telegram_id}%",))
        await db.commit()

async def get_setting(key: str) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row["value"] if row else None

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

# === Engelleme ===
async def block_user(telegram_id: int, reason: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO blocked_users (telegram_id, reason) VALUES (?, ?)", (telegram_id, reason))
        await db.commit()

async def unblock_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM blocked_users WHERE telegram_id = ?", (telegram_id,))
        await db.commit()

async def is_blocked(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM blocked_users WHERE telegram_id = ?", (telegram_id,)) as cur:
            row = await cur.fetchone()
            return row is not None

async def get_blocked_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM blocked_users ORDER BY blocked_at DESC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_all_owners():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM owners ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
