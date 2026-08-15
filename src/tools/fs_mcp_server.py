#!/usr/bin/env python3
"""Filesystem MCP sunucusu — stdio üzerinden JSON-RPC 2.0.

Sunumun "en az bir MCP/harici araç çağrısı" şartı, bir Python fonksiyonuna
"MCP" adı vererek değil, **gerçekten ayrı bir süreçte konuşan bir sunucu**
ile karşılanıyor. Uygulayıcı agent dosyalarını buradan yazar.

## Ne uygulanıyor

Model Context Protocol'ün araç (tool) alt kümesi:

| Yöntem | Durum |
|---|---|
| `initialize` | ✔ |
| `notifications/initialized` | ✔ (bildirim, yanıt üretmez) |
| `tools/list` | ✔ |
| `tools/call` | ✔ |
| `resources/*`, `prompts/*`, `sampling/*` | ✖ — bu projede karşılığı yok |

Dürüstçe: bu **tam bir MCP sunucusu değil**, protokolün araç alt kümesinin
çalışan bir uygulaması. Kapsam dışı yöntemler `-32601 Method not found`
döndürür.

## Güvenlik

Yol koruması **sunucunun içindedir**, çağıranın değil. Uygulayıcı agent
`../../etc/passwd` isterse istemci değil sunucu reddeder — güvenlik kontrolü
istemciye güvenmemelidir.

Çalıştırma:
    python -m src.tools.fs_mcp_server --root /workspaces/<gorev_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.security.path_guard import PathViolation, safe_join

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "gtech-fs"
SERVER_VERSION = "1.0.0"

MAX_FILE_BYTES = 512 * 1024

TOOLS: list[dict[str, Any]] = [
    {
        "name": "dosya_yaz",
        "description": (
            "Workspace içine bir dosya yazar. Yol workspace köküne görelidir; "
            "üst dizin başvurusu ve mutlak yol reddedilir."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "yol": {"type": "string", "description": "workspace'e göreli dosya yolu"},
                "icerik": {"type": "string", "description": "dosyanın tam içeriği"},
            },
            "required": ["yol", "icerik"],
            "additionalProperties": False,
        },
    },
    {
        "name": "dosya_oku",
        "description": "Workspace içindeki bir dosyayı okur.",
        "inputSchema": {
            "type": "object",
            "properties": {"yol": {"type": "string"}},
            "required": ["yol"],
            "additionalProperties": False,
        },
    },
    {
        "name": "dosya_listele",
        "description": "Workspace içindeki dosyaları listeler.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
]


class ToolError(Exception):
    """Araç çağrısı başarısız. İstemciye `isError` ile döner."""


class FileSystemTools:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def dosya_yaz(self, yol: str, icerik: str) -> str:
        if len(icerik.encode("utf-8")) > MAX_FILE_BYTES:
            raise ToolError(f"dosya çok büyük (tavan {MAX_FILE_BYTES} bayt)")
        path = self._resolve(yol)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(icerik, encoding="utf-8")
        return f"{yol} yazıldı ({len(icerik.encode('utf-8'))} bayt)"

    def dosya_oku(self, yol: str) -> str:
        path = self._resolve(yol)
        if not path.is_file():
            raise ToolError(f"dosya yok: {yol}")
        return path.read_text(encoding="utf-8", errors="replace")

    def dosya_listele(self) -> str:
        if not self.root.is_dir():
            return "(workspace boş)"
        names = sorted(
            str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file()
        )
        return "\n".join(names) if names else "(workspace boş)"

    def _resolve(self, yol: str) -> Path:
        try:
            return safe_join(self.root, yol)
        except PathViolation as exc:
            # Güvenlik kontrolü sunucunun içinde; istemciye güvenilmez.
            raise ToolError(str(exc)) from exc


class McpServer:
    def __init__(self, tools: FileSystemTools) -> None:
        self.tools = tools
        self._initialized = False

    def handle(self, request: dict) -> dict | None:
        """Bir isteği işler. Bildirimler için `None` döner (yanıt yok)."""
        method = request.get("method")
        request_id = request.get("id")

        if method == "notifications/initialized":
            self._initialized = True
            return None

        if request_id is None:
            return None  # tanınmayan bildirim: sessizce yut

        try:
            result = self._dispatch(method, request.get("params") or {})
        except ToolError as exc:
            # Araç hatası protokol hatası DEĞİLDİR: modelin görebileceği,
            # düzeltebileceği bir sonuçtur.
            return _ok(request_id, {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            })
        except KeyError:
            return _error(request_id, -32601, f"Method not found: {method}")
        except (TypeError, ValueError) as exc:
            return _error(request_id, -32602, f"Invalid params: {exc}")
        return _ok(request_id, result)

    def _dispatch(self, method: str | None, params: dict) -> dict:
        if method == "initialize":
            return {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
        if method == "tools/list":
            return {"tools": TOOLS}
        if method == "tools/call":
            return self._call_tool(params)
        raise KeyError(method)

    def _call_tool(self, params: dict) -> dict:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        known = {t["name"] for t in TOOLS}
        if name not in known:
            raise ToolError(f"bilinmeyen araç: {name}")
        try:
            text = getattr(self.tools, name)(**arguments)
        except TypeError as exc:
            raise ToolError(f"geçersiz argüman: {exc}") from exc
        return {"content": [{"type": "text", "text": text}], "isError": False}


def _ok(request_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def serve(root: Path, stdin=None, stdout=None) -> None:
    """Satır bazlı JSON-RPC döngüsü. stdio taşıması."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    server = McpServer(FileSystemTools(root))

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            response = _error(None, -32700, "Parse error")
        else:
            response = server.handle(request)
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    serve(Path(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
