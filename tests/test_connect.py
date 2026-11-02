"""Tests against a local FAKE server (stdlib). Run: python -m unittest -v"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import prehack_connect as pc  # noqa: E402


class FakeHandler(BaseHTTPRequestHandler):
    """Fake server: 1st poll pending, 2nd slow_down, 3rd approved."""
    polls = 0
    mode = "ok"  # ok | expired

    def log_message(self, *args) -> None:  # silence the log
        pass

    def _send(self, status: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path == "/mcp/device/start":
            self._send(200, {"user_code": "WDJB-MJHT", "verification_url": "http://x/device",
                             "device_code": "opaco", "interval": 1})
        elif self.path == "/mcp/device/poll":
            if FakeHandler.mode == "expired":
                return self._send(200, {"status": "expired"})
            FakeHandler.polls += 1
            if FakeHandler.polls == 1:
                return self._send(200, {"status": "pending"})
            if FakeHandler.polls == 2:
                return self._send(200, {"status": "slow_down"})
            self._send(200, {"mcp_token": "tok_secret_123456", "expires_at": "2026-11-02T00:00:00Z"})
        else:
            self._send(404, {})


class ConnectTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeHandler.polls, FakeHandler.mode = 0, "ok"
        self.server = HTTPServer(("127.0.0.1", 0), FakeHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.sleeps: list[float] = []

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def args(self, *extra: str):
        return pc.parse_args(["--server-url", self.url, *extra])

    def test_fluxo_completo_idempotente_e_backup(self) -> None:
        target = self.home / ".claude.json"
        target.write_text(json.dumps({"outra": 1, "mcpServers": {"x": {"url": "u"}}}))
        code = pc.run(self.args(), cwd=self.home, home=self.home, sleep=self.sleeps.append)
        self.assertEqual(code, 0)
        self.assertEqual(self.sleeps, [1, 1, 6])  # slow_down adds 5s
        data = json.loads(target.read_text())
        self.assertEqual(data["outra"], 1)
        self.assertIn("x", data["mcpServers"])
        self.assertEqual(data["mcpServers"]["prehack"]["url"], f"{self.url}/mcp/rpc")
        self.assertEqual(data["mcpServers"]["prehack"]["headers"]["Authorization"], "Bearer tok_secret_123456")
        self.assertEqual(len(list(self.home.glob(".claude.json.bak-*"))), 1)
        # idempotency: same block -> unchanged, no new backup
        block = pc.build_server_block(self.url, "tok_secret_123456", "http")
        self.assertEqual(pc.write_config(target, block), "unchanged")
        self.assertEqual(len(list(self.home.glob(".claude.json.bak-*"))), 1)

    def test_dry_run_nao_grava(self) -> None:
        code = pc.run(self.args("--dry-run", "--editor", "both"), cwd=self.home, home=self.home,
                      sleep=lambda s: None)
        self.assertEqual(code, 0)
        self.assertFalse((self.home / ".claude.json").exists())
        self.assertFalse((self.home / ".cursor" / "mcp.json").exists())

    def test_cursor_cria_arquivo(self) -> None:
        pc.run(self.args("--editor", "cursor"), cwd=self.home, home=self.home, sleep=lambda s: None)
        self.assertTrue((self.home / ".cursor" / "mcp.json").exists())

    def test_expirado(self) -> None:
        FakeHandler.mode = "expired"
        code = pc.run(self.args(), cwd=self.home, home=self.home, sleep=lambda s: None)
        self.assertEqual(code, 1)

    def test_json_invalido_nao_e_sobrescrito(self) -> None:
        target = self.home / ".claude.json"
        target.write_text("{quebrado")
        code = pc.run(self.args(), cwd=self.home, home=self.home, sleep=lambda s: None)
        self.assertEqual(code, 1)
        self.assertEqual(target.read_text(), "{quebrado")


class PythonVersionTests(unittest.TestCase):
    """The runtime check is a pure function; no interpreter swapping needed."""

    def test_old_python_gets_a_message(self) -> None:
        message = pc.check_python_version((3, 8, 10, "final", 0))
        self.assertEqual(
            message,
            "PreHack Connect needs Python 3.9 or newer; you have 3.8. "
            "Install a newer Python or run with python3.9+.",
        )

    def test_supported_python_passes(self) -> None:
        self.assertIsNone(pc.check_python_version((3, 9, 0)))
        self.assertIsNone(pc.check_python_version((3, 12, 1)))
        self.assertIsNone(pc.check_python_version(sys.version_info))

    def test_main_exits_2_before_argparse_on_old_python(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(pc.sys, "version_info", (3, 7, 0)), redirect_stderr(stderr):
            code = pc.main(["--this-flag-does-not-exist"])  # argparse never runs
        self.assertEqual(code, 2)
        self.assertIn("needs Python 3.9 or newer; you have 3.7", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
