#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

if docker compose version >/dev/null 2>&1; then
  compose='docker compose'
else
  compose='docker-compose'
fi

$compose run --rm --no-deps --entrypoint wp cli eval-file /challenge/reset.php

$compose exec -T --user 33:33 wordpress sh -c \
  "mkdir -p /var/www/html/wp-content/customer-area/ftp-uploads && printf '%s\\n' 'Quarterly onboarding packet (sample)' > /var/www/html/wp-content/customer-area/ftp-uploads/onboarding-notes.txt"

echo "Challenge state reset."
