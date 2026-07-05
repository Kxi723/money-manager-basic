"""
Fill the database with demo users and transactions
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

logger = logging.getLogger("seed.py")

import config
import security
from db import db, init_db

# Pre-set data for seeding the database
USERS = [
    ("jason", "password"),
    ("test", "admin"),
]

# (username, amount, type, category, note, date)
TRANSACTIONS = [
    ("jason", 40.30, "expense", "Utilities", "Umobile", "2026-07-01"),
    ("jason", 14.70, "expense", "Restaurant", "Lunch", "2026-07-01"),
    ("jason", 10.00, "expense", "Restaurant", "Lunch", "2026-07-02"),
    ("jason", 9.20, "expense", "Restaurant", "Lunch", "2026-07-03"),
    ("jason", 21.61, "expense", "Transport", "Fuel", "2026-07-03"),
    ("jason", 12.40, "expense", "Restaurant", "Lunch", "2026-07-04"),
    ("jason", 5.00, "expense", "Restaurant", "Dinner", "2026-07-04"),
    ("jason", 9.90, "expense", "Restaurant", "Lunch", "2026-07-05"),
    ("jason", 12.40, "expense", "Restaurant", "Dinner", "2026-07-05"),
    ("jason", 10.00, "expense", "Restaurant", "Lunch", "2026-07-06"),
    ("jason", 9.80, "expense", "Restaurant", "Lunch", "2026-07-07"),
    ("jason", 900.00, "income", "Allowance", "Tiong Nam", "2026-07-07"),
    ("test", 900.00, "income", "Allowance", "Tiong Nam", "2026-07-07"),
]


def seed() -> None:
    init_db()
    with db() as conn:
        # Reset db
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM users")
        user = {}

        # Insert users into db
        for username, password in USERS:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",(
                    username, 
                    security.hash_password(password)
                ),
            )

            # Get user id
            user[username] = conn.execute("SELECT id FROM users WHERE username = ?",
                (username,)).fetchone()["id"]

        # Insert transactions into db
        for username, amount, ttype, category, note, tdate in TRANSACTIONS:
            conn.execute(
                "INSERT INTO transactions (user_id, amount, type, category, note, date) VALUES (?, ?, ?, ?, ?, ?)",(
                    user[username],
                    security.encrypt_field(str(amount)),
                    ttype,
                    category,
                    security.encrypt_field(note),
                    tdate,
                ),
            )

    logger.info(f"Data seeded in {config.db_path()}")


def ensure_seeded() -> None:
    """
    If no user detected in current mode, seed the database.
    It's safe to call on startup and on every mode switch.
    """
    init_db()
    with db() as conn:
        has_users = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    if not has_users:
        seed()


if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging()
    seed()
