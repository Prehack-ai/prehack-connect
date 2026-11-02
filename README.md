# PreHack Connect

**Connect your AI editor to PreHack, an autonomous AI pentester for your app. One command, no API key.**

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![Dependencies: none](https://img.shields.io/badge/dependencies-none%20(stdlib)-brightgreen)
![Auth: device code RFC 8628](https://img.shields.io/badge/auth-device%20code%20(RFC%208628)-informational)
![Use: authorized only](https://img.shields.io/badge/use-authorized%20only-red)

[PreHack](https://prehack.ai) connects to your GitHub, finds security flaws in your app,
**proves each one with a real attack** in an isolated sandbox, and hands you the fix as a
Pull Request. **This repository is the small installer that plugs PreHack into the AI
tool you already use** (Claude Code or Cursor) through MCP.

> **What this repo is, and is not.** It is only the connector: a skill plus one
> Python script. It contains **no scanning engine, no security prompts, no attack skills
> and no secrets**. All of that runs on PreHack's servers. See [Security and trust](#security-and-trust).

## Who is this for

- **Developers** who want to run and review security scans from inside Claude Code or Cursor.
- **Founders and small teams** shipping fast (often with AI-written code) with no security
  team and no budget for a manual pentest.
- **Anyone** who wants to know what an installer does to their machine before running it.
  This one is a single readable file, standard library only.

## How it works

You (or your AI) run the connector. It never asks you to paste a key. It uses the
**OAuth 2.0 Device Authorization Grant ([RFC 8628](https://datatracker.ietf.org/doc/html/rfc8628))**,
the same kind of flow used by TVs and CLIs such as the GitHub CLI.

```
 Your machine                      PreHack server                 You, in a browser
 ------------                      --------------                 -----------------
 1. connector asks to start  --->  returns a short code + link
 2. prints the link and code  ------------------------------->   3. opens the link,
                                                                     signs in / subscribes,
                                                                     approves the code
 4. connector polls...        --->  "approved" + token   <-----
 5. writes the "prehack" entry into your editor's MCP config (file mode 0600)
 6. you restart the editor; PreHack's tools appear
```

1. The script asks the server for a one-time code and a verification link.
2. It prints them. **You** open the link in your own browser, create an account or sign in,
   subscribe if you have not yet, and approve.
3. The script polls until approved (or until the code expires) and receives an MCP token.
4. It writes a single `mcpServers.prehack` entry into your editor's config.

Account creation, payment and approval always happen in your browser, never in the script
and never on your behalf.

## Quickstart

Requirements: Python 3.12+. Nothing to install.

**Option A, let your AI do it.** In Claude Code or Cursor, say:

> install PreHack from github.com/Prehack-ai/prehack-connect

**Option B, run it yourself:**

```bash
git clone https://github.com/Prehack-ai/prehack-connect.git
cd prehack-connect

python3 scripts/prehack_connect.py                          # Claude Code, user scope
python3 scripts/prehack_connect.py --editor cursor
python3 scripts/prehack_connect.py --editor both --dry-run  # shows what it would do, writes nothing
```

Then restart your editor, list the server's tools (`tools/list`) and run
`postura_de_seguranca` to confirm the connection.

### Where it writes

| Editor | `--scope user` (default) | `--scope project` |
|---|---|---|
| Claude Code | `~/.claude.json` | `./.mcp.json` |
| Cursor | `~/.cursor/mcp.json` | `./.cursor/mcp.json` |

### Safety behaviours of the script

- **Idempotent:** only touches the `prehack` key; if it is already identical, nothing changes.
- **Backup first:** before modifying an existing file it copies it to `<file>.bak-YYYYMMDD-HHMMSS`.
- **Invalid JSON is never overwritten:** such a file is left untouched.
- **Token file permissions:** the config is written with `0600`.
- **Dry run:** `--dry-run` prints the plan and writes nothing.
- `--scope project` puts the token inside your repository. **Do not commit it.**

### Options

| Flag | Meaning |
|---|---|
| `--editor claude-code\|cursor\|both` | Which editor to configure (default `claude-code`) |
| `--scope user\|project` | Global config or this project only (default `user`) |
| `--transport http\|sse` | Streamable HTTP (default) or SSE |
| `--server-url URL` | Override the server (or env `PREHACK_SERVER_URL`; default `https://prehack-server.fly.dev`) |
| `--ttl SECONDS` | Maximum time to wait for approval |
| `--dry-run` | Show, do not write |

## What is PreHack

PreHack is an autonomous, multi-agent AI pentester offered as a service. In short:

1. **Connect GitHub.** That connection is your consent to test your code.
2. **It tests like an attacker**, including dynamic scans of the running app.
3. **It proves every finding** with a real proof-of-concept attack in an isolated sandbox. No proof, no report.
4. **It sends the fix** as a Pull Request.

Pricing is a single plan, **Plug & Play, US$29/month**, with managed AI credit: PreHack runs
the AI, **you do not need an API key**. See [prehack.ai](https://prehack.ai) for details, current
pricing and FAQ.

## Security and trust

**The wall.** This public repository holds only the installer. By design it contains:

- no scanning engine and no agent orchestration;
- no security prompts and no attack or exploitation skills;
- no secrets, keys or tokens (the token is issued to *you*, at run time, and stored only in
  *your* editor config).

You can verify this: the whole connector is `scripts/prehack_connect.py` (stdlib only) and
`SKILL.md`. Read them before you run them.

**What the script does on your machine:** talks to the PreHack server to run the device-code
flow, and edits your editor's MCP config file (with backup). Nothing else.

**Authorized use only.** Test only code and targets that you own or have **written permission**
to test. PreHack must not be used against third parties' systems. You are responsible for
having the authorization and complying with applicable law.

**Found a problem in this connector?** Please contact us through [prehack.ai](https://prehack.ai)
rather than opening a public issue with sensitive details.

## Testing

```bash
python3 -m py_compile scripts/prehack_connect.py
python3 scripts/prehack_connect.py --help
python3 -m unittest discover -s tests -v   # uses a local fake server, no network
```

## Links

- Website, pricing and FAQ: [prehack.ai](https://prehack.ai)
- Sign-in standard: [RFC 8628, OAuth 2.0 Device Authorization Grant](https://datatracker.ietf.org/doc/html/rfc8628)
- MCP (Model Context Protocol): [modelcontextprotocol.io](https://modelcontextprotocol.io)
