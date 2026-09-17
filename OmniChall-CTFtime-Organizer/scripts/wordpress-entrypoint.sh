#!/bin/sh
set -eu

printf '%s\n' "${CTF_FLAG:-CTF{customer_area_path_escape}}" > /opt/flag.txt
chown root:www-data /opt/flag.txt
chmod 0440 /opt/flag.txt

exec docker-entrypoint.sh "$@"
