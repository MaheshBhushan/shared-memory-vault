"""Fail-open hook entry point used by Claude Code and Codex."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from ..capture import capture, normalize
from ..config import load
from ..ipc import recall as ipc_recall
from ..retrieval import recall as direct_recall


def _prompt(payload):
    return payload.get("prompt") or payload.get("user_prompt") or payload.get("input") or ""


def recall_hook(payload):
    prompt = _prompt(payload)
    if len(prompt.strip()) < 8 or prompt.lstrip().startswith("/"):
        return ""
    config = load()
    try:
        results = ipc_recall(config.endpoint, prompt, limit=2)
    except Exception:
        try:
            db = sqlite3.connect(f"file:{config.database.resolve()}?mode=ro", uri=True)
            db.row_factory = sqlite3.Row
            results = direct_recall(db, prompt, limit=2)
            db.close()
        except Exception:
            return ""
    if not results:
        return ""
    lines = ["Relevant shared memory (read a file only if needed):"]
    lines.extend(f"- {config.vault / hit['path']} — {hit['title']}" for hit in results)
    return "\n".join(lines)


def capture_hook(payload, harness):
    config = load()
    transcript = _transcript(payload.get("transcript_path"))
    session = normalize(harness=harness,
        session_id=payload.get("session_id") or payload.get("sessionID"),
        cwd=payload.get("cwd"), project=payload.get("project"),
        started_at=payload.get("started_at"), ended_at=payload.get("ended_at"),
        branch=payload.get("branch"), prompts=payload.get("prompts") or transcript[0],
        commands=payload.get("commands") or transcript[2], files_changed=payload.get("files_changed") or transcript[3],
        final_response=payload.get("final_response") or transcript[1])
    capture(config, session)


def _text(content):
    if isinstance(content, str): return content
    if isinstance(content, list):
        return "\n".join(str(item.get("text", "")) for item in content
                          if isinstance(item, dict) and item.get("type") in {"text", "input_text", "output_text"})
    return ""


def _transcript(value):
    """Best-effort JSONL extraction; rollout knowledge stays at the adapter boundary."""
    prompts, final, commands, files = [], "", [], set()
    if not value: return prompts, final, commands, []
    path = Path(value).expanduser()
    if not path.is_file(): return prompts, final, commands, []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            event = json.loads(line); payload = event.get("payload", event)
            message = payload.get("message", payload) if isinstance(payload, dict) else {}
            role, content = message.get("role"), message.get("content")
            text = _text(content)
            if role == "user" and text and not text.startswith(("# AGENTS.md instructions", "<environment_context>")): prompts.append(text)
            elif role == "assistant" and text: final = text
            item = payload.get("item", {}) if isinstance(payload, dict) else {}
            if item.get("type") in {"CommandExecution", "command_execution"}:
                command = item.get("command")
                commands.append(" ".join(command) if isinstance(command, list) else str(command or ""))
            changes = item.get("changes", {})
            if isinstance(changes, dict): files.update(changes)
    except Exception:
        return [], "", [], []
    return prompts[-40:], final, [value for value in commands if value][-40:], sorted(files)[:100]


def main(argv=None):
    argv = argv or sys.argv[1:]
    try:
        payload = json.load(sys.stdin)
        if argv[0] == "recall":
            output = recall_hook(payload)
            if output: print(output)
        elif argv[0] == "capture":
            capture_hook(payload, argv[1])
    except Exception:
        pass  # A memory failure must never block a harness.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
