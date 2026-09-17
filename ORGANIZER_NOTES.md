# Organizer handoff: Customer Area Path Escape

## Challenge summary

- Platform: WordPress / web
- Vulnerability: CVE-2026-3464 in WP Customer Area 8.3.4
- Intended difficulty: medium
- Development flag: `CTF{customer_area_path_escape}`
- Default URL: `http://127.0.0.1:8080`
- Player credentials: `customer` / `customer-local-only`

The intended solve authenticates as the low-privilege customer, obtains the attachment nonce from the customer's real private-file post, abuses the `ftp-folder` filename traversal in `cuar_attach_file`, copies `/opt/flag.txt` into protected Customer Area storage, and downloads it through the plugin.

## Pre-deployment checklist

1. Set `CTF_FLAG` through the deployment secret system. Do not put the production flag in this archive or Git history.
2. Change both development passwords.
3. Remove `poc/` from anything distributed to players.
4. Keep MariaDB private and place the WordPress service behind the event ingress/proxy.
5. Prefer one isolated Compose project per team.
6. Preserve the one-attachment limit and player ownership of the seeded private-file post.
7. Run `make verify`, `make solve`, `make reset`, and `make solve` again before release.

The Compose file intentionally publishes WordPress to host loopback. Adapt ingress at the infrastructure layer; do not publish MariaDB.

## Deployment smoke test

```bash
cp .env.example .env
# Replace CTF_FLAG and credentials before production deployment.
docker compose up -d
docker compose logs -f cli
make verify
make solve
```

Expected development solve output:

```text
CTF{customer_area_path_escape}
```

Reset after testing so a team receives an unused attachment slot:

```bash
make reset
```

## Release separation

Organizer-only files:

- `poc/exploit.py`
- `poc/github_poc_etc_passwd.py`
- `ORGANIZER_NOTES.md`

Player-facing material may contain `PLAYER_BRIEF.md` and connection details supplied by the event platform. Source files are optional depending on the desired difficulty, but the PoCs and production secrets must never be included.

CTFtime is normally used for event/challenge listings and write-ups rather than hosting Docker infrastructure. Deploy the instance through the organizers' challenge platform, then place its public connection URL and `PLAYER_BRIEF.md` text in the relevant event challenge entry.
