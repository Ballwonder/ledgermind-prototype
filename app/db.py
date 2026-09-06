
import sqlite3, json
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ledgermind.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    source_id TEXT UNIQUE,
    source TEXT,
    account_name TEXT,
    date TEXT,
    amount REAL,
    description TEXT,
    merchant TEXT,
    pending INTEGER DEFAULT 0,
    status TEXT DEFAULT 'new'
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    source TEXT,
    date TEXT,
    vendor TEXT,
    amount REAL,
    description TEXT,
    attachment_name TEXT,
    confidence REAL
);

CREATE TABLE IF NOT EXISTS decisions (
    transaction_id TEXT PRIMARY KEY,
    route TEXT,
    account TEXT,
    tax_category TEXT,
    confidence REAL,
    explanation TEXT,
    evidence_ids TEXT,
    missing_facts TEXT,
    journal TEXT,
    posted INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    external_id TEXT,
    encrypted_access_token TEXT,
    cursor TEXT,
    status TEXT DEFAULT 'connected',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL,
    prior_category TEXT,
    corrected_category TEXT NOT NULL,
    note TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT,
    payload TEXT
);
"""

def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with conn() as c:
        c.executescript(SCHEMA)

def audit(transaction_id, event_type, payload):
    with conn() as c:
        c.execute(
            "INSERT INTO audit_events(transaction_id,event_type,payload) VALUES (?,?,?)",
            (transaction_id, event_type, json.dumps(payload))
        )
