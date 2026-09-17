#!/bin/sh
set -eu

cd /var/www/html

echo "Waiting for WordPress files and database..."
until [ -f wp-includes/version.php ] && wp db check --quiet 2>/dev/null; do
  sleep 2
done

if ! wp core is-installed 2>/dev/null; then
  wp core install \
    --url="${WP_URL}" \
    --title="Northstar Customer Document Portal" \
    --admin_user="${ADMIN_USER}" \
    --admin_password="${ADMIN_PASSWORD}" \
    --admin_email="admin@example.test" \
    --skip-email
fi

archive=/tmp/customer-area.8.3.4.zip
expected_sha256=f6f1bedef8e98ecc1b351cd4659bf8a5321dffe7c0696c65c0c6ded0b122e74b

if [ -f /vendor/wp-customer-area.8.3.4.zip ]; then
  cp /vendor/wp-customer-area.8.3.4.zip "$archive"
  echo "Using vendor/wp-customer-area.8.3.4.zip"
else
  echo "Downloading the official WP Customer Area 8.3.4 archive..."
  wp eval 'file_put_contents("/tmp/customer-area.8.3.4.zip", wp_remote_retrieve_body(wp_remote_get("https://downloads.wordpress.org/plugin/customer-area.8.3.4.zip", ["timeout" => 60])));'
fi

actual_sha256="$(sha256sum "$archive" | awk '{print $1}')"
if [ "$actual_sha256" != "$expected_sha256" ]; then
  echo "FATAL: WP Customer Area archive checksum mismatch" >&2
  echo "expected: $expected_sha256" >&2
  echo "actual:   $actual_sha256" >&2
  exit 1
fi

if ! wp plugin is-installed customer-area; then
  wp plugin install "$archive" --activate
else
  wp plugin activate customer-area
fi

version="$(wp plugin get customer-area --field=version)"
if [ "$version" != "8.3.4" ]; then
  echo "FATAL: expected WP Customer Area 8.3.4, found $version" >&2
  exit 1
fi
echo "WP Customer Area version: $version"

mkdir -p wp-content/customer-area/ftp-uploads
printf '%s\n' 'Quarterly onboarding packet (sample)' > wp-content/customer-area/ftp-uploads/onboarding-notes.txt

wp eval-file /challenge/seed.php
wp rewrite structure '/%postname%/' --hard
wp rewrite flush --hard

touch /var/www/html/.lab-ready
echo "Lab initialization complete: ${WP_URL}"
