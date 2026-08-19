"""Record a live Streamable HTTP handshake from WorkspaceAlberta Box to the local WA server."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = ROOT / "mcp-servers" / "canadabuys"
CLI = ROOT / "box" / "src" / "cli.mjs"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_health(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"WA HTTP server did not become healthy: {last_error}")


class BoxMcpHandshakeTest(unittest.TestCase):
    def test_box_handshakes_with_local_wa_http_server(self) -> None:
        self.assertTrue(CLI.is_file())
        port = _free_port()
        with tempfile.TemporaryDirectory() as data_dir:
            env = {
                **os.environ,
                "CANADABUYS_DATA_DIR": data_dir,
                "PYTHONPATH": os.pathsep.join(
                    [str(ROOT), str(SERVER_DIR), os.environ.get("PYTHONPATH", "")]
                ),
            }
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    (
                        "import uvicorn; from server_http import app; "
                        f"uvicorn.run(app, host='127.0.0.1', port={port}, log_level='warning')"
                    ),
                ],
                cwd=str(SERVER_DIR),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                _wait_health(f"http://127.0.0.1:{port}/health")
                result = subprocess.run(
                    [
                        "node",
                        str(CLI),
                        "handshake",
                        "--url",
                        f"http://127.0.0.1:{port}/mcp",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(ROOT / "box"),
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    msg=f"handshake failed\nstdout={result.stdout}\nstderr={result.stderr}",
                )
                payload = json.loads(result.stdout)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["serverInfo"]["name"], "canadabuys")
                tool_names = {tool["name"] for tool in payload["tools"]}
                self.assertIn("search_opportunities", tool_names)
                self.assertIn("get_my_profile", tool_names)
                self.assertIn("daily_bid_brief", tool_names)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
