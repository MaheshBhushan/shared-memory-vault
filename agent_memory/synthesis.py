"""Background queue to canonical Markdown; providers stay outside capture/index."""

from __future__ import annotations

import json
import os
import re
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .capture import _lock
from .config import Config
from .index import connect, update


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return value[:60] or "session"


def builtin_markdown(session: dict) -> str:
    title_source = next(iter(session.get("prompts") or []), "Coding session")
    title = " ".join(title_source.strip().split())[:100]
    date = (session.get("ended_at") or session.get("started_at") or
            datetime.now(timezone.utc).isoformat())[:10]
    project = session.get("project") or (Path(session["cwd"]).name if session.get("cwd") else "unassigned")
    yaml = ["---", "type: session", f"project: {_slug(project)}", f"date: {date}"]
    for key in ("harness", "session_id", "host"):
        if session.get(key) is not None:
            yaml.append(f"{key}: {json.dumps(str(session[key]), ensure_ascii=False)}")
    yaml.extend(["tags: [session]", "---", "", f"# {title}", ""])
    sections = []
    if session.get("prompts"):
        sections += ["## Requests", *[f"- {value}" for value in session["prompts"]]]
    if session.get("final_response"):
        sections += ["", "## Outcome", session["final_response"]]
    if session.get("files_changed"):
        sections += ["", "## Files changed", *[f"- `{value}`" for value in session["files_changed"]]]
    if session.get("commands"):
        sections += ["", "## Commands", *[f"- `{value}`" for value in session["commands"]]]
    return "\n".join(yaml + sections).rstrip() + "\n"


def process_queue(config: Config) -> int:
    """Claim all queued digests; failed items remain queued."""
    queue_root = config.state / "queue"
    pending, active, lock = queue_root / "pending.txt", queue_root / "active.txt", queue_root / ".lock"
    with _lock(lock):
        names = set(active.read_text().splitlines()) if active.exists() else set()
        names.update(pending.read_text().splitlines() if pending.exists() else [])
        active.parent.mkdir(parents=True, exist_ok=True)
        active.write_text("".join(f"{name}\n" for name in sorted(names)), encoding="utf-8")
        pending.write_text("", encoding="utf-8")
    completed = []
    for name in sorted(names):
        source = queue_root / "inbox" / Path(name).name
        if not source.is_file():
            completed.append(name); continue
        session = json.loads(source.read_text(encoding="utf-8"))
        project = _slug(session.get("project") or (Path(session["cwd"]).name if session.get("cwd") else "unassigned"))
        date = (session.get("ended_at") or session.get("started_at") or datetime.now(timezone.utc).isoformat())[:10]
        identity = _slug(str(session.get("session_id") or source.stem))[:24]
        target = config.vault / "projects" / project / "sessions" / f"{date}-{identity}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(builtin_markdown(session), encoding="utf-8")
        os.replace(temporary, target)
        with closing(connect(config.database)) as db:
            update(db, config.vault, only=target)
        completed.append(name)
    with _lock(lock):
        remaining = set(active.read_text().splitlines()) - set(completed)
        active.write_text("".join(f"{name}\n" for name in sorted(remaining)), encoding="utf-8")
    return len(completed)
