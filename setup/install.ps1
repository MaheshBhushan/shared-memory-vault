$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { throw "Python 3.11+ is required. Install it with: winget install Python.Python.3.12" }
if (-not (Test-Path (Join-Path $Root ".venv\Scripts\python.exe"))) { & $Python -m venv (Join-Path $Root ".venv") }
& (Join-Path $Root ".venv\Scripts\python.exe") -m pip install --disable-pip-version-check -q $Root
$env:SHARED_MEMORY_SOURCE_ROOT = $Root
& (Join-Path $Root ".venv\Scripts\memory.exe") install @args
