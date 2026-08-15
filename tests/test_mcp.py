"""MCP sunucusu ve istemcisi.

Sunumun "en az bir MCP çağrısı" şartı gerçek bir stdio sunucusuyla
karşılanıyor. Buradaki en önemli test yol kaçışının **sunucuda**
reddedildiğini gösteren testtir: güvenlik kontrolü istemciye güvenmemeli.
"""

from __future__ import annotations

import io
import json

import pytest

from src.tools.fs_mcp_server import (
    PROTOCOL_VERSION,
    TOOLS,
    FileSystemTools,
    McpServer,
    ToolError,
    serve,
)
from src.tools.mcp_client import McpClient, McpError


def request(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


@pytest.fixture
def server(tmp_path) -> McpServer:
    return McpServer(FileSystemTools(tmp_path))


# ==========================================================================
# Protokol
# ==========================================================================


def test_initialize_sunucu_bilgisi_doner(server):
    result = server.handle(request("initialize"))["result"]
    assert result["protocolVersion"] == PROTOCOL_VERSION
    assert result["serverInfo"]["name"]
    assert "tools" in result["capabilities"]


def test_initialized_bildirimi_yanit_uretmez(server):
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_semalari_doner(server):
    tools = server.handle(request("tools/list"))["result"]["tools"]
    assert {t["name"] for t in tools} == {"dosya_yaz", "dosya_oku", "dosya_listele"}
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"
        assert tool["description"]


def test_kapsam_disi_yontem_32601_doner(server):
    """resources/* ve prompts/* bu projede uygulanmıyor; dürüstçe reddediliyor."""
    error = server.handle(request("resources/list"))["error"]
    assert error["code"] == -32601


def test_bozuk_json_parse_hatasi_doner(tmp_path):
    out = io.StringIO()
    serve(tmp_path, stdin=io.StringIO("{bozuk\n"), stdout=out)
    assert json.loads(out.getvalue())["error"]["code"] == -32700


# ==========================================================================
# Araçlar
# ==========================================================================


def test_dosya_yazilir_ve_okunur(server, tmp_path):
    server.handle(request("tools/call", {
        "name": "dosya_yaz", "arguments": {"yol": "logic.js", "icerik": "export const x=1;"}
    }))
    assert (tmp_path / "logic.js").read_text(encoding="utf-8") == "export const x=1;"

    result = server.handle(request("tools/call", {
        "name": "dosya_oku", "arguments": {"yol": "logic.js"}
    }))["result"]
    assert result["isError"] is False
    assert "export const x=1;" in result["content"][0]["text"]


def test_alt_dizin_olusturulur(server, tmp_path):
    server.handle(request("tools/call", {
        "name": "dosya_yaz", "arguments": {"yol": "src/a.js", "icerik": "1"}
    }))
    assert (tmp_path / "src" / "a.js").is_file()


def test_dosya_listelenir(server):
    for name in ("b.js", "a.js"):
        server.handle(request("tools/call", {
            "name": "dosya_yaz", "arguments": {"yol": name, "icerik": "x"}
        }))
    text = server.handle(request("tools/call", {
        "name": "dosya_listele", "arguments": {}
    }))["result"]["content"][0]["text"]
    assert text.splitlines() == ["a.js", "b.js"]


# ==========================================================================
# Güvenlik — kontrol sunucunun içinde
# ==========================================================================


@pytest.mark.parametrize(
    "kotu", ["../kacis.js", "../../etc/passwd", "/etc/passwd", "a/../../b.js"]
)
def test_yol_kacisi_sunucuda_reddedilir(server, kotu, tmp_path):
    result = server.handle(request("tools/call", {
        "name": "dosya_yaz", "arguments": {"yol": kotu, "icerik": "kotu"}
    }))["result"]
    assert result["isError"] is True
    assert "reddedildi" in result["content"][0]["text"]
    assert not (tmp_path.parent / "kacis.js").exists()


def test_yol_ihlali_protokol_hatasi_degil_arac_hatasidir(server):
    """Model bunu görüp düzeltebilmeli; bağlantıyı koparmamalı."""
    response = server.handle(request("tools/call", {
        "name": "dosya_yaz", "arguments": {"yol": "../x", "icerik": "y"}
    }))
    assert "error" not in response
    assert response["result"]["isError"] is True


def test_bilinmeyen_arac_reddedilir(server):
    result = server.handle(request("tools/call", {
        "name": "kabuk_calistir", "arguments": {"komut": "rm -rf /"}
    }))["result"]
    assert result["isError"] is True


def test_gecersiz_argüman_reddedilir(server):
    result = server.handle(request("tools/call", {
        "name": "dosya_yaz", "arguments": {"yanlis_alan": "x"}
    }))["result"]
    assert result["isError"] is True


def test_cok_buyuk_dosya_reddedilir(tmp_path):
    tools = FileSystemTools(tmp_path)
    with pytest.raises(ToolError, match="çok büyük"):
        tools.dosya_yaz("buyuk.js", "x" * (600 * 1024))


def test_olmayan_dosya_okunamaz(tmp_path):
    with pytest.raises(ToolError, match="dosya yok"):
        FileSystemTools(tmp_path).dosya_oku("yok.js")


# ==========================================================================
# İstemci — gerçek alt süreçle
# ==========================================================================


def test_istemci_sunucuyu_baslatir_ve_arac_listeler(tmp_path):
    with McpClient(tmp_path) as client:
        names = {t["name"] for t in client.list_tools()}
    assert names == {t["name"] for t in TOOLS}


def test_istemci_dosya_yazar(tmp_path):
    with McpClient(tmp_path) as client:
        result = client.write_file("logic.js", "const x = 1;")
    assert result.ok
    assert (tmp_path / "logic.js").read_text(encoding="utf-8") == "const x = 1;"


def test_istemci_cagrilari_transkript_icin_kaydeder(tmp_path):
    with McpClient(tmp_path) as client:
        client.write_file("a.js", "1")
        client.write_file("b.js", "2")
    assert [c.arac for c in client.calls] == ["mcp:dosya_yaz", "mcp:dosya_yaz"]
    assert all(c.basarili for c in client.calls)
    assert client.calls[0].ozet == "a.js"


def test_istemci_basarisiz_cagriyi_isaretler(tmp_path):
    with McpClient(tmp_path) as client:
        result = client.write_file("../kacis.js", "kotu")
    assert not result.ok
    assert client.calls[0].basarili is False


def test_istemci_kapandiktan_sonra_cagri_hata_verir(tmp_path):
    client = McpClient(tmp_path)
    with client:
        pass
    with pytest.raises(McpError, match="çalışmıyor"):
        client.list_tools()
