"""Deterministically derive an FTS5 index from canonical Markdown."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

CANONICAL_DIRS = ("projects", "wiki", "global")
LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS documents(
 id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, type TEXT, project TEXT,
 title TEXT NOT NULL, date TEXT, harness TEXT, session_id TEXT, host TEXT,
 mtime INTEGER NOT NULL, content_hash TEXT NOT NULL, symptoms TEXT, tags TEXT,
 body TEXT NOT NULL, metadata TEXT NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
 title,symptoms,tags,body,content='documents',content_rowid='id',
 tokenize='porter unicode61');
CREATE TABLE IF NOT EXISTS links(source_path TEXT NOT NULL,target TEXT NOT NULL,
 resolved_path TEXT,FOREIGN KEY(source_path) REFERENCES documents(path) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS links_source_idx ON links(source_path);
CREATE INDEX IF NOT EXISTS links_target_idx ON links(target);
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
 INSERT INTO documents_fts(rowid,title,symptoms,tags,body)
 VALUES(new.id,new.title,new.symptoms,new.tags,new.body); END;
CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
 INSERT INTO documents_fts(documents_fts,rowid,title,symptoms,tags,body)
 VALUES('delete',old.id,old.title,old.symptoms,old.tags,old.body); END;
CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE OF title,symptoms,tags,body ON documents BEGIN
 INSERT INTO documents_fts(documents_fts,rowid,title,symptoms,tags,body)
 VALUES('delete',old.id,old.title,old.symptoms,old.tags,old.body);
 INSERT INTO documents_fts(rowid,title,symptoms,tags,body)
 VALUES(new.id,new.title,new.symptoms,new.tags,new.body); END;
PRAGMA user_version=1;
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    return db


def canonical_files(vault: Path):
    for directory in CANONICAL_DIRS:
        root = vault / directory
        if root.is_dir():
            yield from sorted(root.rglob("*.md"))


def _value(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if value.startswith("[") and value.endswith("]"):
        return [part.strip().strip("\"'") for part in value[1:-1].split(",") if part.strip()]
    return value or None


def parse_markdown(path: Path):
    raw = path.read_text(encoding="utf-8", errors="replace")
    metadata, body = {}, raw
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end >= 0:
            for line in raw[4:end].splitlines():
                if ":" in line and line and not line[0].isspace():
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = _value(value)
            body = raw[end + 5:]
    heading = re.search(r"^#\s+(.+?)\s*$", body, re.MULTILINE)
    title = metadata.get("title") or (heading.group(1) if heading else path.stem)
    tags = metadata.get("tags")
    return metadata, str(title), body, " ".join(map(str, tags)) if isinstance(tags, list) else str(tags or "")


def _relative(vault: Path, path: Path) -> str:
    resolved = path.resolve()
    relative = resolved.relative_to(vault.resolve())
    if relative.parts[0] not in CANONICAL_DIRS or resolved.suffix.lower() != ".md":
        raise ValueError(f"not canonical vault Markdown: {path}")
    return relative.as_posix()


def _index_file(db, vault: Path, path: Path) -> str:
    relative = _relative(vault, path)
    if not path.exists():
        db.execute("DELETE FROM documents WHERE path=?", (relative,))
        return "deleted"
    mtime = path.stat().st_mtime_ns
    previous = db.execute("SELECT mtime,content_hash FROM documents WHERE path=?", (relative,)).fetchone()
    if previous and previous["mtime"] == mtime:
        return "unchanged"
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if previous and previous["content_hash"] == digest:
        db.execute("UPDATE documents SET mtime=? WHERE path=?", (mtime, relative))
        return "unchanged"
    meta, title, body, tags = parse_markdown(path)
    values = (relative, meta.get("type"), meta.get("project"), title, meta.get("date"),
              meta.get("harness"), meta.get("session_id"), meta.get("host"), mtime,
              digest, meta.get("symptoms"), tags, body,
              json.dumps(meta, ensure_ascii=False, sort_keys=True))
    db.execute("""INSERT INTO documents(path,type,project,title,date,harness,session_id,host,
      mtime,content_hash,symptoms,tags,body,metadata) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(path) DO UPDATE SET type=excluded.type,project=excluded.project,
      title=excluded.title,date=excluded.date,harness=excluded.harness,
      session_id=excluded.session_id,host=excluded.host,mtime=excluded.mtime,
      content_hash=excluded.content_hash,symptoms=excluded.symptoms,tags=excluded.tags,
      body=excluded.body,metadata=excluded.metadata""", values)
    db.execute("DELETE FROM links WHERE source_path=?", (relative,))
    db.executemany("INSERT INTO links(source_path,target) VALUES(?,?)",
                   ((relative, value.split("|", 1)[0].strip()) for value in LINK_RE.findall(body)
                    if value.split("|", 1)[0].strip()))
    return "indexed"


def _resolve_links(db):
    exact, names = {}, {}
    for row in db.execute("SELECT path,metadata FROM documents"):
        path, stem = row["path"], row["path"][:-3]
        exact[stem.casefold()] = path
        names.setdefault(Path(stem).name.casefold(), set()).add(path)
        if path.startswith("projects/") and path.endswith("/overview.md"):
            names.setdefault(path.split("/", 2)[1].casefold(), set()).add(path)
        aliases = json.loads(row["metadata"]).get("aliases", [])
        for alias in aliases if isinstance(aliases, list) else [aliases]:
            if alias:
                names.setdefault(str(alias).casefold(), set()).add(path)
    def resolve(source, target):
        target = target.split("#", 1)[0].split("^", 1)[0].strip()
        target = target[:-3] if target.lower().endswith(".md") else target
        if target.casefold() in exact:
            return exact[target.casefold()]
        relative = (Path(source).parent / target).as_posix().casefold()
        if relative in exact:
            return exact[relative]
        matches = names.get(Path(target).name.casefold(), set())
        return next(iter(matches)) if len(matches) == 1 else None
    db.executemany("UPDATE links SET resolved_path=? WHERE rowid=?",
                   ((resolve(row["source_path"], row["target"]), row["rowid"])
                    for row in db.execute("SELECT rowid,* FROM links")))


def update(db, vault: Path, rebuild=False, only: Path | None = None):
    vault = vault.resolve()
    counts = {"indexed": 0, "unchanged": 0, "deleted": 0}
    if rebuild:
        db.execute("DELETE FROM documents")
    if only:
        path = only if only.is_absolute() else vault / only
        counts[_index_file(db, vault, path)] += 1
    else:
        files = list(canonical_files(vault))
        present = {_relative(vault, path) for path in files}
        for path in files:
            counts[_index_file(db, vault, path)] += 1
        stale = [row[0] for row in db.execute("SELECT path FROM documents") if row[0] not in present]
        db.executemany("DELETE FROM documents WHERE path=?", ((path,) for path in stale))
        counts["deleted"] += len(stale)
    _resolve_links(db)
    db.commit()
    counts.update(documents=db.execute("SELECT count(*) FROM documents").fetchone()[0],
                  links=db.execute("SELECT count(*) FROM links").fetchone()[0],
                  resolved_links=db.execute("SELECT count(*) FROM links WHERE resolved_path IS NOT NULL").fetchone()[0])
    return counts
