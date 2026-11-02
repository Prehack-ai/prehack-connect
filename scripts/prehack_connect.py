#!/usr/bin/env python3
"""PreHack public connector: authenticates the customer and points their
editor at the PreHack MCP server.

Stdlib only. It contains no engine, prompts, attack skills or secrets:
everything sensitive lives on the server. This file only runs the
device-code flow (RFC 8628) and writes the ``mcpServers`` block into the
editor config.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_SERVER_URL = "https://prehack-server.fly.dev"
SERVER_NAME = "prehack"
START_PATH = "/mcp/device/start"
POLL_PATH = "/mcp/device/poll"
RPC_PATH = "/mcp/rpc"
HTTP_TIMEOUT = 15  # seconds per request
DEFAULT_TTL = 600  # seconds; used if the server does not report an expiry
SLOW_DOWN_STEP = 5  # RFC 8628: add 5s to the interval on "slow_down"
DEFAULT_INTERVAL = 5


class ConnectError(Exception):
    """Expected flow error, with a human-friendly message."""


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def post_json(url: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """POST JSON and return (status, body). HTTP errors do not raise:
    a 4xx body may carry the reason (e.g. expired, denied)."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectError(f"could not reach {url}: {exc}") from exc
    try:
        body = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = {}
    return status, body if isinstance(body, dict) else {}


# --------------------------------------------------------------------------
# Device-code flow
# --------------------------------------------------------------------------

def start_device_flow(base: str) -> dict[str, Any]:
    """Ask the server for a device_code/user_code pair."""
    status, body = post_json(f"{base}{START_PATH}", {})
    needed = ("user_code", "verification_url", "device_code")
    if status != 200 or any(key not in body for key in needed):
        raise ConnectError(f"the server refused to start the connection (HTTP {status}).")
    return body


def poll_for_token(
    base: str,
    device_code: str,
    interval: int,
    ttl: int,
    sleep=time.sleep,
    clock=time.monotonic,
) -> dict[str, Any]:
    """Poll until ``mcp_token`` is received. Honors ``interval`` and
    ``slow_down``; gives up once the TTL is exceeded."""
    deadline = clock() + ttl
    wait = max(1, interval)
    while clock() < deadline:
        sleep(wait)
        status, body = post_json(f"{base}{POLL_PATH}", {"device_code": device_code})
        if status == 200 and body.get("mcp_token"):
            return body
        state = body.get("status")
        if status == 200 and state == "pending":
            continue
        if status == 200 and state == "slow_down":
            wait += SLOW_DOWN_STEP
            continue
        if state == "expired" or status in (400, 404, 410):
            raise ConnectError("the code expired. Run the connector again.")
        if state in ("denied", "access_denied") or status == 403:
            raise ConnectError("the connection was denied on the approval page.")
        raise ConnectError(f"unexpected server response (HTTP {status}).")
    raise ConnectError("timed out waiting for approval. Run again when you are ready.")


# --------------------------------------------------------------------------
# Editor config
# --------------------------------------------------------------------------

def config_path(editor: str, scope: str, cwd: Path, home: Path) -> Path:
    """Path of the editor's MCP config file.

    - Claude Code, user scope: ``~/.claude.json`` (outside any repo).
    - Claude Code, project scope: ``<cwd>/.mcp.json`` (often committed!).
    - Cursor, user scope: ``~/.cursor/mcp.json``; project: ``<cwd>/.cursor/mcp.json``.
    """
    if editor == "claude-code":
        return home / ".claude.json" if scope == "user" else cwd / ".mcp.json"
    if editor == "cursor":
        base = home if scope == "user" else cwd
        return base / ".cursor" / "mcp.json"
    raise ConnectError(f"unknown editor: {editor}")


def build_server_block(base: str, token: str, transport: str) -> dict[str, Any]:
    """MCP server block. The token goes as a Bearer header."""
    return {
        "type": transport,
        "url": f"{base}{RPC_PATH}",
        "headers": {"Authorization": f"Bearer {token}"},
    }


def write_config(path: Path, block: dict[str, Any]) -> str:
    """Write ``mcpServers.prehack`` idempotently.

    Preserves the rest of the file, backs it up before changing it and only
    touches the ``prehack`` key. Returns "created", "updated" or "unchanged".
    """
    data: dict[str, Any] = {}
    existed = path.exists()
    if existed:
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise ConnectError(f"{path} is not valid JSON; left it untouched ({exc}).") from exc
        if not isinstance(data, dict):
            raise ConnectError(f"{path} has an unexpected format; left it untouched.")
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ConnectError(f"'mcpServers' in {path} is not an object; left it untouched.")
    if servers.get(SERVER_NAME) == block:
        return "unchanged"
    if existed:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, path.with_name(f"{path.name}.bak-{stamp}"))
    servers[SERVER_NAME] = block
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)  # contains a token
    tmp.replace(path)  # atomic swap
    return "updated" if existed else "created"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="prehack_connect",
        description="Connect your editor (Claude Code/Cursor) to PreHack via device-code.",
    )
    parser.add_argument("--server-url", default=os.environ.get("PREHACK_SERVER_URL", DEFAULT_SERVER_URL),
                        help=f"server base URL (env PREHACK_SERVER_URL; default {DEFAULT_SERVER_URL}).")
    parser.add_argument("--editor", choices=["claude-code", "cursor", "both"], default="claude-code")
    parser.add_argument("--scope", choices=["user", "project"], default="user",
                        help="user = global config (default, safe); project = file in the current repo (careful: contains a token).")
    parser.add_argument("--transport", choices=["http", "sse"], default="http",
                        help="MCP transport type written to the config (default http = Streamable HTTP with SSE).")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL, help="maximum seconds to wait for approval.")
    parser.add_argument("--dry-run", action="store_true",
                        help="runs the whole flow but writes NOTHING; shows what would be written (token masked).")
    return parser.parse_args(argv)


def mask(token: str) -> str:
    return f"{token[:4]}…({len(token)} chars)" if len(token) > 8 else "***"


def run(args: argparse.Namespace, cwd: Path | None = None, home: Path | None = None,
        sleep=time.sleep) -> int:
    base = args.server_url.rstrip("/")
    cwd, home = cwd or Path.cwd(), home or Path.home()
    try:
        started = start_device_flow(base)
        print("To connect PreHack:")
        print(f"  1. Open  {started['verification_url']}")
        print(f"  2. Paste the code:  {started['user_code']}")
        print("  3. Create your account / subscribe if you have not yet, then approve.")
        print("Waiting for approval...", flush=True)
        token_info = poll_for_token(
            base, started["device_code"], int(started.get("interval", DEFAULT_INTERVAL)),
            args.ttl, sleep=sleep,
        )
        token = token_info["mcp_token"]
        block = build_server_block(base, token, args.transport)
        editors = ["claude-code", "cursor"] if args.editor == "both" else [args.editor]
        for editor in editors:
            path = config_path(editor, args.scope, cwd, home)
            if args.dry_run:
                shown = {**block, "headers": {"Authorization": f"Bearer {mask(token)}"}}
                print(f"[dry-run] would write to {path}: mcpServers.{SERVER_NAME} = {json.dumps(shown)}")
                continue
            result = write_config(path, block)
            print(f"{editor}: {result} at {path}")
            if args.scope == "project":
                print(f"  WARNING: {path.name} contains the token. Do not commit it (.gitignore).")
    except ConnectError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    print("Done. Restart your editor and ask it to list the tools (tools/list) and run postura_de_seguranca.")
    if token_info.get("expires_at"):
        print(f"The token is valid until {token_info['expires_at']}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
