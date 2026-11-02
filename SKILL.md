---
name: prehack-connect
description: Use quando o usuário pedir para instalar, conectar ou configurar a PreHack, ligar o pentest de IA ao meu repo, testar a segurança do meu código com IA, achar vulnerabilidades no meu projeto, ou mandar a URL github.com/Prehack-ai/prehack-connect. Também quando disser "conecta a PreHack no meu Claude Code/Cursor", "quero o pentester de IA", "instala o MCP da PreHack" ou "cadê minha credencial da PreHack".
---

# Conectar a PreHack ao editor

Esta skill só **autentica** e **aponta o editor** para o servidor da PreHack.
Todo o trabalho de segurança roda no servidor. Uso autorizado apenas: só
teste código e alvos que são do usuário ou que ele tem permissão escrita para testar.

## Passo a passo

1. **Rode o conector** (Python 3.12+, sem instalar nada):
   ```bash
   python3 scripts/prehack_connect.py
   ```
   Opções úteis: `--editor claude-code|cursor|both`, `--scope user|project`,
   `--server-url <url>` (ou env `PREHACK_SERVER_URL`), `--dry-run` (não grava nada).
   Prefira o escopo `user` (padrão): o escopo `project` grava o token dentro do repo.
2. **Mostre ao humano, em destaque**, o link e o código que o script imprimir
   ("Abra ... e cole o código ..."). É o humano quem abre o link no navegador dele,
   cria a conta, assina e aprova. Você não cria conta, não paga e não
   preenche nada por ele.
3. **Aguarde.** O script faz o poll sozinho e termina quando o humano aprovar
   (ou avisa se o código expirar; nesse caso rode de novo).
4. **Peça para reiniciar o editor** (ou recarregar os servidores MCP) para ele ler a config nova.
5. **Confirme:** chame `tools/list` no servidor `prehack` (deve listar as ferramentas)
   e rode `postura_de_seguranca`. Se responder, diga ao usuário: "conectado ✅".

## Regras

- Nunca peça nem mostre o token ao usuário, não o cole no chat, não o versione.
- Se `tools/list` retornar 401, o token expirou: rode o conector de novo.
- Não tente contornar a aprovação no navegador nem o pagamento.
