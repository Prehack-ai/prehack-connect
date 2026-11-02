# PreHack Connect

## O que é

Conector **público** da PreHack (pentester de IA autônomo). É uma skill de
Claude Code/Cursor mais um script que autentica você (device-code, RFC 8628)
e grava, na config do seu editor, o apontamento para o servidor MCP da PreHack.

Este repositório **não contém** motor, prompts de segurança, skills de ataque,
segredos nem chaves. Tudo isso vive no servidor. Aqui só há o instalador.

## Como rodar

Peça à sua IA: *"instala a PreHack a partir de github.com/Prehack-ai/prehack-connect"*, ou rode você mesmo
(Python 3.12+, só biblioteca padrão):

```bash
python3 scripts/prehack_connect.py                 # Claude Code, escopo user
python3 scripts/prehack_connect.py --editor cursor
python3 scripts/prehack_connect.py --editor both --dry-run   # só mostra, não grava
```

O script mostra um link e um código. Abra o link no navegador, crie a conta/assine
(se ainda não fez) e aprove. Ele então grava o bloco `mcpServers.prehack`.

Onde grava:

| Editor | `--scope user` (padrão) | `--scope project` |
|---|---|---|
| Claude Code | `~/.claude.json` | `./.mcp.json` |
| Cursor | `~/.cursor/mcp.json` | `./.cursor/mcp.json` |

- **Idempotente:** só mexe na chave `prehack`; se já está igual, não altera nada.
- **Backup:** antes de alterar um arquivo existente, copia para `<arquivo>.bak-AAAAMMDD-HHMMSS`.
- Arquivo com JSON inválido não é tocado. O arquivo é gravado com permissão `0600` (tem token).
- `--scope project` coloca o token no repo: não versione.
- Servidor: `--server-url` ou env `PREHACK_SERVER_URL` (padrão `https://prehack-server.fly.dev`).
- Transporte: `--transport http` (padrão, Streamable HTTP/SSE) ou `sse`.

Depois reinicie o editor, liste as ferramentas (`tools/list`) e rode `postura_de_seguranca`.

## Como testar

```bash
python3 -m py_compile scripts/prehack_connect.py
python3 scripts/prehack_connect.py --help
python3 -m unittest discover -s tests -v   # usa um servidor falso local, sem rede
```

Uso autorizado apenas: teste somente alvos seus ou com permissão escrita.
