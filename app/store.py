from __future__ import annotations

import contextlib
import json
import os
import secrets
import sqlite3
from pathlib import Path

DEFAULTS = {
    "uploads_enabled": False,
    "max_uploads_24h": 2,
    "timezone": "Asia/Colombo",
    "render_width": 720,
    "threads": 2,
    "storage_limit_mb": 4096,
    "retention_days": 7,
}


class Store:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        for name in ("assets", "outputs", "work", "secrets"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root / "secrets", 0o700)
        except OSError:
            pass
        self.db = self.root / "studio.sqlite3"
        with self.connect() as c:
            c.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL,
                    path TEXT NOT NULL, sha256 TEXT UNIQUE NOT NULL, extension TEXT NOT NULL,
                    mood TEXT NOT NULL, rights_notes TEXT NOT NULL DEFAULT '',
                    attribution TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 0, start_sec REAL NOT NULL DEFAULT 0,
                    duration REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL,
                    fingerprint TEXT UNIQUE NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    publish_at TEXT, delivery TEXT NOT NULL, preapproved INTEGER NOT NULL DEFAULT 0,
                    is_demo INTEGER NOT NULL DEFAULT 0, output TEXT,
                    youtube_id TEXT, uploaded_at TEXT, upload_session TEXT,
                    error TEXT NOT NULL DEFAULT '', progress INTEGER NOT NULL DEFAULT 0
                );
                CREATE UNIQUE INDEX IF NOT EXISTS unique_active_slot ON jobs(publish_at)
                    WHERE delivery='scheduled' AND status!='cancelled';
                CREATE UNIQUE INDEX IF NOT EXISTS unique_youtube_id ON jobs(youtube_id)
                    WHERE youtube_id IS NOT NULL;
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
                    job_id TEXT, message TEXT NOT NULL
                );
            """)
            for key, value in DEFAULTS.items():
                c.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (key, json.dumps(value)))
            c.execute("INSERT OR IGNORE INTO settings VALUES ('csrf',?)", (json.dumps(secrets.token_urlsafe(32)),))
        try:
            os.chmod(self.db, 0o600)
        except OSError:
            pass

    @contextlib.contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=20)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=20000")
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def settings(self):
        with self.connect() as c:
            return {r["key"]: json.loads(r["value"]) for r in c.execute("SELECT * FROM settings")}

    def set_settings(self, values):
        with self.connect() as c:
            for key, value in values.items():
                c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, json.dumps(value)))

    def rows(self, sql, args=()):
        with self.connect() as c:
            return [dict(r) for r in c.execute(sql, args)]

    def one(self, sql, args=()):
        rows = self.rows(sql, args)
        return rows[0] if rows else None

    def used_bytes(self):
        return sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file())
