import json
import tempfile
import unittest
from pathlib import Path

from agent_memory.install import merge_json_hook, remove_json_hooks


class InstallTest(unittest.TestCase):
    def test_atomic_idempotent_merge_and_remove(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({"theme": "dark", "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "existing"}]}]}}))
            command = "python -m agent_memory.adapters.common recall # shared-memory-vault"
            self.assertTrue(merge_json_hook(path, "UserPromptSubmit", command))
            self.assertFalse(merge_json_hook(path, "UserPromptSubmit", command))
            data = json.loads(path.read_text())
            self.assertEqual("dark", data["theme"])
            self.assertEqual(2, len(data["hooks"]["UserPromptSubmit"][0]["hooks"]))
            self.assertTrue(remove_json_hooks(path))
            self.assertEqual(["existing"], [x["command"] for x in json.loads(path.read_text())["hooks"]["UserPromptSubmit"][0]["hooks"]])


if __name__ == "__main__": unittest.main()
