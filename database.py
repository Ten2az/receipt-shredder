"""
database.py — SQLite schema + encrypted field helpers
======================================================
Uses SQLite for zero-cost MVP storage.
Sensitive fields (vendor names, line items) are Fernet-encrypted at rest.

Swap to PostgreSQL later:
  pip install psycopg2-binary
  Change DATABASE_URL to postgresql://user:pass@host/db
  SQLAlchemy handles the rest automatically.
"""

import os
import sqlite3
from cryptography.fernet import Fernet

# ── Encryption ────────────────────────────────────────────────────────────────
# Generate once: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Store in .env as FERNET_KEY
_raw_key = os.getenv("FERNET_KEY", Fernet.generate_key().decode())
_cipher   = Fernet(_raw_key.encode() if isinstance(_raw_key, str) else _raw_key)

def encrypt(text: str) -> str:
    """Encrypt a string before writing to DB."""
    if not text:
        return text
    return _cipher.encrypt(text.encode()).decode()

def decrypt(token: str) -> str:
    """Decrypt a string after reading from DB."""
    if not token:
        return token
    try:
        return _cipher.decrypt(token.encode()).decode()
    except Exception:
        return token  # Fallback: return raw if already plaintext (migration safety)

# ── Database path ─────────────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "receipt_shredder.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows dict-like access: row["field"]
    return conn

# ── Schema ────────────────────────────────────────────────────────────────────
def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    conn = get_conn()
    c = conn.cursor()

    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT    UNIQUE NOT NULL,
            password_hash TEXT,
            google_id   TEXT,
            is_premium  BOOLEAN DEFAULT 0,
            stripe_customer_id TEXT,
            profile     TEXT,   -- JSON blob: {state, user_type, categories}
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Receipts table — vendor/items encrypted, amounts stored plaintext for aggregation
    c.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            upload_date     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            receipt_date    TEXT,       -- YYYY-MM-DD from receipt
            vendor_enc      TEXT,       -- encrypted vendor name
            total           REAL,       -- unencrypted for SUM queries
            tax_amount      REAL,
            items_enc       TEXT,       -- encrypted JSON line items
            category        TEXT,       -- e.g. "Food", "Office Supplies"
            subcategory     TEXT,
            is_deductible   BOOLEAN DEFAULT 0,
            deductible_type TEXT,       -- e.g. "Home Office", "Business Meal"
            state_flags     TEXT,       -- JSON: state-specific deduction notes
            confidence      REAL,       -- 0-1 extraction confidence
            needs_review    BOOLEAN DEFAULT 0,  -- flagged for user review
            image_path      TEXT,       -- local path (deleted after processing in privacy mode)
            raw_text_enc    TEXT,       -- encrypted OCR text
            user_feedback   INTEGER,    -- 1=correct, -1=incorrect, 0=unreviewed
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    # AI feedback for personalization
    c.execute("""
        CREATE TABLE IF NOT EXISTS ai_feedback (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            receipt_id  INTEGER,
            original_category TEXT,
            corrected_category TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Cached monthly insights (avoid re-running Sonnet every page load)
    c.execute("""
        CREATE TABLE IF NOT EXISTS insight_cache (
            user_id     INTEGER NOT NULL,
            month       TEXT NOT NULL,  -- YYYY-MM
            insight_json TEXT,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, month)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized")
