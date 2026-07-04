import sqlite3
from contextlib import contextmanager

DB_PATH = "bunt_bot.db"


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS alerted_situations (
                game_pk INTEGER,
                at_bat_index INTEGER,
                PRIMARY KEY (game_pk, at_bat_index)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)


def already_alerted(game_pk: int, at_bat_index) -> bool:
    with _conn() as c:
        return c.execute(
            "SELECT 1 FROM alerted_situations WHERE game_pk = ? AND at_bat_index = ?",
            (game_pk, at_bat_index),
        ).fetchone() is not None


def mark_alerted(game_pk: int, at_bat_index):
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO alerted_situations (game_pk, at_bat_index) VALUES (?, ?)",
            (game_pk, at_bat_index),
        )


def set_config(key: str, value: str):
    with _conn() as c:
        c.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_config(key: str):
    with _conn() as c:
        row = c.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None
