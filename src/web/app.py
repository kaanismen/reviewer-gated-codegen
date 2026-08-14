"""HTTP katmanı.

Faz 0 kapsamı: sistemin ayakta olduğunu ve hangi modda çalıştığını gösteren
tek sayfa + sağlık ucu. Orkestrasyon uçları (SSE transkript akışı, görev
başlatma) Faz 5'te eklenecek.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.config import WORKSPACES_ROOT, in_container, resolve_provider
from src.orchestrator.limits import LIMITS

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Agent Oyun Atölyesi", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _node_version() -> str | None:
    """Node yoksa None döner — sağlık ucu bunu eksiklik olarak raporlar."""
    node = shutil.which("node")
    if not node:
        return None
    try:
        done = subprocess.run(
            [node, "--version"], capture_output=True, text=True, timeout=5, check=True
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return done.stdout.strip() or None


def _runner_user_exists() -> bool:
    """Sandbox'ın ayrıcalık düşürme katmanı bu kullanıcıya dayanır (§3.3)."""
    try:
        import pwd  # POSIX; Windows'ta geliştirirken yoktur
    except ImportError:
        return False
    try:
        pwd.getpwnam("runner")
    except KeyError:
        return False
    return True


@app.get("/api/health")
def health() -> dict[str, object]:
    provider = resolve_provider()
    node = _node_version()
    return {
        "durum": "ayakta",
        "saglayici": provider.name,
        "saglayici_gerekce": provider.reason,
        "cevrimdisi_mod": provider.is_offline,
        "python": platform.python_version(),
        "node": node,
        "konteyner": in_container(),
        "runner_kullanicisi": _runner_user_exists(),
        "workspaces": str(WORKSPACES_ROOT),
        "workspaces_yazilabilir": WORKSPACES_ROOT.is_dir(),
        "limitler": LIMITS.as_dict(),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
