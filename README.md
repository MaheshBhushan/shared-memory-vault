# Shared Memory Vault

Shared memory for your coding agents.

```text
Claude Code ─┐
Codex ───────┤
OpenCode ────┼──→ one persistent memory
Pi ──────────┘
```

Markdown-native. Obsidian workspace. Local-first. Low-latency. No MCP required.

Shared Memory Vault is self-installing infrastructure, not another app to keep open. It gives supported coding harnesses one local memory: session capture writes to a durable background queue, canonical notes live in an Obsidian vault, and a persistent local service retrieves compact pointers from a disposable SQLite FTS5 index.

> Status: v0.1.0. Linux is live-tested. Windows logic and CI are tested, but a real Windows installation and latency run remain required. Claude Code and Codex were live-proven in the originating V2 system; this clean installer is isolated-environment tested. OpenCode and Pi adapters are experimental pending live cross-harness capture verification.

## Install

Linux:

```bash
git clone https://github.com/MaheshBhushan/shared-memory-vault.git
cd shared-memory-vault
./setup/install.sh
```

Windows PowerShell:

```powershell
git clone https://github.com/MaheshBhushan/shared-memory-vault.git
cd shared-memory-vault
.\setup\install.ps1
```

The installer checks Python and Obsidian, creates `~/Documents/AgentMemory` (or `%USERPROFILE%\Documents\AgentMemory`), detects installed harnesses, backs up and merges hooks, builds the index, and starts the local service. It never installs a coding harness. If automatic Obsidian installation is unavailable, setup prints the official continuation path.

Paths with spaces and Unicode are supported. Override the vault with `./setup/install.sh --vault "/path/with spaces/AgentMemory"`.

## How it works

```text
HOT:        harness → hook/plugin → local IPC → resident service → SQLite FTS5
BACKGROUND: session → normalized capture → scrubbed queue → synthesis → Markdown → index
```

The invariant is strict:

```text
Markdown = canonical memory
SQLite + FTS5 = disposable derived index
Obsidian = visible workspace
```

Delete `memory.db`, run `memory reindex`, and the complete index returns from Markdown. The retriever uses FTS5/BM25 with proven field weights (`title=8`, `symptoms=10`, `tags=5`, `body=1`) and a `1.08` wiki/global boost. It returns paths, titles, scores, and small snippets—not whole documents.

See [architecture](docs/architecture.md), [configuration](docs/configuration.md), and [adding a harness](docs/adapters.md).

## Commands

```bash
memory doctor
memory recall "audio routing" --project friday
memory recall "agent context" --global --limit 3
memory reindex
memory benchmark --rounds 500
memory synthesize
```

Recall is local-only: Unix domain socket on Linux, named pipe on Windows, direct read-only SQLite fallback if IPC is unavailable, then a silent miss. A memory failure never blocks a coding prompt.

## Platform and harness status

| Component | Status |
|---|---|
| Linux / Unix socket / systemd user service | Live verified |
| Windows / named pipe / Startup task | CI and unit tested; live verification pending |
| Claude Code hooks | Proven V2 behavior; clean merge tested |
| Codex hooks | Proven V2 cross-harness behavior; clean merge tested |
| OpenCode owned plugin | Implemented; experimental/live verification pending |
| Pi owned extension | Implemented; experimental/live verification pending |

The OpenCode and Pi files are owned by this repository and coexist with Agent Overlay; Agent Overlay is not a dependency.

## Performance

The originating Linux V2 corpus measured 2.209 ms in-process p95 and 2.584 ms Unix-socket p95. Clean-repository results are recorded in the release/report and should be measured on every target machine with `memory benchmark`. Cloud CI latency is informational and is not compared with local hardware. No Windows latency claim is made without a Windows measurement.

## Privacy and security

No network is used for recall. The Unix socket is user-only (0600), the database is read-only in the service, capture is bounded and secret-scrubbed, and raw queue/index/runtime state is Git-ignored. Scrubbing is defense in depth, not a guarantee: harness transcripts remain sensitive and users should rotate exposed credentials.

Never commit your vault unless you intentionally want its contents in Git. See [SECURITY.md](SECURITY.md).

## Recovery and uninstall

Rebuild disposable state:

```bash
memory reindex
memory doctor
```

Remove hooks, adapters, service, index, and runtime state while preserving the Markdown vault:

```bash
./setup/uninstall.sh
```

Canonical memory is deleted only with the explicit destructive option:

```bash
./setup/uninstall.sh --delete-vault
```

## Development

```bash
python -m unittest discover -s tests -v
python -m agent_memory --help
```

Contributions are welcome; read [CONTRIBUTING.md](CONTRIBUTING.md). This project deliberately has no embeddings, vector database, graph database, MCP server, REST service, cloud database, or remote recall dependency.
