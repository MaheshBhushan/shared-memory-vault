"""Normalized, scrubbed, bounded, asynchronous session capture."""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import Config

SCHEMA_FIELDS = ("session_id", "harness", "host", "project", "cwd", "started_at",
                 "ended_at", "branch", "prompts", "commands", "files_changed", "final_response")
SECRET_PATTERNS = [
    re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*([^\s\"']+)")]


def scrub(value: str) -> str:
    value = SECRET_PATTERNS[0].sub("[REDACTED]", value)
    return SECRET_PATTERNS[1].sub(lambda match: f"{match.group(1)}=[REDACTED]", value)


def normalize(**values):
    result = {"schema_version": 1}
    for field in SCHEMA_FIELDS:
        default = [] if field in {"prompts", "commands", "files_changed"} else ("" if field == "final_response" else None)
        result[field] = values.get(field, default)
    result["host"] = result["host"] or socket.gethostname()
    return result


@contextmanager
def _lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    if os.name == "nt":
        import msvcrt
        if handle.tell() == 0: handle.write("\0"); handle.flush()
        handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl
        fcntl.flock(handle, fcntl.LOCK_EX)
    try:
        yield
    finally:
        if os.name == "nt":
            handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


def _bounded(values, count=40, size=2000):
    return [scrub(str(value))[:size] for value in (values or [])[:count]]


def capture(config: Config, session: dict) -> Path:
    if session.get("schema_version") != 1:
        raise ValueError("unsupported provenance schema")
    inbox, queue = config.state / "queue/inbox", config.state / "queue/pending.txt"
    inbox.mkdir(parents=True, exist_ok=True)
    identity = str(session.get("session_id") or json.dumps(session, sort_keys=True))
    filename = f"{session.get('harness') or 'unknown'}-{hashlib.sha256(identity.encode()).hexdigest()[:16]}.json"
    safe = normalize(**session)
    for field in ("prompts", "commands", "files_changed"):
        safe[field] = _bounded(safe[field])
    safe["final_response"] = scrub(str(safe.get("final_response") or ""))[:8000]
    target, temporary = inbox / filename, inbox / f".{filename}.tmp"
    temporary.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    with _lock(config.state / "queue/.lock"):
        existing = set(queue.read_text(encoding="utf-8").splitlines()) if queue.exists() else set()
        existing.add(filename)
        temp_queue = queue.with_suffix(".tmp")
        temp_queue.write_text("".join(f"{name}\n" for name in sorted(existing)), encoding="utf-8")
        os.replace(temp_queue, queue)
    return target
