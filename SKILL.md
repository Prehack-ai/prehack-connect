---
name: prehack-connect
description: Use when the user asks to install, connect or set up PreHack, hook the AI pentester up to my repo, run an AI pentest on my code, scan my code for vulnerabilities with AI, find security holes in my project, try PreHack for free, get a free security scan from my AI editor, or sends the URL github.com/Prehack-ai/prehack-connect. Also when they say "connect PreHack to my Claude Code/Cursor", "install PreHack", "I want the AI pentester", "set up the PreHack MCP" or "where's my PreHack credential".
---

# Connect PreHack to your editor

This skill only **authenticates** and **points the editor** at the PreHack
server. All the security work runs on the server. Authorized use only: only
test code and targets that belong to the user or that they have written
permission to test.

## Steps

1. **Run the connector** (Python 3.9+, nothing to install):
   ```bash
   python3 scripts/prehack_connect.py
   ```
   Useful options: `--editor claude-code|cursor|both`, `--scope user|project`,
   `--server-url <url>` (or env `PREHACK_SERVER_URL`), `--dry-run` (writes nothing).
   Prefer the `user` scope (default): the `project` scope writes the token inside the repo.
2. **Show the human, prominently,** the link and code the script prints
   ("Open ... Paste the code ..."). The human opens the link in their own browser,
   creates the account, then either **Authorize (free)** or **Subscribe**, and
   approves. You do not create accounts, pay or fill in anything on their behalf.
3. **Wait.** The script polls on its own and finishes once the human approves
   (or reports that the code expired; in that case run it again).
4. **Ask them to restart the editor** (or reload the MCP servers) so it reads the new config.
5. **Confirm:** call `tools/list` on the `prehack` server (it should list the tools)
   and run `postura_de_seguranca`. If it responds, tell the user: "connected ✅".

## Free mode vs Plug & Play

After connecting, a user without a subscription is in **free mode**. Tell them
plainly what that means:

- **Free mode** is not the PreHack pentester agent. It runs a set of deterministic
  platform tools (pattern matching and fixed checks): no AI, no proof of exploit,
  no fixes, no dynamic scan of the running app. Coverage and accuracy are lower
  than the agent and false positives are expected. Findings include file and line.
  Unlimited. In free mode nothing is ever written to the user's GitHub.
- **Plug & Play (US$29/mo)** adds AI-powered detection (more vulnerability classes,
  fewer false positives), proof of exploit for every finding, fixes delivered as
  pull requests, and dynamic scans of the running app.

## Rules

- Never ask the user for the token or show it to them, never paste it in the chat, never commit it.
- If `tools/list` returns 401, the token has expired: run the connector again.
- Do not try to bypass the browser approval or the payment.
- Tell the user plainly which mode they are in after connecting: tool results from
  the server carry `modo: "free"` and an `aviso` block when in free mode. Relay that
  notice to the user the first time, including that free mode is not the pentester
  agent. Do not present free-mode findings as proven or as the agent's output.
