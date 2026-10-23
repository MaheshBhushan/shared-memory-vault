import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from agent_memory.capture import capture, normalize
from agent_memory.config import defaults, load, save
from agent_memory.index import connect, update
from agent_memory.retrieval import recall
from agent_memory.synthesis import process_queue


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = defaults()
        self.config.vault_path = str(self.root / "Vault with ünicode")
        self.config.state_path = str(self.root / "State with spaces")
        for name in ("projects/demo", "wiki", "global", "archive"):
            (self.config.vault / name).mkdir(parents=True)
        (self.config.vault / "projects/demo/overview.md").write_text(
            "---\ntype: project\nproject: demo\nsymptoms: 'speaker output'\ntags: [audio]\ncustom: kept\n---\n# Demo\nRoute sound. [[audio-routing|details]]\n", encoding="utf-8")
        (self.config.vault / "wiki/audio-routing.md").write_text("# Audio routing\nUse the speaker. [[demo]]\n", encoding="utf-8")
        (self.config.vault / "archive/private.md").write_text("# Never indexed\n", encoding="utf-8")

    def tearDown(self): self.temp.cleanup()

    def test_index_recall_links_and_disposable_rebuild(self):
        with closing(connect(self.config.database)) as db:
            first = update(db, self.config.vault, rebuild=True)
            before = [(row["path"], row["content_hash"]) for row in db.execute("SELECT path,content_hash FROM documents ORDER BY path")]
            hits = recall(db, "speaker output")
            self.assertEqual(2, first["documents"])
            self.assertEqual("projects/demo/overview.md", hits[0]["path"])
            self.assertEqual(2, first["resolved_links"])
        self.config.database.unlink()
        with closing(connect(self.config.database)) as db:
            update(db, self.config.vault, rebuild=True)
            after = [(row["path"], row["content_hash"]) for row in db.execute("SELECT path,content_hash FROM documents ORDER BY path")]
            self.assertEqual(before, after)
            self.assertEqual([h["path"] for h in hits], [h["path"] for h in recall(db, "speaker output")])

    def test_capture_synthesis_provenance_and_scrub(self):
        with closing(connect(self.config.database)) as db: update(db, self.config.vault, rebuild=True)
        token = "sk-" + "x" * 40
        item = capture(self.config, normalize(harness="codex", session_id="s-1", cwd=str(self.root / "my project"), prompts=[f"Remember teal. token={token}"], final_response="Teal chosen."))
        self.assertNotIn(token, item.read_text())
        self.assertEqual(1, process_queue(self.config))
        note = next((self.config.vault / "projects/my-project/sessions").glob("*.md"))
        self.assertIn('harness: "codex"', note.read_text())
        with closing(sqlite3.connect(self.config.database)) as db:
            db.row_factory = sqlite3.Row
            self.assertEqual(note.relative_to(self.config.vault).as_posix(), recall(db, "teal chosen")[0]["path"])

    def test_runbook_resolution_requires_review_and_sources(self):
        approved = self.config.vault / "wiki/approved-runbook.md"
        approved.write_text('''---
type: runbook
review_status: reviewed
symptoms: "printer offline"
cause: "stale spool queue"
resolution: "restart the print spooler"
escalation_boundary: "Escalate if the queue returns after restart."
source_links: ["https://docs.example/spooler"]
---
# Printer support runbook
Confirm the queue state. See [vendor guidance](https://vendor.example/printer).
''', encoding="utf-8")
        unreviewed = self.config.vault / "wiki/unreviewed-runbook.md"
        unreviewed.write_text('''---
type: runbook
review_status: draft
symptoms: "scanner offline"
cause: "expired scanner lease"
resolution: "renew the lease"
escalation_boundary: "Escalate if renewal fails."
source_links: ["https://docs.example/scanner"]
---
# Scanner support runbook
''', encoding="utf-8")
        unsourced = self.config.vault / "wiki/unsourced-runbook.md"
        unsourced.write_text('''---
type: runbook
review_status: reviewed
symptoms: "router disconnected"
resolution: "reboot the router"
---
# Router support runbook
''', encoding="utf-8")
        with closing(connect(self.config.database)) as db:
            update(db, self.config.vault, rebuild=True)
            printer = recall(db, "printer offline")[0]
            scanner = recall(db, "scanner offline")[0]
            router = recall(db, "router disconnected")[0]
        self.assertEqual("restart the print spooler", printer["resolution"])
        self.assertEqual("stale spool queue", printer["cause"])
        self.assertEqual("Escalate if the queue returns after restart.", printer["escalation_boundary"])
        self.assertIn("https://docs.example/spooler", printer["source_links"])
        self.assertIn("https://vendor.example/printer", printer["source_links"])
        self.assertIsNone(scanner["resolution"])
        self.assertIn("https://docs.example/scanner", scanner["source_links"])
        self.assertIsNone(router["resolution"])

    def test_index_upgrade_reindexes_existing_documents(self):
        with closing(connect(self.config.database)) as db:
            update(db, self.config.vault, rebuild=True)
        with closing(sqlite3.connect(self.config.database)) as db:
            db.execute("PRAGMA user_version=1")
        with closing(connect(self.config.database)) as db:
            counts = update(db, self.config.vault)
            self.assertEqual(2, counts["indexed"])
            self.assertEqual(2, db.execute("PRAGMA user_version").fetchone()[0])


if __name__ == "__main__": unittest.main()
