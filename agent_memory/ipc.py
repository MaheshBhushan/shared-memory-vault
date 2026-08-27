"""Local IPC: Unix sockets on POSIX, native named pipes on Windows."""

from __future__ import annotations

import json
import os
import socket
from multiprocessing.connection import Client, Listener
from pathlib import Path

PROTOCOL_VERSION = 1
MAX_REQUEST = 16 * 1024
MAX_RESPONSE = 64 * 1024
PIPE_AUTHKEY = b"shared-memory-vault-local-v1"


def request(endpoint: str, payload: dict, timeout=1.0):
    if os.name == "nt":
        connection = Client(endpoint, family="AF_PIPE", authkey=PIPE_AUTHKEY)
        try:
            connection.send_bytes(json.dumps(payload).encode())
            raw = connection.recv_bytes(MAX_RESPONSE)
        finally:
            connection.close()
    else:
        encoded = json.dumps(payload, ensure_ascii=False).encode() + b"\n"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            client.connect(endpoint)
            client.sendall(encoded)
            chunks, size = [], 0
            while True:
                chunk = client.recv(min(4096, MAX_RESPONSE + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_RESPONSE:
                    raise RuntimeError("memory response is too large")
                if b"\n" in chunk:
                    break
            raw = b"".join(chunks).split(b"\n", 1)[0]
    response = json.loads(raw)
    if not response.get("ok"):
        raise RuntimeError(response.get("error", "memory request failed"))
    return response.get("results", response)


def recall(endpoint, query, limit=3, project=None, global_only=False):
    return request(endpoint, {"version": PROTOCOL_VERSION, "action": "recall",
                              "query": query, "limit": limit, "project": project,
                              "global": global_only})


def windows_listener(endpoint):
    return Listener(endpoint, family="AF_PIPE", authkey=PIPE_AUTHKEY)


def read_windows(connection):
    return json.loads(connection.recv_bytes(MAX_REQUEST))
