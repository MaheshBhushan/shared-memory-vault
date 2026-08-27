"""Central, cross-platform configuration."""

from __future__ import annotations

import json
import os
import platform
import socket
from dataclasses import asdict, dataclass
from pathlib import Path


def _home() -> Path:
    return Path.home()


def default_config_path() -> Path:
    override = os.environ.get("SHARED_MEMORY_CONFIG")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", _home() / "AppData/Roaming")) / "SharedMemoryVault/config.json"
    return Path(os.environ.get("XDG_CONFIG_HOME", _home() / ".config")) / "shared-memory-vault/config.json"


@dataclass(slots=True)
class Config:
    vault_path: str
    state_path: str
    runtime_path: str
    endpoint: str
    host_identifier: str
    enabled_adapters: list[str]
    synthesis_provider: str = "builtin"

    @property
    def vault(self) -> Path:
        return Path(self.vault_path).expanduser()

    @property
    def state(self) -> Path:
        return Path(self.state_path).expanduser()

    @property
    def database(self) -> Path:
        return self.state / "memory.db"


def defaults() -> Config:
    if os.name == "nt":
        data = Path(os.environ.get("LOCALAPPDATA", _home() / "AppData/Local")) / "SharedMemoryVault"
        vault = _home() / "Documents/AgentMemory"
        endpoint = r"\\.\pipe\shared-memory-vault"
    else:
        data = Path(os.environ.get("XDG_STATE_HOME", _home() / ".local/state")) / "shared-memory-vault"
        vault = _home() / "Documents/AgentMemory"
        runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/shared-memory-{os.getuid()}"))
        endpoint = str(runtime / "shared-memory-vault.sock")
    return Config(str(vault), str(data), str(data / "runtime"), endpoint,
                  socket.gethostname(), [], "builtin")


def load(path: Path | None = None) -> Config:
    path = path or default_config_path()
    if not path.exists():
        return defaults()
    base = asdict(defaults())
    base.update(json.loads(path.read_text(encoding="utf-8")))
    return Config(**base)


def save(config: Config, path: Path | None = None) -> Path:
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    if os.name != "nt":
        path.chmod(0o600)
    return path


def platform_name() -> str:
    return "Windows" if os.name == "nt" else platform.system()
