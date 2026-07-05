"""
Initialise database and define tables, manages connections
"""
import config
import sqlite3
from contextlib import contextmanager

# SQLite commands to create tables
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password      TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    amount        TEXT NOT NULL,
    type          TEXT NOT NULL,
    category      TEXT NOT NULL,
    note          TEXT NOT NULL DEFAULT '',
    date          TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

def get_connection() -> sqlite3.Connection:
    # Connect to database file (or create it)
    conn = sqlite3.connect(config.db_path())
    conn.row_factory = sqlite3.Row
    # Enable the enforcement of SQLite foreign key constraint
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# Auto release the resource
@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)
