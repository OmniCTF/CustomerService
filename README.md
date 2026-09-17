# CVE-2026-3464: WP Customer Area 8.3.4 local lab
# This is a SOURCELESS chall

This repository is a self-contained, loopback-only WordPress research lab and small CTF challenge for the arbitrary-file-**read** impact of CVE-2026-3464. It intentionally does not implement the deletion variant.

## Architecture

`docker-compose.yml` runs three pinned official images:

- `wordpress:6.7.2-php8.2-apache` serves WordPress on `127.0.0.1:8080` only. Its entrypoint creates `/opt/flag.txt` outside `/var/www/html`.
- `mariadb:11.4.5` stores WordPress data on the internal Compose network and publishes no host port.
- `wordpress:cli-2.11.0-php8.2` installs WordPress, downloads and checksum-verifies WP Customer Area 8.3.4, creates the users/content, and then exits.

The `wp_data` volume is shared by WordPress and the one-shot CLI bootstrap. The database has its own volume. The only published socket is the WordPress loopback port.

## Credentials

| Account | Password | Access |
|---|---|---|
| `admin` | `admin-local-only-hehetryguessme101@` | WordPress administrator |
| `customer` | `customer-local-only` | Custom `Customer Area Player` role |

The player role has WordPress `read` plus Customer Area `cuar_pf_edit` and `cuar_pf_read`. It does **not** have `cuar_pf_manage_attachments`, `cuar_pf_list_all`, `cuar_pf_delete`, `manage_options`, WordPress `edit_posts`, Editor, or Administrator privileges. `cuar_pf_edit` opens the ordinary edit screen for the player's seeded private-file post, and `cuar_pf_read` is the post type's read capability. The AJAX handler itself accepts the post author without `cuar_pf_manage_attachments`, so the player owns the seeded post. The plugin's optional global admin-area restriction remains disabled; no broad admin-access capability is added.



## CTF deployment notes

- Supply the real flag as an environment secret (`CTF_FLAG`) and never commit it.
- Remove `poc/` from the player-facing release.
- Replace both development passwords.
- Expose the instance only through controlled CTF infrastructure; keep MariaDB and internal services private.
- Prefer an isolated instance per team.
- Retain the loopback binding for local research. If challenge infrastructure must proxy it, explicitly design that network boundary rather than broadly publishing the container port.

The helper PHP files only seed/reset users and posts. They are mounted into the CLI container, are not web-accessible, and contain no file-read endpoint. The vulnerable behavior is entirely WP Customer Area 8.3.4.
