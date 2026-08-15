"""MCP istemcisi — filesystem sunucusuna stdio üzerinden bağlanır.

Sunucu ayrı bir süreçtir (`src/tools/fs_mcp_server.py`). İstemci onu
başlatır, `initialize` el sıkışmasını yapar ve araç çağrılarını iletir.

Her çağrı transkripte `ToolCall` olarak kaydedilir (§7.3): hangi araç,
hangi özet, başarılı mı. Denetlenebilirlik için çağrının kendisi de kanıt.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType

from src.transcript.models import ToolCall

PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "gtech-orchestrator"
CALL_TIMEOUT_SEC = 20


class McpError(RuntimeError):
    """Protokol düzeyinde hata — sunucu yanıt vermedi veya bozuk yanıt verdi."""


@dataclass
class McpResult:
    text: str
    is_error: bool

    @property
    def ok(self) -> bool:
        return not self.is_error


@dataclass
class McpClient:
    """Bağlam yöneticisi olarak kullanılır; süreç çıkışta kapatılır."""

    root: Path
    _process: subprocess.Popen | None = field(default=None, init=False)
    _next_id: int = field(default=0, init=False)
    calls: list[ToolCall] = field(default_factory=list, init=False)

    # -- yaşam döngüsü ------------------------------------------------------

    def __enter__(self) -> "McpClient":
        self._process = subprocess.Popen(
            [sys.executable, "-m", "src.tools.fs_mcp_server", "--root", str(self.root)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._handshake()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        self.close()

    def close(self) -> None:
        if self._process is None:
            return
        try:
            if self._process.stdin:
                self._process.stdin.close()
            self._process.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            self._process.kill()
        finally:
            self._process = None

    def _handshake(self) -> None:
        result = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": "1.0.0"},
            },
        )
        if "serverInfo" not in result:
            raise McpError(f"beklenmeyen initialize yanıtı: {result}")
        self._notify("notifications/initialized")

    # -- protokol -----------------------------------------------------------

    def _send(self, payload: dict) -> None:
        if self._process is None or self._process.stdin is None:
            raise McpError("MCP sunucusu çalışmıyor")
        self._process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._process.stdin.flush()

    def _notify(self, method: str, params: dict | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _request(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        self._send({
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
            "params": params or {},
        })

        if self._process is None or self._process.stdout is None:
            raise McpError("MCP sunucusu çalışmıyor")
        line = self._process.stdout.readline()
        if not line:
            stderr = self._process.stderr.read() if self._process.stderr else ""
            raise McpError(f"MCP sunucusu yanıt vermedi: {stderr[:300]}")

        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise McpError(f"bozuk MCP yanıtı: {line[:200]}") from exc

        if "error" in response:
            err = response["error"]
            raise McpError(f"MCP hatası {err.get('code')}: {err.get('message')}")
        return response.get("result") or {}

    # -- araçlar ------------------------------------------------------------

    def list_tools(self) -> list[dict]:
        return list(self._request("tools/list").get("tools") or [])

    def call(self, name: str, **arguments) -> McpResult:
        """Aracı çağırır ve sonucu transkript kaydına ekler."""
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        blocks = result.get("content") or []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        is_error = bool(result.get("isError"))

        ozet = arguments.get("yol") or ", ".join(f"{k}={v}" for k, v in arguments.items())
        self.calls.append(
            ToolCall(arac=f"mcp:{name}", ozet=str(ozet)[:120], basarili=not is_error)
        )
        return McpResult(text=text, is_error=is_error)

    # -- kolaylık -----------------------------------------------------------

    def write_file(self, yol: str, icerik: str) -> McpResult:
        return self.call("dosya_yaz", yol=yol, icerik=icerik)

    def read_file(self, yol: str) -> McpResult:
        return self.call("dosya_oku", yol=yol)

    def list_files(self) -> McpResult:
        return self.call("dosya_listele")
