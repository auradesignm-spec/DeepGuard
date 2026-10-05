"""Durable session store for Sieve scrape runs.

DeepGuard has no database; uploads and reports live in plain directories
(``settings.UPLOAD_DIR`` / ``settings.REPORTS_DIR``). Sieve session state
follows the same convention: one JSON document per session under
``settings.SIEVE_STATE_DIR`` (gitignored, like the other runtime dirs).

Why this exists: ``POST /api/scrapes`` has no idempotency key and an accepted
call spends credits. The ``session_id`` from the 202 therefore has to reach
durable storage before the caller is allowed to do anything else, so that a
crash resumes polling from the stored id instead of starting a duplicate run.

Writes are atomic (temp file + ``os.replace``) and guarded by a lock so
concurrent requests cannot interleave a half-written record.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings

# Session ids are opaque server-issued tokens; only these characters are
# allowed so a crafted id can never escape the state directory.
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_safe_session_id(session_id: Any) -> bool:
    """True when an id is a plain token safe to use as a filename."""
    return isinstance(session_id, str) and bool(_SAFE_ID.match(session_id))


def _root(state_dir: Optional[str] = None) -> str:
    return state_dir or settings.SIEVE_STATE_DIR


def _path(session_id: str, state_dir: Optional[str] = None) -> str:
    if not isinstance(session_id, str) or not _SAFE_ID.match(session_id):
        raise ValueError(f"unsafe session id: {session_id!r}")
    root = _root(state_dir)
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, f"{session_id}.json")


def _write(record: Dict[str, Any], path: str) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=True, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def save_session(record: Dict[str, Any], *, state_dir: Optional[str] = None) -> Dict[str, Any]:
    """Atomically persist a session record and return the stored copy."""
    session_id = record.get("session_id")
    path = _path(session_id, state_dir)
    stored = dict(record)
    stored.setdefault("created_at", _utc_now())
    stored["updated_at"] = _utc_now()
    with _LOCK:
        _write(stored, path)
    return stored


def load_session(session_id: str, *, state_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Return the stored record, or ``None`` when absent/unsafe."""
    try:
        path = _path(session_id, state_dir)
    except ValueError:
        return None
    if not os.path.exists(path):
        return None
    with _LOCK:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None


def update_session(session_id: str, *, state_dir: Optional[str] = None, **fields: Any) -> Optional[Dict[str, Any]]:
    """Merge ``fields`` into a stored record. Returns ``None`` if unknown."""
    with _LOCK:
        record = load_session(session_id, state_dir=state_dir)
        if record is None:
            return None
        record.update(fields)
        record["updated_at"] = _utc_now()
        _write(record, _path(session_id, state_dir))
    return record


def list_sessions(*, state_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return every stored session, newest first."""
    root = _root(state_dir)
    if not os.path.isdir(root):
        return []
    records: List[Dict[str, Any]] = []
    for name in sorted(os.listdir(root)):
        if not name.endswith(".json"):
            continue
        record = load_session(name[: -len(".json")], state_dir=state_dir)
        if record:
            records.append(record)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records


def delete_session(session_id: str, *, state_dir: Optional[str] = None) -> bool:
    """Remove a stored session (used by tests and cleanup tooling)."""
    try:
        path = _path(session_id, state_dir)
    except ValueError:
        return False
    with _LOCK:
        if os.path.exists(path):
            os.remove(path)
            return True
    return False
