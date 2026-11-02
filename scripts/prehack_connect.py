#!/usr/bin/env python3
"""Conector público da PreHack: autentica o cliente e aponta o editor dele
para o servidor MCP da PreHack.

Só stdlib. Não contém motor, prompt, skill de ataque nem segredo: tudo que é
sensível mora no servidor. Este arquivo apenas faz o device-code flow
(RFC 8628) e grava o bloco ``mcpServers`` na config do editor.
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
HTTP_TIMEOUT = 15  # segundos por requisição
DEFAULT_TTL = 600  # segundos; usado se o servidor não informar expiração
SLOW_DOWN_STEP = 5  # RFC 8628: soma 5s ao intervalo em "slow_down"
DEFAULT_INTERVAL = 5


class ConnectError(Exception):
    """Erro esperado do fluxo, com mensagem amigável para o humano."""


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def post_json(url: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """POST JSON e devolve (status, corpo). Erros HTTP não levantam exceção:
    o corpo de 4xx pode trazer o motivo (ex.: expirado, negado)."""
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
        raise ConnectError(f"não consegui falar com {url}: {exc}") from exc
    try:
        body = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = {}
    return status, body if isinstance(body, dict) else {}


# --------------------------------------------------------------------------
# Device-code flow
# --------------------------------------------------------------------------

def start_device_flow(base: str) -> dict[str, Any]:
    """Pede um par device_code/user_code ao servidor."""
    status, body = post_json(f"{base}{START_PATH}", {})
    needed = ("user_code", "verification_url", "device_code")
    if status != 200 or any(key not in body for key in needed):
        raise ConnectError(f"o servidor recusou iniciar a conexão (HTTP {status}).")
    return body


def poll_for_token(
    base: str,
    device_code: str,
    interval: int,
    ttl: int,
    sleep=time.sleep,
    clock=time.monotonic,
) -> dict[str, Any]:
    """Faz poll até receber ``mcp_token``. Respeita ``interval`` e
    ``slow_down``; desiste ao passar do TTL."""
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
            raise ConnectError("o código expirou. Rode o conector de novo.")
        if state in ("denied", "access_denied") or status == 403:
            raise ConnectError("a conexão foi negada na página de aprovação.")
        raise ConnectError(f"resposta inesperada do servidor (HTTP {status}).")
    raise ConnectError("tempo esgotado esperando a aprovação. Rode de novo quando estiver pronto.")


# --------------------------------------------------------------------------
# Config do editor
# --------------------------------------------------------------------------

def config_path(editor: str, scope: str, cwd: Path, home: Path) -> Path:
    """Caminho do arquivo de config MCP do editor.

    - Claude Code, escopo user: ``~/.claude.json`` (fora de qualquer repo).
    - Claude Code, escopo project: ``<cwd>/.mcp.json`` (costuma ser versionado!).
    - Cursor, escopo user: ``~/.cursor/mcp.json``; project: ``<cwd>/.cursor/mcp.json``.
    """
    if editor == "claude-code":
        return home / ".claude.json" if scope == "user" else cwd / ".mcp.json"
    if editor == "cursor":
        base = home if scope == "user" else cwd
        return base / ".cursor" / "mcp.json"
    raise ConnectError(f"editor desconhecido: {editor}")


def build_server_block(base: str, token: str, transport: str) -> dict[str, Any]:
    """Bloco do servidor MCP. O token vai como Bearer no header."""
    return {
        "type": transport,
        "url": f"{base}{RPC_PATH}",
        "headers": {"Authorization": f"Bearer {token}"},
    }


def write_config(path: Path, block: dict[str, Any]) -> str:
    """Grava ``mcpServers.prehack`` de forma idempotente.

    Preserva todo o resto do arquivo, faz backup antes de alterar e só mexe
    na chave ``prehack``. Devolve "criado", "atualizado" ou "inalterado".
    """
    data: dict[str, Any] = {}
    existed = path.exists()
    if existed:
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise ConnectError(f"{path} não é um JSON válido; não mexi nele ({exc}).") from exc
        if not isinstance(data, dict):
            raise ConnectError(f"{path} tem formato inesperado; não mexi nele.")
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ConnectError(f"'mcpServers' em {path} não é um objeto; não mexi nele.")
    if servers.get(SERVER_NAME) == block:
        return "inalterado"
    if existed:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, path.with_name(f"{path.name}.bak-{stamp}"))
    servers[SERVER_NAME] = block
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)  # contém token
    tmp.replace(path)  # troca atômica
    return "atualizado" if existed else "criado"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="prehack_connect",
        description="Conecta o seu editor (Claude Code/Cursor) à PreHack via device-code.",
    )
    parser.add_argument("--server-url", default=os.environ.get("PREHACK_SERVER_URL", DEFAULT_SERVER_URL),
                        help=f"URL base do servidor (env PREHACK_SERVER_URL; padrão {DEFAULT_SERVER_URL}).")
    parser.add_argument("--editor", choices=["claude-code", "cursor", "both"], default="claude-code")
    parser.add_argument("--scope", choices=["user", "project"], default="user",
                        help="user = config global (padrão, seguro); project = arquivo no repo atual (cuidado: token).")
    parser.add_argument("--transport", choices=["http", "sse"], default="http",
                        help="tipo de transporte MCP gravado na config (padrão http = Streamable HTTP com SSE).")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL, help="segundos máximos esperando a aprovação.")
    parser.add_argument("--dry-run", action="store_true",
                        help="faz o fluxo todo mas NÃO grava nada; mostra o que gravaria (token mascarado).")
    return parser.parse_args(argv)


def mask(token: str) -> str:
    return f"{token[:4]}…({len(token)} chars)" if len(token) > 8 else "***"


def run(args: argparse.Namespace, cwd: Path | None = None, home: Path | None = None,
        sleep=time.sleep) -> int:
    base = args.server_url.rstrip("/")
    cwd, home = cwd or Path.cwd(), home or Path.home()
    try:
        started = start_device_flow(base)
        print("Para conectar a PreHack:")
        print(f"  1. Abra  {started['verification_url']}")
        print(f"  2. Cole o código:  {started['user_code']}")
        print("  3. Crie a conta / assine, se ainda não fez, e aprove.")
        print("Aguardando a aprovação...", flush=True)
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
                print(f"[dry-run] gravaria em {path}: mcpServers.{SERVER_NAME} = {json.dumps(shown)}")
                continue
            result = write_config(path, block)
            print(f"{editor}: {result} em {path}")
            if args.scope == "project":
                print(f"  ATENÇÃO: {path.name} contém o token. Não versione (.gitignore).")
    except ConnectError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelado.", file=sys.stderr)
        return 130
    print("Pronto. Reinicie o editor e peça: liste as ferramentas (tools/list) e rode postura_de_seguranca.")
    if token_info.get("expires_at"):
        print(f"O token vale até {token_info['expires_at']}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
