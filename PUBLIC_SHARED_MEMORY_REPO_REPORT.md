# Public Shared Memory Repository Report

Report date: 2026-08-27

## 1. GitHub repository

- Name: `shared-memory-vault`
- URL: https://github.com/MaheshBhushan/shared-memory-vault
- Visibility: public
- Publication implementation commit: `22072a41eeec51647d58747f9aa667d6b42827ea`
- Version: `v0.1.0` (pre-1.0)

## Verification vocabulary

- **LIVE VERIFIED** — exercised end to end on the local Linux host.
- **CI VERIFIED** — executed successfully by GitHub-hosted platform runners.
- **UNIT TESTED** — logic exercised through an automated test or mock.
- **IMPLEMENTED BUT UNVERIFIED** — implementation exists but lacks the claimed live proof.
- **NOT IMPLEMENTED** — deliberately absent.

## 2. Extraction and rewrite

**LIVE VERIFIED** — The public repository was created with clean Git history. It does not inherit the personal vault's history.

Portable behavior extracted and generalized from Shared Memory V2:

- deterministic `projects/`, `wiki/`, and `global/` Markdown indexing;
- SQLite FTS5 external-content schema, triggers, content hashes, and wikilinks;
- query normalization and retained BM25 weights (`8/10/5/1`) plus `1.08` wiki/global boost;
- compact recall output and fail-open direct-SQLite fallback;
- local Unix-socket daemon protocol;
- normalized provenance, secret scrubbing, bounded capture, and durable queue;
- Claude/Codex JSON hook conventions and OpenCode/Pi lifecycle knowledge.

Rewritten components:

- all paths and configuration;
- installer, diagnostics, health checks, uninstall, and backup/merge behavior;
- platform IPC abstraction and Windows named-pipe implementation;
- repository-owned OpenCode and Pi adapters (no Agent Overlay dependency);
- synthesis boundary and deterministic built-in provider;
- cross-platform test suite, CI, public docs, and empty vault bootstrap.

Personal Markdown, session history, transcripts, projects, databases, queues, provider configuration, credentials, host state, paths, and Git history were not copied.

## 3. Installed architecture

```text
                            HOT READ PATH

Claude/Codex hook ───────┐
OpenCode/Pi adapter ─────┼─→ local IPC
                         │     ├─ Linux Unix socket
                         │     └─ Windows named pipe
                         ▼
                  persistent daemon
                         │ read-only
                         ▼
                  SQLite + FTS5
                  DISPOSABLE INDEX
                         ▲
                         │ deterministic index
                         │
 projects/ + wiki/ + global/ Markdown
          CANONICAL MEMORY

                         BACKGROUND WRITE PATH

Harness session → thin adapter → schema-v1 normalized capture
       → bounded secret scrub → durable queue → synthesis provider
       → canonical Markdown → incremental index refresh
```

There is no TCP listener, HTTP, MCP, embedding model, vector database, graph database, cloud database, remote recall, or LLM in the recall hot path.

## 4. Linux installation behavior

**LIVE VERIFIED** in a temporary isolated home and vault:

1. `setup/install.sh` created/reused a repository virtual environment.
2. A vault with spaces and Unicode in its path was created.
3. central configuration and disposable index were created outside the vault;
4. detected harness configurations were backed up and merged;
5. repository-owned OpenCode/Pi adapters were installed;
6. a Unix-socket daemon was started for the isolated test;
7. capture, synthesis, index update, and recall passed;
8. a second install created no duplicate hook entries; and
9. uninstall removed owned integrations/state and preserved canonical Markdown.

The systemd user service template passed `systemd-analyze verify`. The production installer installs/enables `shared-memory-vault.service`; the isolated test used a direct daemon process to avoid touching the user's live systemd configuration.

## 5. Windows installation behavior

**CI VERIFIED** for package installation, shared tests, FTS5, path handling, and command availability on Windows with Python 3.11 and 3.13.

**UNIT TESTED** for the native `AF_PIPE` named-pipe client contract and Windows file-lock branch. PowerShell installer/uninstaller scripts parse successfully under PowerShell 7.

**IMPLEMENTED BUT UNVERIFIED** for a complete real Windows install, named-pipe daemon round-trip, Startup integration, Obsidian installation, harness config installation, uninstall, and local latency. No Windows latency claim is made.

## 6. Obsidian installation behavior

- **LIVE VERIFIED** detection of the existing Linux Flatpak installation.
- **IMPLEMENTED BUT UNVERIFIED** Linux absence path: user-scoped Flathub install when Flatpak is available; otherwise the official download continuation is reported.
- **IMPLEMENTED BUT UNVERIFIED** Windows absence path: `winget install --id Obsidian.Obsidian -e` with package/source agreement flags.
- Vault bootstrap never modifies unrelated vaults and requires no Obsidian plugin.

## 7. Harness integrations

| Harness | Public implementation status | Evidence |
|---|---|---|
| Claude Code | **UNIT TESTED** clean JSON merge; originating V2 **LIVE VERIFIED** | Recall and SessionEnd commands coexist with existing hooks and fail open. Extracted live install not run against personal config. |
| Codex | **LIVE VERIFIED** with a Codex-shaped isolated event; originating V2 **LIVE VERIFIED** cross-harness | Capture became canonical Markdown and was recalled through the shared core. A real disposable Codex process was not rerun after extraction. |
| OpenCode | **UNIT TESTED**, **IMPLEMENTED BUT UNVERIFIED** live | Owned plugin builds with Bun and uses OpenCode lifecycle shapes; live provider session remains pending. |
| Pi | **UNIT TESTED**, **IMPLEMENTED BUT UNVERIFIED** live | Owned extension builds with Bun and uses Pi lifecycle shapes; live provider session remains pending. |

Adapters never import into the memory core. Agent Overlay is neither required nor modified by this repository.

## 8. SQLite / FTS5 and vault

**LIVE VERIFIED**:

- schema version 1 documents include `id`, `path`, `type`, `project`, `title`, `date`, `harness`, `session_id`, `host`, `mtime`, `content_hash`, `symptoms`, `tags`, `body`, and preserved JSON metadata;
- FTS5 fields are `title`, `symptoms`, `tags`, and `body`, tokenized with `porter unicode61`;
- relation rows store `source_path`, wikilink `target`, and `resolved_path`;
- incremental, single-file, deletion cleanup, and full rebuild paths are tested;
- archive/intermediate content is excluded;
- unknown historical metadata remains unknown.

The clean vault starts with empty `projects/`, `wiki/`, and `global/` namespaces plus explanatory files. It ships no fake history.

## 9. Capture and synthesis

**LIVE VERIFIED** — A normalized Codex-shaped session containing a non-sensitive marker flowed through capture, scrubbed queue, built-in synthesis, canonical project session Markdown, index refresh, and recall. Provenance retained harness and session identity.

The default built-in provider deterministically turns normalized sessions into session notes. It does not perform expensive LLM work. The provider boundary is independent from capture/index/retrieval so a richer Claude or other synthesis provider can be added without changing memory authority or the hot path.

Capture uses atomic replacement and an OS lock. Queue items are deterministic and idempotent. Synthesis failures leave active work recoverable.

## 10. Recall and fallback

**LIVE VERIFIED** — Linux IPC and direct SQLite return the same ranked results. The recall hook attempts:

```text
local IPC → direct read-only SQLite → silent miss
```

The clean public version does not retain the personal vault's `rg` implementation because it depended on that repository's layout. A silent miss remains fail-open and never blocks the harness.

## 11. Index rebuild and recovery

**LIVE VERIFIED**:

```text
create index → snapshot ranked JSON → move database aside
→ rebuild only from Markdown → compare ranked JSON
```

The before/after ranked results were identical. `PRAGMA quick_check` returned `ok`, `foreign_key_check` returned no rows, and the rebuilt document count matched.

Recovery:

```bash
memory reindex
memory doctor
```

## 12. Security review

**LIVE VERIFIED** repository-wide and staged-file review:

- no absolute personal home paths or hostnames;
- no personal vault notes, projects, transcripts, JSONL, SQLite files, sockets, queue state, or private Git history;
- no `.env`, provider config, credential, token, cookie, or email address;
- ignored state was not relied on: every staged path and Git history were inspected;
- the only credential-shaped value is a synthetic string assembled in a scrubber test and never a real key;
- Unix socket mode was observed as 0600;
- daemon SQLite connection is query-only/read-only;
- request and response sizes, query length, project length, and result count are bounded.

Secret-pattern scrubbing is defense in depth and cannot guarantee recognition of novel credentials.

## 13. Tests and CI

Local Linux results:

- 5 Python tests passed;
- index/rebuild, FTS recall, wikilinks, unknown metadata, Unicode/space paths, secret scrubbing, capture/synthesis, provenance, Unix socket permissions, atomic/idempotent config merge, uninstall preservation, and Windows pipe contract were covered;
- both TypeScript adapters compiled with Bun;
- Python compileall, Bash syntax, PowerShell parsing, wheel build, and systemd unit verification passed.

GitHub Actions run `33095377779`: **CI VERIFIED PASS** on:

- Ubuntu, Python 3.11;
- Ubuntu, Python 3.13;
- Windows, Python 3.11; and
- Windows, Python 3.13.

The first CI run exposed an open SQLite connection tolerated by Linux but rejected by Windows. The shared synthesis code was corrected to close it explicitly; the second matrix passed.

## 14. Linux benchmark

Clean isolated repository, one synthesized document:

| Path | Samples | p50 | p95 | p99 | Result |
|---|---:|---:|---:|---:|---|
| in-process SQLite | 500 | 0.073 ms | 0.110 ms | 0.170 ms | **LIVE VERIFIED**, under 10 ms target |
| Unix socket IPC | 500 | 0.159 ms | 0.272 ms | 0.400 ms | **LIVE VERIFIED**, under 10 ms target |
| complete fresh Python hook | 100 | 72.726 ms | 89.856 ms | 97.412 ms | **LIVE VERIFIED**, misses 25 ms target |

The small clean corpus makes these results unsuitable for comparison with the 191-document personal V2 benchmark. The full hook result confirms interpreter startup remains the dominant Claude/Codex cost. No result was selectively omitted.

## 15. Windows benchmark

**NOT MEASURED.** Windows CI validates logic but is not a controlled local latency environment. The remaining requirement is a live Windows named-pipe and complete-hook benchmark.

## 16. Compatibility and removal

Configuration changes use read → parse → timestamped backup → merge owned entry → atomic validated write. Reinstall is idempotent. Existing hooks/plugins remain present. OpenCode and Pi use separate owned filenames.

Default uninstall removes owned hooks, adapters, service/startup, derived database, queue, runtime state, and configuration. It preserves the Markdown vault. `--delete-vault` is the separate explicit destructive choice.

Linux:

```bash
./setup/uninstall.sh
```

Windows:

```powershell
.\setup\uninstall.ps1
```

## 17. Known limitations and experimental capabilities

- **LIVE VERIFIED limitation:** fresh Python Claude/Codex hooks miss the full-path 25 ms target even though core IPC is well below 10 ms.
- **IMPLEMENTED BUT UNVERIFIED:** real Windows installation, pipe round-trip, service startup, Obsidian setup, and latency.
- **IMPLEMENTED BUT UNVERIFIED:** live extracted OpenCode and Pi capture/cross-recall.
- **IMPLEMENTED BUT UNVERIFIED:** live extracted Claude/Codex process-level cross-recall; the originating V2 proof remains valid, and the extracted Codex-shaped pipeline is live verified.
- Built-in synthesis writes factual session notes but does not perform LLM cross-project wiki synthesis.
- Frontmatter parsing intentionally supports flat top-level values, not arbitrary nested YAML.
- Lexical retrieval depends on the words present in title, symptoms, tags, and body.

## 18. Installation command

```bash
git clone https://github.com/MaheshBhushan/shared-memory-vault.git
cd shared-memory-vault
./setup/install.sh
```

Windows uses `.\setup\install.ps1` after the same clone.

## 19. Recommended next milestones

1. Run the isolated installer and named-pipe daemon on a real Windows machine; record IPC and hook latency.
2. Run real extracted Claude ↔ Codex cross-process capture/recall without touching the personal vault.
3. Run live OpenCode and Pi session capture, synthesis, and cross-harness recall.
4. Replace the fresh Python Claude/Codex hook wrapper with a measured tiny native client only if those harnesses cannot provide a resident hook surface.
5. Add an optional Claude synthesis provider for higher-quality wiki consolidation while preserving the deterministic built-in fallback.
6. Expand quality evaluation with a public, non-personal corpus; retain complexity only when hit@1/hit@3 measurements improve.

No `1.0` claim is appropriate until both platforms and all claimed harness paths are live verified.
