"""Persistent local-only recall service."""

from __future__ import annotations

import json
import os
import signal
import socket
import sqlite3
import stat
import threading
import time
from pathlib import Path

from .config import load
from .ipc import MAX_REQUEST, MAX_RESPONSE, PROTOCOL_VERSION, read_windows, windows_listener
from .retrieval import recall
from .synthesis import process_queue


class RequestError(ValueError):
    pass


def validate(payload):
    if not isinstance(payload, dict) or payload.get("version") != PROTOCOL_VERSION:
        raise RequestError("unsupported request or protocol version")
    if payload.get("action") not in {"recall", "health"}:
        raise RequestError("unsupported action")
    if payload["action"] == "health":
        return None
    query, limit = payload.get("query"), payload.get("limit", 3)
    project, global_only = payload.get("project"), payload.get("global", False)
    if not isinstance(query, str) or not query.strip() or len(query) > 4096:
        raise RequestError("query must be 1..4096 characters")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise RequestError("limit must be 1..20")
    if project is not None and (not isinstance(project, str) or not 1 <= len(project) <= 128):
        raise RequestError("invalid project")
    if not isinstance(global_only, bool) or (project and global_only):
        raise RequestError("invalid global/project filter")
    return query, limit, project, global_only


def handle(db, payload):
    try:
        args = validate(payload)
        if args is None:
            return {"ok": True, "status": "ready"}
        return {"ok": True, "results": recall(db, *args)}
    except Exception as error:
        return {"ok": False, "error": str(error)}


def _serve_windows(db, endpoint):
    listener = windows_listener(endpoint)
    try:
        while True:
            connection = listener.accept()
            try:
                response = json.dumps(handle(db, read_windows(connection))).encode()
                connection.send_bytes(response[:MAX_RESPONSE])
            except Exception as error:
                connection.send_bytes(json.dumps({"ok": False, "error": str(error)}).encode())
            finally:
                connection.close()
    finally:
        listener.close()


def _serve_unix(db, endpoint):
    path = Path(endpoint)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists():
        if not stat.S_ISSOCK(path.lstat().st_mode):
            raise RuntimeError(f"refusing to replace non-socket: {path}")
        probe = socket.socket(socket.AF_UNIX)
        try:
            probe.settimeout(.1)
            probe.connect(str(path))
        except (ConnectionRefusedError, FileNotFoundError, socket.timeout):
            path.unlink(missing_ok=True)
        else:
            raise RuntimeError("memory daemon already running")
        finally:
            probe.close()
    server = socket.socket(socket.AF_UNIX)
    stop = False
    def finish(*_):
        nonlocal stop
        stop = True
        server.close()
    signal.signal(signal.SIGTERM, finish)
    signal.signal(signal.SIGINT, finish)
    try:
        server.bind(str(path)); path.chmod(0o600); server.listen(16); server.settimeout(.5)
        while not stop:
            try:
                connection, _ = server.accept()
            except (socket.timeout, OSError):
                continue
            with connection:
                data = bytearray()
                while b"\n" not in data and len(data) <= MAX_REQUEST:
                    chunk = connection.recv(4096)
                    if not chunk: break
                    data.extend(chunk)
                try:
                    payload = json.loads(bytes(data).split(b"\n", 1)[0])
                    response = handle(db, payload)
                except Exception as error:
                    response = {"ok": False, "error": str(error)}
                connection.sendall(json.dumps(response, ensure_ascii=False).encode()[:MAX_RESPONSE] + b"\n")
    finally:
        server.close(); path.unlink(missing_ok=True)


def serve(config_path=None):
    config = load(config_path)
    if not config.database.is_file():
        raise RuntimeError("derived index is missing; run memory reindex")
    db = sqlite3.connect(f"file:{config.database.resolve()}?mode=ro", uri=True, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    stopping = threading.Event()
    def worker():
        while not stopping.wait(2):
            try:
                process_queue(config)
            except Exception:
                pass
    background = threading.Thread(target=worker, daemon=True)
    background.start()
    try:
        (_serve_windows if os.name == "nt" else _serve_unix)(db, config.endpoint)
    finally:
        stopping.set()
        db.close()
