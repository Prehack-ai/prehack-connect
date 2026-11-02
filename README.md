# PreHack Connect

## What it is

The **public** connector for PreHack (an autonomous AI pentester). It is a
Claude Code/Cursor skill plus a script that authenticates you (device-code,
RFC 8628) and writes, into your editor's config, the entry that points to the
PreHack MCP server.

This repository **does not contain** the engine, security prompts, attack
skills, secrets or keys. All of that lives on the server. Here there is only
the installer.

## How to run

Ask your AI: *"install PreHack from github.com/Prehack-ai/prehack-connect"*, or run it yourself
(Python 3.12+, standard library only):

```bash
python3 scripts/prehack_connect.py                 # Claude Code, user scope
python3 scripts/prehack_connect.py --editor cursor
python3 scripts/prehack_connect.py --editor both --dry-run   # only shows, writes nothing
```

The script prints a link and a code. Open the link in your browser, create an
account/subscribe (if you have not yet) and approve. It then writes the
`mcpServers.prehack` block.

Where it writes:

| Editor | `--scope user` (default) | `--scope project` |
|---|---|---|
| Claude Code | `~/.claude.json` | `./.mcp.json` |
| Cursor | `~/.cursor/mcp.json` | `./.cursor/mcp.json` |

- **Idempotent:** only touches the `prehack` key; if it is already identical, nothing changes.
- **Backup:** before changing an existing file, it copies it to `<file>.bak-YYYYMMDD-HHMMSS`.
- A file with invalid JSON is left untouched. The file is written with `0600` permissions (it holds a token).
- `--scope project` puts the token inside the repo: do not commit it.
- Server: `--server-url` or env `PREHACK_SERVER_URL` (default `https://prehack-server.fly.dev`).
- Transport: `--transport http` (default, Streamable HTTP/SSE) or `sse`.

Afterwards, restart your editor, list the tools (`tools/list`) and run `postura_de_seguranca`.

## How to test

```bash
python3 -m py_compile scripts/prehack_connect.py
python3 scripts/prehack_connect.py --help
python3 -m unittest discover -s tests -v   # uses a local fake server, no network
```

Authorized use only: test only targets you own or have written permission to test.
