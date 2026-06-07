import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("bot.database")


class Database:

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self) -> None:
        self._conn = self._connect()
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS guild_config (
                    guild_id         INTEGER PRIMARY KEY,
                    welcome_channel  INTEGER,
                    announce_channel INTEGER,
                    log_channel      INTEGER,
                    ticket_category  INTEGER,
                    staff_role       INTEGER,
                    welcome_message  TEXT DEFAULT 'Bienvenue {user_mention} sur **{server}** ! Vous etes le membre n {member_count}.',
                    goodbye_message  TEXT DEFAULT 'Au revoir **{user}**, nous etions {member_count} membres.'
                );

                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id   INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL UNIQUE,
                    creator_id INTEGER NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    closed_at  TEXT,
                    status     TEXT DEFAULT 'open'
                );

                CREATE TABLE IF NOT EXISTS ticket_transcripts (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL REFERENCES tickets(ticket_id),
                    content   TEXT NOT NULL,
                    saved_at  TEXT DEFAULT (datetime('now'))
                );
            """)
        logger.info(f"Base de donnees initialisee : {self.db_path}")

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._conn:
            return self._conn.execute(query, params)

    def fetchone(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        return self._conn.execute(query, params).fetchone()

    def fetchall(self, query: str, params: tuple = ()) -> list:
        return self._conn.execute(query, params).fetchall()

    def get_guild_config(self, guild_id: int) -> Optional[sqlite3.Row]:
        return self.fetchone("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,))

    def upsert_guild_config(self, guild_id: int, **kwargs: Any) -> None:
        self.execute("INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (guild_id,))
        if kwargs:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values()) + [guild_id]
            self.execute(f"UPDATE guild_config SET {sets} WHERE guild_id = ?", tuple(values))

    def create_ticket(self, guild_id: int, channel_id: int, creator_id: int) -> int:
        cur = self.execute(
            "INSERT INTO tickets (guild_id, channel_id, creator_id) VALUES (?, ?, ?)",
            (guild_id, channel_id, creator_id),
        )
        return cur.lastrowid

    def get_ticket_by_channel(self, channel_id: int) -> Optional[sqlite3.Row]:
        return self.fetchone("SELECT * FROM tickets WHERE channel_id = ?", (channel_id,))

    def close_ticket(self, channel_id: int) -> None:
        self.execute(
            "UPDATE tickets SET status = 'closed', closed_at = datetime('now') WHERE channel_id = ?",
            (channel_id,),
        )

    def save_transcript(self, ticket_id: int, content: str) -> None:
        self.execute(
            "INSERT INTO ticket_transcripts (ticket_id, content) VALUES (?, ?)",
            (ticket_id, content),
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
