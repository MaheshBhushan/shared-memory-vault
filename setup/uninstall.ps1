$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
& (Join-Path $Root ".venv\Scripts\memory.exe") uninstall @args
