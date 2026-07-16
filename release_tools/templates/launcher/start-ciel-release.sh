#!/bin/zsh
set -u

export PATH="/usr/bin:/bin:/usr/sbin:/sbin"

BIN_DIR="$(cd "$(dirname "$0")" && /bin/pwd -P)"
APP_ROOT="$(cd "$BIN_DIR/.." && /bin/pwd -P)"
INSTALL_ROOT="$(cd "$BIN_DIR/../../.." && /bin/pwd -P)"
DATA_ROOT="$INSTALL_ROOT/UserData"
SERVER="$BIN_DIR/ciel-server/ciel-server"
RELEASE_JSON="$APP_ROOT/release.json"
PORT="3015"
LOG_DIR="$DATA_ROOT/logs"
RUNTIME_DIR="$DATA_ROOT/runtime"
LOG_FILE="$LOG_DIR/ciel-server.log"
LAUNCH_LOG="$LOG_DIR/start-ciel-release.log"
PID_FILE="$RUNTIME_DIR/ciel-server.pid"
HEALTH_ELAPSED_SECONDS="0"

finish() {
  local result="$1"
  print -r -- "HEALTH_ELAPSED_SECONDS=$HEALTH_ELAPSED_SECONDS"
  print -r -- "FINAL_RESULT=$result"
  # The AppleScript wrapper parses FINAL_RESULT and presents a precise
  # diagnostic dialog; keep the shell process successful so that output is
  # preserved across `do shell script`.
  exit 0
}

log_line() {
  /bin/mkdir -p "$LOG_DIR"
  print -r -- "$(/bin/date '+%Y-%m-%d %H:%M:%S') $1" >> "$LAUNCH_LOG"
}

json_raw() {
  # release.json is UTF-8 JSON, not a property-list. Keep the launcher
  # dependency-free on macOS by extracting the scalar fields we own.
  /usr/bin/sed -nE "s/^[[:space:]]*\"$1\"[[:space:]]*:[[:space:]]*\"([^\"]*)\".*$/\1/p" "$2" | /usr/bin/head -n 1
}

read_health() {
  /usr/bin/curl -fsS --max-time 2 "http://127.0.0.1:$PORT/api/app-info" 2>/dev/null || true
}

extract_version() {
  local payload="$1"
  local pattern='"version"[[:space:]]*:[[:space:]]*"([^"]+)"'
  if [[ "$payload" =~ $pattern ]]; then
    print -r -- "$match[1]"
  fi
}

port_is_listening() {
  /usr/sbin/lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1
}

owned_service_pid() {
  local pid=""
  local command_line=""
  [[ -f "$PID_FILE" ]] || return 1
  pid="$(/usr/bin/tr -cd '0-9' < "$PID_FILE")"
  [[ -n "$pid" ]] || return 1
  /bin/kill -0 "$pid" >/dev/null 2>&1 || return 1
  /usr/sbin/lsof -nP -a -p "$pid" -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || return 1
  command_line="$(/bin/ps -ww -p "$pid" -o command= 2>/dev/null || true)"
  [[ "$command_line" == *"$SERVER"* ]] || return 1
  print -r -- "$pid"
}

if [[ ! -f "$RELEASE_JSON" || ! -x "$SERVER" ]]; then
  log_line "FINAL_RESULT=RELEASE_INCOMPLETE"
  finish "RELEASE_INCOMPLETE"
fi

PRODUCT_ID="$(json_raw product_id "$RELEASE_JSON")"
EXPECTED_VERSION="$(json_raw internal_build "$RELEASE_JSON")"
if [[ "$PRODUCT_ID" != "local.ciel.canvas" || -z "$EXPECTED_VERSION" ]]; then
  log_line "FINAL_RESULT=RELEASE_METADATA_INVALID"
  finish "RELEASE_METADATA_INVALID"
fi

/bin/mkdir -p "$DATA_ROOT" "$LOG_DIR" "$RUNTIME_DIR" "$RUNTIME_DIR/temp" "$RUNTIME_DIR/home" "$RUNTIME_DIR/cache"
/bin/chmod 700 "$DATA_ROOT" "$LOG_DIR" "$RUNTIME_DIR" "$RUNTIME_DIR/temp" "$RUNTIME_DIR/home" "$RUNTIME_DIR/cache" 2>/dev/null || true

HEALTH="$(read_health)"
ACTUAL_VERSION="$(extract_version "$HEALTH")"
if [[ "$ACTUAL_VERSION" == "$EXPECTED_VERSION" ]]; then
  OWNED_PID="$(owned_service_pid || true)"
  if [[ -n "$OWNED_PID" ]]; then
    log_line "PID=$OWNED_PID HEALTH=REUSE VERSION=$ACTUAL_VERSION FINAL_RESULT=SUCCESS"
    /usr/bin/open "http://127.0.0.1:$PORT" >/dev/null 2>&1 || true
    finish "SUCCESS"
  fi
  log_line "PORT=$PORT SAME_VERSION_NOT_OWNED FINAL_RESULT=PORT_OCCUPIED"
  finish "PORT_OCCUPIED"
fi

if port_is_listening; then
  if [[ -n "$(owned_service_pid || true)" ]]; then
    log_line "PORT=$PORT OWNED_VERSION_MISMATCH ACTUAL=$ACTUAL_VERSION FINAL_RESULT=VERSION_MISMATCH"
    finish "VERSION_MISMATCH"
  fi
  log_line "PORT=$PORT FINAL_RESULT=PORT_OCCUPIED"
  finish "PORT_OCCUPIED"
fi

log_line "START INTERNAL_BUILD=$EXPECTED_VERSION PORT=$PORT"
(
  export CIEL_PORTABLE=1
  export CIEL_INSTALL_ROOT="$INSTALL_ROOT"
  export CIEL_APP_ROOT="$APP_ROOT"
  export CIEL_DATA_ROOT="$DATA_ROOT"
  export HOME="$RUNTIME_DIR/home"
  export TMPDIR="$RUNTIME_DIR/temp"
  export TMP="$TMPDIR"
  export TEMP="$TMPDIR"
  export XDG_CACHE_HOME="$RUNTIME_DIR/cache"
  export PYTHONPYCACHEPREFIX="$RUNTIME_DIR/cache/pycache"
  export PYTHONDONTWRITEBYTECODE=1
  export PORT="$PORT"
  cd "$APP_ROOT" || exit 91
  /usr/bin/nohup "$SERVER" >> "$LOG_FILE" 2>&1 </dev/null &
  print -r -- "$!" > "$PID_FILE"
)

PID="$(/usr/bin/tr -cd '0-9' < "$PID_FILE" 2>/dev/null || true)"
if [[ -z "$PID" ]]; then
  log_line "FINAL_RESULT=PROCESS_EXITED"
  finish "PROCESS_EXITED"
fi

for attempt in {1..120}; do
  if ! /bin/kill -0 "$PID" >/dev/null 2>&1; then
    HEALTH_ELAPSED_SECONDS="$(( (attempt - 1) / 2 ))"
    log_line "PID=$PID FINAL_RESULT=PROCESS_EXITED"
    finish "PROCESS_EXITED"
  fi
  HEALTH="$(read_health)"
  ACTUAL_VERSION="$(extract_version "$HEALTH")"
  if [[ "$ACTUAL_VERSION" == "$EXPECTED_VERSION" ]]; then
    HEALTH_ELAPSED_SECONDS="$(( (attempt - 1) / 2 ))"
    log_line "PID=$PID HEALTH=PASS VERSION=$ACTUAL_VERSION FINAL_RESULT=SUCCESS"
    /usr/bin/open "http://127.0.0.1:$PORT" >/dev/null 2>&1 || true
    finish "SUCCESS"
  fi
  /bin/sleep 0.5
done

HEALTH_ELAPSED_SECONDS="60"
log_line "PID=$PID FINAL_RESULT=HEALTH_TIMEOUT"
finish "HEALTH_TIMEOUT"
