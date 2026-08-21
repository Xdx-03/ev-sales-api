#!/usr/bin/env bash

set -Eeuo pipefail

readonly health_path="/car/model/public/list"
readonly base_url="${EV_API_BASE_URL:-http://127.0.0.1:8080}"
readonly request_timeout="${EV_API_TIMEOUT:-10}"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

pass() {
    printf 'PASS: %s\n' "$*"
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_command python3
require_command curl
require_command mktemp
require_command sed
require_command uname

[[ "$request_timeout" =~ ^[1-9][0-9]*$ ]] || fail "EV_API_TIMEOUT must be a positive integer"

case "${EV_TEST_ENV:-test}" in
    prod | production)
        fail "production is not an allowed automation target"
        ;;
esac

read -r api_scheme api_host is_loopback < <(
    python3 - "$base_url" <<'PY'
import ipaddress
import sys
from urllib.parse import urlsplit

parsed = urlsplit(sys.argv[1])
if parsed.scheme not in {"http", "https"} or not parsed.hostname:
    raise SystemExit("EV_API_BASE_URL must be an absolute HTTP(S) URL")
if parsed.username or parsed.password:
    raise SystemExit("EV_API_BASE_URL must not contain credentials")
if parsed.query or parsed.fragment:
    raise SystemExit("EV_API_BASE_URL must not contain a query or fragment")

hostname = parsed.hostname.lower()
loopback = hostname == "localhost"
try:
    loopback = loopback or ipaddress.ip_address(hostname).is_loopback
except ValueError:
    pass

print(parsed.scheme, hostname, str(loopback).lower())
PY
) || fail "EV_API_BASE_URL validation failed"

if [[ "$api_scheme" == "http" && "$is_loopback" != "true" ]]; then
    [[ "${EV_ALLOW_INSECURE_HTTP:-false}" == "true" ]] || fail \
        "plain HTTP is refused for non-loopback hosts; use HTTPS"
fi

if command -v getent >/dev/null 2>&1; then
    getent hosts "$api_host" >/dev/null || fail "DNS lookup failed for $api_host"
    pass "DNS lookup: $api_host"
fi

pass "OS: $(uname -sr)"
pass "Python: $(python3 --version 2>&1)"
pass "curl: $(curl --version | sed -n '1p')"

readonly api_url="${base_url%/}${health_path}"
response_file="$(mktemp "${TMPDIR:-/tmp}/ev-api-preflight.XXXXXX.json")"
trap 'rm -f "$response_file"' EXIT

http_code="$({
    curl \
        --silent \
        --show-error \
        --header 'Accept: application/json' \
        --connect-timeout 3 \
        --max-time "$request_timeout" \
        --output "$response_file" \
        --write-out '%{http_code}' \
        "$api_url"
} || fail "request failed before receiving an HTTP response")"

[[ "$http_code" =~ ^2[0-9][0-9]$ ]] || fail "preflight returned HTTP $http_code"
pass "HTTP status: $http_code"

python3 - "$response_file" <<'PY'
import json
import sys
from pathlib import Path

response_path = Path(sys.argv[1])
try:
    payload = json.loads(response_path.read_text(encoding="utf-8"))
except (OSError, UnicodeError, json.JSONDecodeError) as exc:
    raise SystemExit(f"ERROR: response is not valid UTF-8 JSON: {exc}") from None

if not isinstance(payload, dict):
    raise SystemExit("ERROR: response JSON must be an object")
if payload.get("code") != 200:
    raise SystemExit(f"ERROR: expected business code 200, got {payload.get('code')!r}")

print("PASS: business response code: 200")
PY

pass "Linux test environment preflight completed"
