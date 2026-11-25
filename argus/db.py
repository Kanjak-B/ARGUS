"""Persistance SQLite : inventaire, dernière topologie et historique des changements."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL UNIQUE,
    hostname TEXT,
    created_at TEXT NOT NULL,
    role TEXT
);
CREATE TABLE IF NOT EXISTS state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    topology TEXT NOT NULL,
    scanned_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    details TEXT NOT NULL
);
"""


class DuplicateDeviceError(Exception):
    """Cette adresse est déjà enregistrée."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            # Bases créées avant l'ajout des couches
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(devices)")}
            if "role" not in columns:
                conn.execute("ALTER TABLE devices ADD COLUMN role TEXT")

    @contextmanager
    def _connect(self):
        # Une connexion par opération : utilisable depuis n'importe quel thread
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:  # commit, ou rollback en cas d'erreur
                yield conn
        finally:
            conn.close()

    def list_devices(self):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, ip, hostname, created_at, role FROM devices ORDER BY id"
            )
            return [dict(row) for row in rows]

    def set_role(self, device_id, role):
        """role : couche choisie, ou None pour la détection automatique."""
        with self._connect() as conn:
            cursor = conn.execute("UPDATE devices SET role = ? WHERE id = ?", (role, device_id))
            return cursor.rowcount > 0

    def add_device(self, ip):
        created_at = _now()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "INSERT INTO devices (ip, created_at) VALUES (?, ?)", (ip, created_at)
                )
        except sqlite3.IntegrityError as e:
            raise DuplicateDeviceError(ip) from e
        return {
            "id": cursor.lastrowid,
            "ip": ip,
            "hostname": None,
            "created_at": created_at,
            "role": None,
        }

    def delete_device(self, device_id):
        with self._connect() as conn:
            return conn.execute("DELETE FROM devices WHERE id = ?", (device_id,)).rowcount > 0

    def load_state(self):
        """Retourne (topologie, date du scan), ou (None, None) avant le premier scan."""
        with self._connect() as conn:
            row = conn.execute("SELECT topology, scanned_at FROM state WHERE id = 1").fetchone()
        if row is None:
            return None, None
        return json.loads(row["topology"]), row["scanned_at"]

    def save_scan(self, topology, changes):
        """Enregistre en une transaction la topologie, les noms connus et les changements."""
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO state (id, topology, scanned_at) VALUES (1, ?, ?)",
                (json.dumps(topology, ensure_ascii=False), now),
            )
            conn.executemany(
                "UPDATE devices SET hostname = ? WHERE ip = ?",
                [(name, info["ip"]) for name, info in topology["devices"].items()],
            )
            conn.executemany(
                "INSERT INTO changes (created_at, type, message, details) VALUES (?, ?, ?, ?)",
                [
                    (now, c["type"], c["message"], json.dumps(c["details"], ensure_ascii=False))
                    for c in changes
                ],
            )

    def list_changes(self, limit=100):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, created_at, type, message, details FROM changes "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{**dict(row), "details": json.loads(row["details"])} for row in rows]
