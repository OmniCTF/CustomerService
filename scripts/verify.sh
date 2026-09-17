#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

if docker compose version >/dev/null 2>&1; then
  compose='docker compose'
else
  compose='docker-compose'
fi

port="${WP_PORT:-8080}"
base="http://127.0.0.1:${port}"

test "$(curl -sS -o /dev/null -w '%{http_code}' "$base/")" = 200
echo "ok: WordPress is reachable"

version="$($compose run --rm --no-deps --entrypoint wp cli plugin get customer-area --field=version)"
test "$version" = 8.3.4
echo "ok: WP Customer Area is exactly 8.3.4"

$compose run --rm --no-deps --entrypoint wp cli user get customer --field=ID >/dev/null
$compose run --rm --no-deps --entrypoint wp cli eval '$u=get_user_by("login","customer"); if (!$u || !$u->has_cap("cuar_pf_edit") || !$u->has_cap("cuar_pf_read") || $u->has_cap("manage_options") || $u->has_cap("cuar_pf_delete") || $u->has_cap("cuar_pf_list_all") || $u->has_cap("edit_posts")) { exit(1); }'
echo "ok: customer has only the required Customer Area access capabilities"

TARGET="$base" python3 - <<'PY'
import os
import requests

base = os.environ["TARGET"]
s = requests.Session()
s.get(base + "/wp-login.php", timeout=10)
s.post(base + "/wp-login.php", data={
    "log": "customer", "pwd": "customer-local-only", "wp-submit": "Log In",
    "redirect_to": base + "/", "testcookie": "1",
}, timeout=10)
r = s.get(base + "/wp-admin/plugin-install.php", allow_redirects=False, timeout=10)
if r.status_code < 400:
    raise SystemExit("customer unexpectedly reached plugin installation")
PY
echo "ok: customer cannot perform normal plugin-administration actions"

$compose exec -T wordpress test -r /opt/flag.txt
echo "ok: /opt/flag.txt exists and Apache can read it"

status="$(curl -sS -o /tmp/cve-2026-3464-direct-flag -w '%{http_code}' "$base/opt/flag.txt")"
test "$status" = 404
if grep -q 'CTF{' /tmp/cve-2026-3464-direct-flag; then
  echo "FAIL: flag leaked over a direct web request" >&2
  exit 1
fi
echo "ok: flag is not directly reachable over HTTP"

echo "All verification checks passed."
