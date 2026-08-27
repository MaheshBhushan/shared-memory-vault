from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import statistics
import sys
import time
from contextlib import closing
from pathlib import Path

from .config import default_config_path, load, platform_name, save
from .daemon import serve
from .index import connect, update
from .install import (bootstrap_vault, detect_harnesses, install_adapters,
                      install_obsidian, install_service, obsidian_status, uninstall)
from .ipc import recall as ipc_recall, request
from .retrieval import recall
from .synthesis import process_queue


def _percentile(samples, value):
    return sorted(samples)[max(0, min(len(samples) - 1, round((len(samples) - 1) * value)))]


def benchmark(config, rounds=200):
    queries = ["shared memory", "coding session", "project decision", "agent context"]
    with closing(sqlite3.connect(f"file:{config.database.resolve()}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        core = []
        for i in range(rounds):
            start = time.perf_counter_ns(); recall(db, queries[i % len(queries)]); core.append((time.perf_counter_ns()-start)/1e6)
    ipc = []
    for i in range(rounds):
        start = time.perf_counter_ns(); ipc_recall(config.endpoint, queries[i % len(queries)]); ipc.append((time.perf_counter_ns()-start)/1e6)
    def values(samples): return {key: round(_percentile(samples, pct), 3) for key, pct in (("p50", .5), ("p95", .95), ("p99", .99))}
    return {"samples": rounds, "in_process_ms": values(core), "ipc_ms": values(ipc)}


def doctor(config):
    status = {"platform": platform_name(), "obsidian": obsidian_status(),
              "vault": config.vault.is_dir(), "database": config.database.is_file(),
              "sqlite_fts5": False, "documents": 0, "service": False,
              "harnesses": detect_harnesses()}
    try:
        with closing(sqlite3.connect(f"file:{config.database.resolve()}?mode=ro", uri=True)) as db:
            status["documents"] = db.execute("SELECT count(*) FROM documents").fetchone()[0]
            db.execute("SELECT count(*) FROM documents_fts").fetchone()
            status["sqlite_fts5"] = True
        status["service"] = request(config.endpoint, {"version": 1, "action": "health"})["status"] == "ready"
    except Exception:
        pass
    return status


def parser():
    command = argparse.ArgumentParser(prog="memory", description="Local shared memory for coding agents")
    command.add_argument("--config", type=Path)
    actions = command.add_subparsers(dest="action", required=True)
    install = actions.add_parser("install"); install.add_argument("--vault", type=Path); install.add_argument("--skip-obsidian", action="store_true"); install.add_argument("--no-service", action="store_true")
    actions.add_parser("uninstall").add_argument("--delete-vault", action="store_true")
    index = actions.add_parser("reindex"); index.add_argument("--file", type=Path)
    find = actions.add_parser("recall"); find.add_argument("query"); find.add_argument("--project"); find.add_argument("--global", dest="global_only", action="store_true"); find.add_argument("--limit", type=int, default=3); find.add_argument("--json", action="store_true")
    actions.add_parser("daemon"); actions.add_parser("doctor"); actions.add_parser("synthesize")
    bench = actions.add_parser("benchmark"); bench.add_argument("--rounds", type=int, default=200)
    return command


def main(argv=None):
    args = parser().parse_args(argv)
    if args.config: os.environ["SHARED_MEMORY_CONFIG"] = str(args.config)
    config = load(args.config)
    if args.action == "install":
        if args.vault: config.vault_path = str(args.vault.resolve())
        print(f"Obsidian: {'skipped' if args.skip_obsidian else install_obsidian()}")
        bootstrap_vault(config.vault)
        detected = install_adapters(config)
        save(config, args.config)
        with closing(connect(config.database)) as db: print("Index:", update(db, config.vault, rebuild=True))
        if not args.no_service:
            print("Service:", install_service(config))
            for _ in range(50):
                if doctor(config)["service"]: break
                time.sleep(.1)
            health = doctor(config)
            if not health["service"]: raise SystemExit("service failed health check; run memory doctor")
            print("Health:", json.dumps(health))
            print("Benchmark:", json.dumps(benchmark(config, 50)))
        print("Harnesses:", " ".join(f"{name}={'connected' if name in config.enabled_adapters else ('detected' if present else 'not-installed')}" for name, present in detected.items()))
        print("READY")
    elif args.action == "uninstall": uninstall(config, keep_vault=not args.delete_vault)
    elif args.action == "reindex":
        with closing(connect(config.database)) as db: print(json.dumps(update(db, config.vault, rebuild=not args.file, only=args.file)))
    elif args.action == "recall":
        if args.project and args.global_only: raise SystemExit("--project and --global cannot be combined")
        try: results = ipc_recall(config.endpoint, args.query, args.limit, args.project, args.global_only)
        except Exception:
            with closing(sqlite3.connect(f"file:{config.database.resolve()}?mode=ro", uri=True)) as db:
                db.row_factory = sqlite3.Row; results = recall(db, args.query, args.limit, args.project, args.global_only)
        if args.json: print(json.dumps(results, ensure_ascii=False))
        else:
            for hit in results: print(f"{hit['score']:.4f} {hit['path']} — {hit['title']}")
    elif args.action == "daemon": serve(args.config)
    elif args.action == "doctor": print(json.dumps(doctor(config), indent=2))
    elif args.action == "synthesize": print(f"processed={process_queue(config)}")
    elif args.action == "benchmark": print(json.dumps(benchmark(config, args.rounds), indent=2))
    return 0
