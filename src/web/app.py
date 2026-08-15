"""HTTP katmanı.

Faz 0 kapsamı: sistemin ayakta olduğunu ve hangi modda çalıştığını gösteren
tek sayfa + sağlık ucu. Orkestrasyon uçları (SSE transkript akışı, görev
başlatma) Faz 5'te eklenecek.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.config import (
    CASSETTES_DIR,
    SELECTIONS_PATH,
    WORKSPACES_ROOT,
    in_container,
    resolve_provider,
)
from src.llm import catalog, factory
from src.llm.catalog import CatalogError
from src.llm.replay_provider import ReplayProvider
from src.llm.selection import SelectionStore
from src.orchestrator.limits import LIMITS
from src.orchestrator.runner import TaskBusy, TaskRunner
from src.security.key_vault import KeyRejected, KeyVault
from src.transcript.library import GameLibrary
from src.transcript.models import Role

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Agent Oyun Atölyesi", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

library = GameLibrary(WORKSPACES_ROOT)

# Anahtarlar süreç belleğinde durur ve konteyner durunca kaybolur (§3.3).
# Tek kullanıcılı yerel çalıştırma varsayımı (V3) gereği tek bir kasa var.
vault = KeyVault()
# Model seçimi sır değil, bir tercihtir — diske yazılır ve yeniden
# başlatmayı aşar. Anahtarlar aksine yalnızca bellekte durur.
selections = SelectionStore(SELECTIONS_PATH)
task_runner = TaskRunner(vault, library, selections=selections)

# Üretilen oyun tarayıcıda çalışır — yani süreç sandbox'ının (§3.3)
# DIŞINDADIR. Oradaki katmanların hiçbiri burada geçerli değil, o yüzden
# tarayıcı tarafında kendi kısıtı gerekir.
#
# Kritik satır `connect-src 'none'`: oyun sayfası fetch/XHR/WebSocket
# açamaz, dolayısıyla dışarı veri aktaramaz. `img-src data:` uzak görsel
# URL'sini de kapatır — bir görsel isteği de sızıntı kanalıdır.
#
# `'self'` yerine açık host yazılmasının sebebi: oyun `sandbox="allow-scripts"`
# ile (allow-same-origin OLMADAN) gömülür, dolayısıyla belge **opak kaynağa**
# sahiptir ve `'self'` sunucuya çözülmez — `logic.js` engellenirdi.
# allow-same-origin verilmemesi bilinçli: verilseydi oyun ana sayfayı
# script'leyip onun ağ erişimini kullanarak bu CSP'yi baypas edebilirdi.
_LOCAL_ORIGINS = "http://localhost:* http://127.0.0.1:*"

GAME_CSP = (
    "default-src 'none'; "
    f"script-src 'unsafe-inline' {_LOCAL_ORIGINS}; "
    f"style-src 'unsafe-inline' {_LOCAL_ORIGINS}; "
    "img-src data: blob:; "
    "media-src data:; "
    "font-src data:; "
    "connect-src 'none'; "
    "form-action 'none'; "
    "frame-src 'none'; "
    "base-uri 'none'"
)


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
    roller = factory.all_roles(vault, selections)
    return {
        "durum": "ayakta",
        "saglayici": provider.name,
        "saglayici_gerekce": provider.reason,
        "cevrimdisi_mod": all(r.saglayici == "replay" for r in roller),
        "roller": [r.as_dict() for r in roller],
        "anahtarlar": [f.as_dict() for f in vault.fingerprints()],
        "kaset_sayisi": ReplayProvider(CASSETTES_DIR).count(),
        "kayit_modu": factory.recording_enabled(),
        "python": platform.python_version(),
        "node": node,
        "konteyner": in_container(),
        "runner_kullanicisi": _runner_user_exists(),
        "workspaces": str(WORKSPACES_ROOT),
        "workspaces_yazilabilir": WORKSPACES_ROOT.is_dir(),
        "limitler": LIMITS.as_dict(),
    }


class TaskInput(BaseModel):
    model_config = {"extra": "forbid"}

    gorev: str = Field(min_length=1, max_length=LIMITS.max_task_chars)


@app.post("/api/gorev")
def start_task(girdi: TaskInput) -> dict[str, object]:
    """Görevi başlatır ve hemen döner; koşu arka planda yürür."""
    try:
        job = task_runner.start(girdi.gorev)
    except TaskBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"durum": job.durum, "baslangic": job.baslangic.isoformat()}


@app.get("/api/gorev")
def task_status() -> dict[str, object]:
    job = task_runner.job
    if job is None:
        return {"durum": "bos"}
    return job.as_dict()


@app.get("/api/gorev/akis")
def task_stream() -> StreamingResponse:
    """Canlı transkript — Server-Sent Events.

    Koşu ayrı bir iş parçacığında yürüyor ve mesajları bir listeye
    biriktiriyor. Akış o listeyi izler ve yeni gelenleri iletir. Kuyruk
    yerine liste kullanılması bilinçli: birden fazla izleyici aynı akışı
    baştan alabilir ve geç bağlanan bir tarayıcı ilk turları kaçırmaz.
    """

    def events():
        gonderilen = 0
        bekleme = 0.0
        while True:
            job = task_runner.job
            if job is None:
                yield _sse("durum", {"durum": "bos"})
                return

            while gonderilen < len(job.mesajlar):
                yield _sse("mesaj", job.mesajlar[gonderilen])
                gonderilen += 1
                bekleme = 0.0

            if job.durum != "calisiyor":
                yield _sse("bitti", {
                    "durum": job.durum,
                    "son_durum": job.son_durum,
                    "gorev_id": job.gorev_id,
                    "rapor": job.rapor,
                    "hata": job.hata,
                })
                return

            time.sleep(0.4)
            bekleme += 0.4
            if bekleme >= 15:  # ara bağlantıların akışı kapatmasını önler
                yield _sse("ping", {})
                bekleme = 0.0

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class KeyInput(BaseModel):
    """Anahtar girişi. `anahtar` alanı hiçbir yanıtta geri dönmez."""

    model_config = {"extra": "forbid"}

    rol: Role
    saglayici: str = Field(min_length=1, max_length=32)
    anahtar: str = Field(min_length=1, max_length=512)


@app.get("/api/anahtarlar")
def list_keys() -> dict[str, object]:
    """Yalnızca maskeli parmak izleri. Anahtarın kendisi asla dönmez."""
    return {"anahtarlar": [f.as_dict() for f in vault.fingerprints()]}


@app.post("/api/anahtarlar")
def set_key(girdi: KeyInput) -> JSONResponse:
    try:
        fingerprint = vault.set(girdi.rol, girdi.saglayici, girdi.anahtar)
    except KeyRejected as exc:
        # KeyRejected mesajı anahtarı asla içermez (§6/T8).
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(
        content=fingerprint.as_dict(),
        headers={"Cache-Control": "no-store"},
    )


@app.delete("/api/anahtarlar")
def clear_keys(rol: Role | None = None) -> dict[str, object]:
    vault.clear(rol)
    return {"temizlendi": rol.value if rol else "hepsi"}


class ModelInput(BaseModel):
    model_config = {"extra": "forbid"}

    rol: Role
    saglayici: str = Field(min_length=1, max_length=32)
    model: str = Field(min_length=1, max_length=128)


@app.get("/api/modeller")
def list_models(saglayici: str, yenile: bool = False) -> dict[str, object]:
    """Sağlayıcının hesaba açık model listesi.

    Liste sabit tutulmaz, sağlayıcıdan alınır: hangi modellere erişildiği
    hesaba göre değişir ve sabit bir liste zamanla yanlışa döner.
    """
    key = _catalog_key(saglayici)
    if not key:
        raise HTTPException(
            status_code=400,
            detail=f"{saglayici} kataloğu için önce bir API anahtarı girin",
        )
    try:
        models = catalog.fetch(saglayici, key, force=yenile)
    except CatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"saglayici": saglayici, "modeller": [m.as_dict() for m in models]}


def _catalog_key(saglayici: str) -> str | None:
    """Katalog için herhangi bir rolün anahtarı yeter."""
    for rol in (Role.PLANLAYICI, Role.UYGULAYICI, Role.DENETLEYICI):
        key = vault.get(rol, saglayici)
        if key:
            return key
    return None


@app.get("/api/modeller/secim")
def get_selection() -> dict[str, object]:
    return {"secimler": selections.as_dict()}


@app.post("/api/modeller/secim")
def set_selection(girdi: ModelInput) -> dict[str, object]:
    try:
        secim = selections.set(girdi.rol, girdi.saglayici, girdi.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"rol": girdi.rol.value, **secim.as_dict()}


@app.delete("/api/modeller/secim")
def clear_selection(rol: Role | None = None) -> dict[str, object]:
    selections.clear(rol)
    return {"temizlendi": rol.value if rol else "hepsi"}


@app.get("/api/oyunlar")
def list_games() -> dict[str, object]:
    """Üretilmiş tüm oyunlar, en yeniden eskiye.

    Liste ayrı bir indeks dosyasından değil, her görevin transkriptinden
    türetilir; iki kaydın birbirinden sapması imkânsız olur.
    """
    entries = library.entries()
    return {
        "oyunlar": [e.as_dict() for e in entries],
        "toplam": len(entries),
        "oynanabilir": sum(1 for e in entries if e.oynanabilir),
    }


@app.get("/api/oyunlar/{gorev_id}")
def get_game(gorev_id: str) -> dict[str, object]:
    entry = library.get(gorev_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="görev bulunamadı")
    return entry.as_dict()


@app.delete("/api/oyunlar/{gorev_id}")
def delete_game(gorev_id: str) -> dict[str, object]:
    if not library.delete(gorev_id):
        raise HTTPException(status_code=404, detail="görev bulunamadı")
    return {"silindi": gorev_id}


@app.get("/oyun/{gorev_id}/{dosya}")
def serve_game_file(gorev_id: str, dosya: str) -> FileResponse:
    """Üretilen oyun dosyasını sunar.

    İki katmanlı koruma: dosya adı izin listesinde olmalı ve görev kimliği
    yol korumasından geçmeli (`..` veya mutlak yol kabul edilmez). Yanıta
    oyun sayfası için sıkı CSP eklenir.
    """
    path = library.file_path(gorev_id, dosya)
    if path is None:
        raise HTTPException(status_code=404, detail="dosya bulunamadı")
    return FileResponse(
        path,
        headers={
            "Content-Security-Policy": GAME_CSP,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
