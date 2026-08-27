#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
command -v "$PYTHON" >/dev/null || { echo "Python 3.11+ is required." >&2; exit 1; }
"$PYTHON" -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ is required"'
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then "$PYTHON" -m venv "$ROOT/.venv"; fi
"$ROOT/.venv/bin/python" -m pip install --disable-pip-version-check -q "$ROOT"
export SHARED_MEMORY_SOURCE_ROOT="$ROOT"
exec "$ROOT/.venv/bin/memory" install "$@"
