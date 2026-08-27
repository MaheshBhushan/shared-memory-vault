import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from agent_memory.config import defaults, save
from agent_memory.index import connect, update
from agent_memory.ipc import recall


@unittest.skipIf(os.name == "nt", "Unix socket live test")
class DaemonTest(unittest.TestCase):
    def test_unix_socket(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); config = defaults()
            config.vault_path = str(root / "vault"); config.state_path = str(root / "state"); config.endpoint = str(root / "runtime/memory.sock")
            (config.vault / "wiki").mkdir(parents=True); (config.vault / "projects").mkdir(); (config.vault / "global").mkdir()
            (config.vault / "wiki/test.md").write_text("# Test\nCopper narwhal memory.\n")
            config_path = root / "config.json"; save(config, config_path)
            with closing(connect(config.database)) as db: update(db, config.vault, rebuild=True)
            env = dict(os.environ, SHARED_MEMORY_CONFIG=str(config_path))
            process = subprocess.Popen([sys.executable, "-m", "agent_memory", "daemon"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                for _ in range(200):
                    try:
                        hits = recall(config.endpoint, "copper narwhal"); break
                    except (FileNotFoundError, ConnectionRefusedError): time.sleep(.01)
                else: self.fail(process.stderr.read().decode())
                self.assertEqual("wiki/test.md", hits[0]["path"])
                self.assertEqual(0o600, Path(config.endpoint).stat().st_mode & 0o777)
            finally:
                process.terminate(); process.wait(timeout=3)
                process.stderr.close()


if __name__ == "__main__": unittest.main()
