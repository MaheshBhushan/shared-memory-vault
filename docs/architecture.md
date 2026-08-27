# Architecture

## Invariant

```text
Markdown = memory
SQLite = index
Obsidian = workspace/interface
```

Only Markdown under `projects/`, `wiki/`, and `global/` is canonical. Queue files, SQLite files, sockets/pipes, and service state are derived or intermediate and may be recreated.

## Hot read path

```text
Harness
   ↓
adapter
   ↓
local IPC (Unix socket / Windows named pipe)
   ↓
persistent memory service
   ↓
SQLite + FTS5 (read-only connection)
   ↓
compact Markdown pointers
```

The service keeps SQLite open and avoids interpreter startup in resident adapters. FTS5 uses `porter unicode61`, BM25 weights `8/10/5/1`, and a `1.08` synthesis-page boost. Wikilinks are indexed as relations but do not affect ranking.

Failure is fail-open: IPC → direct read-only SQLite → silent miss. Hooks always exit successfully.

## Background write path

```text
Harness session
   ↓
capture adapter
   ↓
schema-v1 normalized session
   ↓
bounded + secret-scrubbed digest
   ↓
durable queue
   ↓
synthesis provider
   ↓
canonical Markdown
   ↓
incremental index refresh
```

The built-in provider deterministically creates provenance-bearing session notes, so capture works without a particular LLM subscription. Future synthesis providers may improve cross-project wiki pages, but cannot be imported by the indexer, capture core, or retriever. Retrieval continues if synthesis is unavailable.

## Boundaries

- `agent_memory/index.py`: Markdown parsing, content hashes, FTS schema, links.
- `agent_memory/retrieval.py`: query normalization and ranking only.
- `agent_memory/ipc.py` and `daemon.py`: platform-local transport and resident service.
- `agent_memory/capture.py` and `synthesis.py`: normalized background writes.
- `agent_memory/adapters/` and `adapters/`: harness lifecycle knowledge only.
- `agent_memory/install.py`: external configuration backup/merge and services.

The core imports no harness adapter. SQLite never receives facts that are absent from canonical Markdown.
