"""
database.py — Couche d'accès aux données (SQLite).

⚠️  RAILWAY : Le système de fichiers est ÉPHÉMÈRE.
    Montez un Volume Railway sur /data et définissez DB_PATH=/data/bot.db
    dans vos variables d'environnement pour rendre la base persistante.
    Un simple changement de DB_PATH suffit — aucune modification de code requise.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("bot.database")


class Database:
    """Gestionnaire de base de données SQLite thread-safe (via check_same_thread=False)."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        """Retourne une connexion SQLite avec Row factory activée."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")   # Meilleures performances concurrentes
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self) -> None:
        """Crée les tables si elles n'existent pas encore."""
        self._conn = self._connect()
        with self._conn:
            self._conn.executescript("""
                -- Configuration par serveur
                CREATE TABLE IF NOT EXISTS guild_config (
                    guild_id        INTEGER PRIMARY KEY,
                    welcome_channel INTEGER,
                    announce_channel INTEGER,
                    log_channel     INTEGER,
                    ticket_category INTEGER,
                    staff_role      INTEGER,
                    welcome_message TEXT    DEFAULT 'Bienvenue {user} sur **{server}** ! 🎉 Vous êtes le membre n°{member_count}.',
                    goodbye_message TEXT    DEFAULT 'Au revoir **{user}**, nous étions {member_count} membres.'
                );

                -- Tickets ouverts
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id    INTEGER NOT NULL,
                    channel_id  INTEGER NOT NULL UNIQUE,
                    creator_id  INTEGER NOT NULL,
                    created_at  TEXT    DEFAULT (datetime('now')),
                    closed_at   TEXT,
                    status      TEXT    DEFAULT 'open'
                );

                -- Transcripts de tickets
                CREATE TABLE IF NOT EXISTS ticket_transcripts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id   INTEGER NOT NULL REFERENCES tickets(ticket_id),
                    content     TEXT    NOT NULL,
                    saved_at    TEXT    DEFAULT (datetime('now'))
                );
            """)
        logger.info(f"✅ Base de données initialisée : {self.db_path}")

    # ── Méthodes génériques ────────────────────────────────────────────────────

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Exécute une requête et commit automatiquement."""
        with self._conn:
            return self._conn.execute(query, params)

    def fetchone(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        return self._conn.execute(query, params).fetchone()

    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self._conn.execute(query, params).fetchall()

    # ── Configuration du serveur ──────────────────────────────────────────────

    def get_guild_config(self, guild_id: int) -> Optional[sqlite3.Row]:
        """Récupère la configuration d'un serveur."""
        return self.fetchone(
            "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)
        )

    def upsert_guild_config(self, guild_id: int, **kwargs: Any) -> None:
        """Crée ou met à jour la configuration d'un serveur."""
        # Insertion initiale si nécessaire
        self.execute(
            "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (guild_id,)
        )
        # Mise à jour des champs fournis
        if kwargs:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values()) + [guild_id]
            self.execute(f"UPDATE guild_config SET {sets} WHERE guild_id = ?", tuple(values))

    # ── Tickets ───────────────────────────────────────────────────────────────

    def create_ticket(self, guild_id: int, channel_id: int, creator_id: int) -> int:
        """Enregistre un nouveau ticket et retourne son ID."""
        cur = self.execute(
            "INSERT INTO tickets (guild_id, channel_id, creator_id) VALUES (?, ?, ?)",
            (guild_id, channel_id, creator_id),
        )
        return cur.lastrowid  # type: ignore

    def get_ticket_by_channel(self, channel_id: int) -> Optional[sqlite3.Row]:
        return self.fetchone(
            "SELECT * FROM tickets WHERE channel_id = ?", (channel_id,)
        )

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
        """Ferme proprement la connexion à la base de données."""
        if self._conn:
            self._conn.close()
            logger.info("🔒 Connexion base de données fermée.")
