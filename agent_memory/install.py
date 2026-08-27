"""Idempotent installer with atomic, backed-up harness configuration merges."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .config import Config, default_config_path, defaults, save
from .index import connect, update

MARKER = "shared-memory-vault"


def _backup(path: Path) -> Path | None:
    if not path.exists(): return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.{MARKER}.{stamp}.bak")
    shutil.copy2(path, backup)
    return backup


def _atomic_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    json.loads(temporary.read_text())
    os.replace(temporary, path)


def merge_json_hook(path: Path, event: str, command: str, timeout=5) -> bool:
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    hooks = data.setdefault("hooks", {}).setdefault(event, [])
    group = hooks[0] if hooks else {"hooks": []}
    if not hooks: hooks.append(group)
    entries = group.setdefault("hooks", [])
    if any(MARKER in str(entry.get("command", "")) for entry in entries):
        return False
    _backup(path)
    entries.append({"type": "command", "command": command, "timeout": timeout})
    _atomic_json(path, data)
    return True


def remove_json_hooks(path: Path):
    if not path.exists(): return False
    data = json.loads(path.read_text(encoding="utf-8")); changed = False
    for groups in data.get("hooks", {}).values():
        for group in groups:
            old = group.get("hooks", [])
            group["hooks"] = [entry for entry in old if MARKER not in str(entry.get("command", ""))]
            changed |= len(old) != len(group["hooks"])
    if changed:
        _backup(path); _atomic_json(path, data)
    return changed


def detect_harnesses(home=Path.home()):
    definitions = {
        "claude": (shutil.which("claude"), home / ".claude/settings.json"),
        "codex": (shutil.which("codex"), home / ".codex/hooks.json"),
        "opencode": (shutil.which("opencode"), home / ".config/opencode"),
        "pi": (shutil.which("pi"), home / ".pi/agent"),
    }
    return {name: bool(binary or config.exists()) for name, (binary, config) in definitions.items()}


def obsidian_status():
    if shutil.which("obsidian"): return "detected"
    if shutil.which("flatpak") and subprocess.run(["flatpak", "info", "md.obsidian.Obsidian"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0: return "detected"
    if os.name == "nt" and shutil.which("winget"):
        result = subprocess.run(["winget", "list", "--id", "Obsidian.Obsidian", "-e"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0: return "detected"
    return "missing"


def install_obsidian(execute=True):
    if obsidian_status() == "detected": return "detected"
    if not execute: return "would install"
    if os.name == "nt" and shutil.which("winget"):
        subprocess.run(["winget", "install", "--id", "Obsidian.Obsidian", "-e",
                        "--accept-package-agreements", "--accept-source-agreements"], check=True)
        return "installed"
    if shutil.which("flatpak"):
        subprocess.run(["flatpak", "install", "--user", "-y", "flathub", "md.obsidian.Obsidian"], check=True)
        return "installed"
    return "manual: install from https://obsidian.md/download, then rerun setup"


def bootstrap_vault(vault: Path):
    for directory in ("projects", "wiki", "global"):
        (vault / directory).mkdir(parents=True, exist_ok=True)
    readme = vault / "README.md"
    if not readme.exists():
        readme.write_text("# Agent Memory\n\nCanonical shared memory. Browse and edit with Obsidian.\n", encoding="utf-8")


def _python_command(action, harness=None):
    args = [str(Path(sys.executable)), "-m", "agent_memory.adapters.common", action]
    if harness: args.append(harness)
    # JSON hook formats execute through a shell; quote every component safely.
    if os.name == "nt":
        return subprocess.list2cmdline(args) + f" & rem {MARKER}"
    import shlex
    return " ".join(shlex.quote(part) for part in args) + f" # {MARKER}"


def install_adapters(config: Config, home=Path.home(), source_root=None):
    detected = detect_harnesses(home); enabled = []
    for name in ("claude", "codex"):
        if detected[name]:
            path = home / (".claude/settings.json" if name == "claude" else ".codex/hooks.json")
            merge_json_hook(path, "UserPromptSubmit", _python_command("recall"), 5)
            merge_json_hook(path, "SessionEnd", _python_command("capture", name), 3)
            enabled.append(name)
    root = source_root or Path(os.environ.get("SHARED_MEMORY_SOURCE_ROOT", Path(__file__).resolve().parents[1]))
    for name, target in (("opencode", home / ".config/opencode/plugin/shared-memory.ts"),
                         ("pi", home / ".pi/agent/extensions/shared-memory.ts")):
        if detected[name]:
            source = root / f"adapters/{name}/shared-memory.ts"
            text = source.read_text(encoding="utf-8").replace("__PYTHON__", str(Path(sys.executable)).replace("\\", "\\\\"))
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_text(encoding="utf-8") != text: _backup(target)
            temporary = target.with_suffix(".tmp"); temporary.write_text(text, encoding="utf-8"); os.replace(temporary, target)
            enabled.append(name)
    config.enabled_adapters = enabled
    return detected


def install_service(config: Config, source_root=None):
    root = source_root or Path(__file__).resolve().parents[1]
    if os.name == "nt":
        startup = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "Microsoft/Windows/Start Menu/Programs/Startup/shared-memory-vault.cmd"
        startup.parent.mkdir(parents=True, exist_ok=True)
        startup.write_text(f'@echo off\r\n"{sys.executable}" -m agent_memory daemon\r\n', encoding="utf-8")
        subprocess.Popen([sys.executable, "-m", "agent_memory", "daemon"], creationflags=0x08000000)
        return startup
    service = Path.home() / ".config/systemd/user/shared-memory-vault.service"
    service.parent.mkdir(parents=True, exist_ok=True)
    content = ("[Unit]\nDescription=Shared Memory Vault\nAfter=default.target\n\n[Service]\n"
               f"Type=simple\nExecStart={json.dumps(sys.executable)} -m agent_memory daemon\nRestart=on-failure\n"
               "RestartSec=1\nUMask=0077\n\n[Install]\nWantedBy=default.target\n")
    service.write_text(content, encoding="utf-8")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", service.name], check=True)
    return service


def uninstall(config: Config, home=Path.home(), keep_vault=True):
    remove_json_hooks(home / ".claude/settings.json"); remove_json_hooks(home / ".codex/hooks.json")
    for path in (home / ".config/opencode/plugin/shared-memory.ts", home / ".pi/agent/extensions/shared-memory.ts"):
        path.unlink(missing_ok=True)
    if os.name == "nt":
        startup = Path(os.environ.get("APPDATA", home / "AppData/Roaming")) / "Microsoft/Windows/Start Menu/Programs/Startup/shared-memory-vault.cmd"
        startup.unlink(missing_ok=True)
    else:
        subprocess.run(["systemctl", "--user", "disable", "--now", "shared-memory-vault.service"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (home / ".config/systemd/user/shared-memory-vault.service").unlink(missing_ok=True)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(config.state, ignore_errors=True)
    default_config_path().unlink(missing_ok=True)
    if not keep_vault: shutil.rmtree(config.vault)
