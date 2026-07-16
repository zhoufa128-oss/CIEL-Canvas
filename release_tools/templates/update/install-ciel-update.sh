#!/bin/zsh
set -u

export PATH="/usr/bin:/bin:/usr/sbin:/sbin"

SCRIPT_DIR="$(cd "$(dirname "$0")" && /bin/pwd -P)"
UPDATE_ROOT="$(cd "$SCRIPT_DIR/../../.." && /bin/pwd -P)"
UPDATE_PLIST="$UPDATE_ROOT/update.plist"
MANIFEST="$UPDATE_ROOT/SHA256SUMS.txt"
PAYLOAD_CURRENT="$UPDATE_ROOT/payload/Application/current"
TEST_PORT="${CIEL_UPDATE_TEST_PORT:-}"
FORCE_HEALTH_FAIL="${CIEL_UPDATE_FORCE_HEALTH_FAIL:-0}"

finish() {
  print -r -- "FINAL_RESULT=$1"
  exit "${2:-0}"
}

plist_raw() {
  /usr/bin/plutil -extract "$1" raw -o - "$2" 2>/dev/null || true
}

sha256_file() {
  /usr/bin/shasum -a 256 "$1" | /usr/bin/awk '{print $1}'
}

semver_in_range() {
  local version="${1%%-*}"
  local minimum="${2%%-*}"
  local maximum="${3%%-*}"
  /usr/bin/awk -v version="$version" -v minimum="$minimum" -v maximum="$maximum" '
    function valid(value) { return value ~ /^[0-9]+\.[0-9]+\.[0-9]+$/ }
    function greater_or_equal(a, b, av, bv, i) {
      split(a, av, "."); split(b, bv, ".")
      for (i = 1; i <= 3; i++) {
        if ((av[i] + 0) > (bv[i] + 0)) return 1
        if ((av[i] + 0) < (bv[i] + 0)) return 0
      }
      return 1
    }
    BEGIN {
      if (!valid(version) || !valid(minimum) || !valid(maximum)) exit 1
      exit !(greater_or_equal(version, minimum) && greater_or_equal(maximum, version))
    }
  '
}

choose_install_root() {
  local candidate="${CIEL_UPDATE_INSTALL_ROOT:-}"
  if [[ -n "$candidate" ]]; then
    print -r -- "${candidate%/}"
    return
  fi
  candidate="$(cd "$UPDATE_ROOT/.." && /bin/pwd -P)/CIEL Canvas"
  if [[ -f "$candidate/Application/current/release.json" ]]; then
    print -r -- "$candidate"
    return
  fi
  candidate="$(/usr/bin/osascript -e 'set selectedFolder to choose folder with prompt "请选择 CIEL Canvas 文件夹"' -e 'POSIX path of selectedFolder' 2>/dev/null || true)"
  print -r -- "${candidate%/}"
}

log_line() {
  /bin/mkdir -p "$LOG_DIR"
  print -r -- "$(/bin/date '+%Y-%m-%d %H:%M:%S') $1" >> "$UPDATE_LOG"
}

owned_service_pid() {
  local pid=""
  local command_line=""
  [[ -f "$PID_FILE" ]] || return 1
  pid="$(/usr/bin/tr -cd '0-9' < "$PID_FILE")"
  [[ -n "$pid" ]] || return 1
  /bin/kill -0 "$pid" >/dev/null 2>&1 || return 1
  command_line="$(/bin/ps -ww -p "$pid" -o command= 2>/dev/null || true)"
  [[ "$command_line" == *"$CURRENT/Application/current/bin/ciel-server/ciel-server"* || "$command_line" == *"$INSTALL_ROOT/Application/current/bin/ciel-server/ciel-server"* ]] || return 1
  print -r -- "$pid"
}

stop_owned_service() {
  local pid="$(owned_service_pid || true)"
  [[ -n "$pid" ]] || return 0
  log_line "STOP_OWNED PID=$pid"
  /bin/kill -TERM "$pid" >/dev/null 2>&1 || true
  for attempt in {1..40}; do
    /bin/kill -0 "$pid" >/dev/null 2>&1 || return 0
    /bin/sleep 0.25
  done
  log_line "STOP_TIMEOUT PID=$pid"
  return 1
}

extract_health_version() {
  local payload="$1"
  local pattern='"version"[[:space:]]*:[[:space:]]*"([^"]+)"'
  if [[ "$payload" =~ $pattern ]]; then
    print -r -- "$match[1]"
  fi
}

start_and_wait() {
  local expected_build="$1"
  local port="${TEST_PORT:-3015}"
  local launcher="$INSTALL_ROOT/Application/current/bin/start-ciel-release.sh"
  local server="$INSTALL_ROOT/Application/current/bin/ciel-server/ciel-server"
  local app_root="$INSTALL_ROOT/Application/current"
  local runtime="$INSTALL_ROOT/UserData/runtime"
  local payload=""
  local actual=""

  /bin/mkdir -p "$runtime/home" "$runtime/temp" "$runtime/cache" "$INSTALL_ROOT/UserData/logs"
  if [[ -n "$TEST_PORT" ]]; then
    (
      export CIEL_PORTABLE=1
      export CIEL_INSTALL_ROOT="$INSTALL_ROOT"
      export CIEL_APP_ROOT="$app_root"
      export CIEL_DATA_ROOT="$INSTALL_ROOT/UserData"
      export HOME="$runtime/home"
      export TMPDIR="$runtime/temp"
      export TMP="$TMPDIR"
      export TEMP="$TMPDIR"
      export XDG_CACHE_HOME="$runtime/cache"
      export PYTHONPYCACHEPREFIX="$runtime/cache/pycache"
      export PYTHONDONTWRITEBYTECODE=1
      export PORT="$port"
      cd "$app_root" || exit 91
      /usr/bin/nohup "$server" >> "$INSTALL_ROOT/UserData/logs/ciel-server-update-test.log" 2>&1 </dev/null &
      print -r -- "$!" > "$PID_FILE"
    )
  else
    [[ -x "$launcher" ]] || return 1
    "$launcher" >> "$UPDATE_LOG" 2>&1 || return 1
  fi

  for attempt in {1..120}; do
    payload="$(/usr/bin/curl -fsS --max-time 2 "http://127.0.0.1:$port/api/app-info" 2>/dev/null || true)"
    actual="$(extract_health_version "$payload")"
    if [[ "$actual" == "$expected_build" ]]; then
      [[ "$FORCE_HEALTH_FAIL" == "1" ]] && return 1
      return 0
    fi
    /bin/sleep 0.5
  done
  return 1
}

[[ -f "$UPDATE_PLIST" && -f "$MANIFEST" && -d "$PAYLOAD_CURRENT" ]] || finish "UPDATE_INCOMPLETE" 11

PRODUCT_ID="$(plist_raw product_id "$UPDATE_PLIST")"
FROM_MIN="$(plist_raw from_version_min "$UPDATE_PLIST")"
FROM_MAX="$(plist_raw from_version_max "$UPDATE_PLIST")"
TO_VERSION="$(plist_raw to_version "$UPDATE_PLIST")"
TO_BUILD="$(plist_raw to_internal_build "$UPDATE_PLIST")"
PLATFORM="$(plist_raw platform "$UPDATE_PLIST")"
ARCHITECTURE="$(plist_raw architecture "$UPDATE_PLIST")"
DATA_SCHEMA="$(plist_raw data_schema_version "$UPDATE_PLIST")"
PACKAGE_TYPE="$(plist_raw package_type "$UPDATE_PLIST")"
PAYLOAD_HASH="$(plist_raw payload_hash "$UPDATE_PLIST")"

[[ "$PRODUCT_ID" == "local.ciel.canvas" ]] || finish "PRODUCT_ID_REJECTED" 12
[[ "$PLATFORM" == "macos" ]] || finish "PLATFORM_REJECTED" 13
[[ "$ARCHITECTURE" == "$(/usr/bin/uname -m)" ]] || finish "ARCHITECTURE_REJECTED" 14
[[ "$PACKAGE_TYPE" == "application-update" ]] || finish "PACKAGE_TYPE_REJECTED" 15
[[ -n "$TO_VERSION" && -n "$TO_BUILD" && -n "$PAYLOAD_HASH" ]] || finish "UPDATE_METADATA_INVALID" 16

if /usr/bin/find "$UPDATE_ROOT/payload" -type d -name UserData -print -quit | /usr/bin/grep -q .; then
  finish "PAYLOAD_USERDATA_REJECTED" 17
fi
if /usr/bin/find "$UPDATE_ROOT/payload" -type l -print -quit | /usr/bin/grep -q .; then
  finish "PAYLOAD_SYMLINK_REJECTED" 18
fi

[[ "$(sha256_file "$MANIFEST")" == "$PAYLOAD_HASH" ]] || finish "MANIFEST_HASH_REJECTED" 19
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -n "$line" ]] || continue
  expected="${line%%  *}"
  relative="${line#*  }"
  [[ "$expected" != "$line" && "$expected" =~ '^[0-9a-f]{64}$' ]] || finish "MANIFEST_FORMAT_REJECTED" 20
  [[ "$relative" == payload/Application/current/* && "$relative" != /* && "$relative" != *".."* && "$relative" != *UserData* ]] || finish "MANIFEST_PATH_REJECTED" 21
  target="$UPDATE_ROOT/$relative"
  [[ -f "$target" ]] || finish "PAYLOAD_FILE_MISSING" 22
  [[ "$(sha256_file "$target")" == "$expected" ]] || finish "PAYLOAD_HASH_REJECTED" 23
done < "$MANIFEST"

INSTALL_ROOT="$(choose_install_root)"
[[ -n "$INSTALL_ROOT" ]] || finish "INSTALL_NOT_SELECTED" 24
CURRENT="$INSTALL_ROOT"
CURRENT_RELEASE="$INSTALL_ROOT/Application/current/release.json"
USER_DATA="$INSTALL_ROOT/UserData"
[[ -f "$CURRENT_RELEASE" && -d "$USER_DATA" ]] || finish "INSTALL_ROOT_REJECTED" 25

CURRENT_PRODUCT="$(plist_raw product_id "$CURRENT_RELEASE")"
CURRENT_VERSION="$(plist_raw release_version "$CURRENT_RELEASE")"
CURRENT_BUILD="$(plist_raw internal_build "$CURRENT_RELEASE")"
CURRENT_SCHEMA="$(plist_raw data_schema_version "$CURRENT_RELEASE")"
CURRENT_PLATFORM="$(plist_raw platform "$CURRENT_RELEASE")"
CURRENT_ARCH="$(plist_raw architecture "$CURRENT_RELEASE")"

[[ "$CURRENT_PRODUCT" == "$PRODUCT_ID" ]] || finish "INSTALL_PRODUCT_REJECTED" 26
[[ "$CURRENT_PLATFORM" == "$PLATFORM" ]] || finish "INSTALL_PLATFORM_REJECTED" 27
[[ "$CURRENT_ARCH" == "$ARCHITECTURE" ]] || finish "INSTALL_ARCHITECTURE_REJECTED" 28
[[ "$CURRENT_SCHEMA" == "$DATA_SCHEMA" ]] || finish "DATA_SCHEMA_REJECTED" 29
[[ "$CURRENT_VERSION" != "$TO_VERSION" ]] || finish "SAME_VERSION_REJECTED" 30
semver_in_range "$CURRENT_VERSION" "$FROM_MIN" "$FROM_MAX" || finish "VERSION_RANGE_REJECTED" 31

LOG_DIR="$USER_DATA/logs"
UPDATE_LOG="$LOG_DIR/update.log"
PID_FILE="$USER_DATA/runtime/ciel-server.pid"
/bin/mkdir -p "$LOG_DIR" "$USER_DATA/runtime" "$INSTALL_ROOT/Application/previous" "$INSTALL_ROOT/Application/failed"
log_line "BEGIN FROM=$CURRENT_VERSION TO=$TO_VERSION"

TIMESTAMP="$(/bin/date '+%Y%m%d-%H%M%S')"
STAGING="$INSTALL_ROOT/Application/staging-$TO_VERSION-$TIMESTAMP"
BACKUP="$INSTALL_ROOT/Application/previous/$CURRENT_VERSION-$TIMESTAMP"
FAILED="$INSTALL_ROOT/Application/failed/$TO_VERSION-$TIMESTAMP"
[[ ! -e "$STAGING" && ! -e "$BACKUP" && ! -e "$FAILED" ]] || finish "STAGING_COLLISION" 32

/usr/bin/ditto "$PAYLOAD_CURRENT" "$STAGING" || finish "STAGING_COPY_FAILED" 33
[[ "$(plist_raw product_id "$STAGING/release.json")" == "$PRODUCT_ID" ]] || finish "STAGING_PRODUCT_REJECTED" 34
[[ "$(plist_raw release_version "$STAGING/release.json")" == "$TO_VERSION" ]] || finish "STAGING_VERSION_REJECTED" 35
[[ "$(plist_raw internal_build "$STAGING/release.json")" == "$TO_BUILD" ]] || finish "STAGING_BUILD_REJECTED" 36

stop_owned_service || finish "OWNED_SERVICE_STOP_FAILED" 37
/bin/mv "$INSTALL_ROOT/Application/current" "$BACKUP" || finish "BACKUP_SWITCH_FAILED" 38
if ! /bin/mv "$STAGING" "$INSTALL_ROOT/Application/current"; then
  /bin/mv "$BACKUP" "$INSTALL_ROOT/Application/current" >/dev/null 2>&1 || true
  finish "CURRENT_SWITCH_FAILED" 39
fi

if start_and_wait "$TO_BUILD"; then
  INSTALL_JSON="$USER_DATA/install.json"
  if [[ -f "$INSTALL_JSON" ]]; then
    /usr/bin/plutil -replace installed_release -string "$TO_VERSION" "$INSTALL_JSON" >/dev/null 2>&1 || {
      log_line "INSTALL_JSON_UPDATE_FAILED"
      stop_owned_service || true
      /bin/mv "$INSTALL_ROOT/Application/current" "$FAILED" >/dev/null 2>&1 || true
      /bin/mv "$BACKUP" "$INSTALL_ROOT/Application/current" >/dev/null 2>&1 || true
      start_and_wait "$CURRENT_BUILD" >/dev/null 2>&1 || true
      finish "INSTALL_JSON_UPDATE_FAILED_ROLLED_BACK" 40
    }
  fi
  log_line "SUCCESS FROM=$CURRENT_VERSION TO=$TO_VERSION BACKUP=$BACKUP"
  finish "SUCCESS" 0
fi

log_line "NEW_HEALTH_FAILED ROLLBACK_BEGIN"
stop_owned_service || true
/bin/mv "$INSTALL_ROOT/Application/current" "$FAILED" >/dev/null 2>&1 || finish "ROLLBACK_MOVE_FAILED" 41
/bin/mv "$BACKUP" "$INSTALL_ROOT/Application/current" >/dev/null 2>&1 || finish "ROLLBACK_RESTORE_FAILED" 42
FORCE_HEALTH_FAIL=0
if start_and_wait "$CURRENT_BUILD"; then
  log_line "ROLLBACK_SUCCESS RESTORED=$CURRENT_VERSION FAILED=$FAILED"
  finish "NEW_HEALTH_FAILED_ROLLED_BACK" 43
fi
log_line "ROLLBACK_HEALTH_FAILED"
finish "ROLLBACK_HEALTH_FAILED" 44
