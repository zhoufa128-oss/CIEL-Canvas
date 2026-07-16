#!/bin/zsh
set -u

export PATH="/usr/bin:/bin:/usr/sbin:/sbin"
HELP_DIR="$(cd "$(dirname "$0")" && /bin/pwd -P)"
INSTALL_ROOT="$(cd "$HELP_DIR/.." && /bin/pwd -P)"
APP_ROOT="$INSTALL_ROOT/Application/current"
DATA_ROOT="$INSTALL_ROOT/UserData"
SERVER="$APP_ROOT/bin/ciel-server/ciel-server"
RUNTIME_DIR="$DATA_ROOT/runtime"

if [[ ! -x "$SERVER" ]]; then
  print -r -- "CIEL Canvas 运行时不存在。"
  exit 1
fi

/bin/mkdir -p "$DATA_ROOT/diagnostics" "$RUNTIME_DIR/temp" "$RUNTIME_DIR/home" "$RUNTIME_DIR/cache"
OUTPUT="$(CIEL_PORTABLE=1 \
  CIEL_INSTALL_ROOT="$INSTALL_ROOT" \
  CIEL_APP_ROOT="$APP_ROOT" \
  CIEL_DATA_ROOT="$DATA_ROOT" \
  HOME="$RUNTIME_DIR/home" \
  TMPDIR="$RUNTIME_DIR/temp" \
  XDG_CACHE_HOME="$RUNTIME_DIR/cache" \
  "$SERVER" --export-diagnostics 2>&1)"
STATUS=$?
print -r -- "$OUTPUT"
if [[ "$STATUS" -eq 0 ]]; then
  /usr/bin/open "$DATA_ROOT/diagnostics" >/dev/null 2>&1 || true
fi
exit "$STATUS"
