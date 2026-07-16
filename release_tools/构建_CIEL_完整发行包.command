#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && /bin/pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/../.." && /bin/pwd -P)"

PYTHON_BIN="${CIEL_PYTHON:-$(/usr/bin/command -v python3 || true)}"
if [[ -z "$PYTHON_BIN" ]]; then
  print -u2 -- "Python 3 is required. Install it (for example with Homebrew) and retry."
  exit 2
fi
exec "$PYTHON_BIN" "$ROOT/Build/build_macos_arm64_release.py" "$@"
