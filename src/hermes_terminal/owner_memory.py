"""Explicit-consent local owner memory, without model dependencies or chat harvesting.

SQLite data is NOT encrypted by this module. Keep the database on an
owner-controlled encrypted volume and never commit private records to Git.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
_SCOPES = frozenset({"owner", "preferences", "projects", "devices", "workflows"})


class MemoryError(ValueError):
    """Invalid or disallowed owner-memory operation."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate(scope: str, key: str) -> None:
    if scope not in _SCOPES or not isinstance(key, str) or not _KEY.fullmatch(key):
        raise MemoryError("invalid memory scope or key")


class OwnerMemoryStore:
    """Auditable owner-confirmed memory store, disabled until explicitly used."""

    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser()
        if not self.path.is_absolute() or self.path.is_symlink():
            raise MemoryError("memory database must be an absolute non-symlink path")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name == "posix":
            mode = self.path.parent.stat().st_mode & 0o777
            if mode & 0o077:
                raise MemoryError("memory parent directory must not permit group/other access")
        if not self.path.exists():
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(self.path, flags, 0o600)
            os.close(fd)
        if self.path.is_symlink() or not self.path.is_file():
            raise MemoryError("invalid memory database file")
        if os.name == "posix" and (self.path.stat().st_mode & 0o077):
            raise MemoryError("memory file must not permit group/other access")
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS memory (
                scope TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                provenance TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL, PRIMARY KEY(scope, key)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS change_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, key_digest TEXT NOT NULL,
                action TEXT NOT NULL, occurred_at TEXT NOT NULL
            )""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA secure_delete=ON")
        db.execute("PRAGMA journal_mode=DELETE")
        return db

    def _event(self, db: sqlite3.Connection, scope: str, key: str, action: str) -> None:
        digest = hashlib.sha256(f"{scope}\0{key}".encode()).hexdigest()
        db.execute("INSERT INTO change_log (key_digest, action, occurred_at) VALUES (?, ?, ?)",
                   (digest, action, _utcnow()))

    def remember(self, *, scope: str, key: str, value: str,
                 provenance: str, consent: bool) -> dict:
        _validate(scope, key)
        if consent is not True:
            raise MemoryError("explicit owner consent is required")
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 2000:
            raise MemoryError("invalid memory value")
        if not isinstance(provenance, str) or not 1 <= len(provenance) <= 160:
            raise MemoryError("provenance is required")
        with self._connect() as db:
            db.execute("""INSERT INTO memory (scope,key,value,provenance,revision,updated_at)
                VALUES (?,?,?,?,1,?)
                ON CONFLICT(scope,key) DO UPDATE SET value=excluded.value,
                provenance=excluded.provenance, revision=revision+1,
                updated_at=excluded.updated_at""",
                       (scope, key, value.strip(), provenance, _utcnow()))
            self._event(db, scope, key, "remember_or_correct")
        return self.get(scope=scope, key=key)

    def get(self, *, scope: str, key: str) -> dict | None:
        _validate(scope, key)
        with self._connect() as db:
            row = db.execute("SELECT scope,key,value,provenance,revision,updated_at FROM memory WHERE scope=? AND key=?",
                             (scope, key)).fetchone()
            return dict(row) if row else None

    def list(self, *, scope: str | None = None, limit: int = 50) -> list[dict]:
        if scope is not None and scope not in _SCOPES:
            raise MemoryError("invalid scope")
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise MemoryError("invalid limit")
        with self._connect() as db:
            if scope is None:
                rows = db.execute("SELECT scope,key,value,provenance,revision,updated_at FROM memory ORDER BY scope,key LIMIT ?", (limit,))
            else:
                rows = db.execute("SELECT scope,key,value,provenance,revision,updated_at FROM memory WHERE scope=? ORDER BY key LIMIT ?", (scope, limit))
            return [dict(row) for row in rows]

    def search(self, query: str, *, limit: int = 10) -> list[dict]:
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 150:
            raise MemoryError("invalid search query")
        if not isinstance(limit, int) or not 1 <= limit <= 30:
            raise MemoryError("invalid limit")
        escaped = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self._connect() as db:
            rows = db.execute("""SELECT scope,key,value,provenance,revision,updated_at FROM memory
                WHERE key LIKE ? ESCAPE '\\' OR value LIKE ? ESCAPE '\\'
                ORDER BY scope,key LIMIT ?""", (f"%{escaped}%", f"%{escaped}%", limit))
            return [dict(row) for row in rows]

    def forget(self, *, scope: str, key: str) -> bool:
        _validate(scope, key)
        with self._connect() as db:
            result = db.execute("DELETE FROM memory WHERE scope=? AND key=?", (scope, key))
            if result.rowcount:
                self._event(db, scope, key, "forget")
            return bool(result.rowcount)
