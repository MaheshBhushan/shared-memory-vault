import unittest
from unittest.mock import patch

from agent_memory import ipc


class WindowsContractTest(unittest.TestCase):
    def test_named_pipe_client_contract(self):
        class Fake:
            def send_bytes(self, value): self.sent = value
            def recv_bytes(self, _): return b'{"ok":true,"results":[]}'
            def close(self): pass
        fake = Fake()
        with patch.object(ipc.os, "name", "nt"), patch.object(ipc, "Client", return_value=fake) as client:
            self.assertEqual([], ipc.recall(r"\\.\pipe\shared-memory-vault", "test query"))
            client.assert_called_once_with(r"\\.\pipe\shared-memory-vault", family="AF_PIPE", authkey=ipc.PIPE_AUTHKEY)


if __name__ == "__main__": unittest.main()
