"""Model kataloğu — sağlayıcıdan canlı model listesi.

Sabit bir model listesi tutmanın iki sorunu var: listedeki modeller
zamanla kaybolur, ve **kullanıcının hesabında hangi modellerin bulunduğunu
bilemeyiz**. Bu yüzden liste sağlayıcının kendi `/v1/models` ucundan
alınır.

İki sağlayıcıda da REST kullanılıyor. Anthropic tarafında SDK var ama tek
bir listeleme çağrısı için iki farklı kod yolu tutmanın karşılığı yok;
istek şekli de kimlik doğrulama başlığı dışında aynı.

Sonuçlar bellekte önbelleğe alınır: katalog her açılışta değişmez ve
arayüz her açıldığında sağlayıcıya istek atmak gereksiz.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import httpx

from src.llm import pricing

CACHE_TTL_SEC = 900
TIMEOUT_SEC = 20

# Sohbet dışı modeller (görsel, ses, gömme, transkripsiyon) kataloğa girmez:
# bu sistemde hiçbirinin karşılığı yok, listede durmaları seçimi zorlaştırır.
_EXCLUDE = re.compile(
    r"(image|audio|tts|transcribe|whisper|realtime|embed|moderation|search|"
    r"diarize|live|instruct|codex)",
    re.IGNORECASE,
)


class CatalogError(RuntimeError):
    """Katalog alınamadı. Mesajı anahtarı içermez."""


@dataclass(frozen=True)
class ModelInfo:
    id: str
    ad: str
    saglayici: str
    fiyat_bilinen: bool
    girdi_usd: str = ""
    cikti_usd: str = ""

    @property
    def etiket(self) -> str:
        if self.fiyat_bilinen and self.girdi_usd:
            return f"{self.ad} · ${self.girdi_usd}/${self.cikti_usd} /MTok"
        return f"{self.ad} · fiyat bilinmiyor"

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "ad": self.ad,
            "saglayici": self.saglayici,
            "fiyat_bilinen": self.fiyat_bilinen,
            "girdi_usd": self.girdi_usd,
            "cikti_usd": self.cikti_usd,
            "etiket": self.etiket,
        }


def _describe(model_id: str, saglayici: str, ad: str = "") -> ModelInfo:
    (girdi, cikti), bilinen = pricing.price_for(model_id)
    return ModelInfo(
        id=model_id,
        ad=ad or model_id,
        saglayici=saglayici,
        fiyat_bilinen=bilinen,
        girdi_usd=str(girdi) if bilinen else "",
        cikti_usd=str(cikti) if bilinen else "",
    )


def _fetch_anthropic(key: str) -> list[ModelInfo]:
    response = httpx.get(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
        params={"limit": 100},
        timeout=TIMEOUT_SEC,
    )
    _raise_for_status(response, "anthropic")
    return [
        _describe(m["id"], "anthropic", m.get("display_name", ""))
        for m in response.json().get("data", [])
    ]


def _fetch_openai(key: str) -> list[ModelInfo]:
    response = httpx.get(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=TIMEOUT_SEC,
    )
    _raise_for_status(response, "openai")
    return [
        _describe(m["id"], "openai")
        for m in response.json().get("data", [])
        if m.get("id", "").startswith(("gpt-", "o1", "o3", "o4"))
    ]


def _raise_for_status(response: httpx.Response, saglayici: str) -> None:
    if response.status_code < 400:
        return
    if response.status_code in (401, 403):
        raise CatalogError(f"{saglayici}: anahtar geçersiz veya yetkisiz")
    raise CatalogError(f"{saglayici}: katalog alınamadı ({response.status_code})")


_FETCHERS = {"anthropic": _fetch_anthropic, "openai": _fetch_openai}

# saglayici -> (zaman, modeller)
_CACHE: dict[str, tuple[float, list[ModelInfo]]] = {}


def fetch(saglayici: str, key: str, force: bool = False) -> list[ModelInfo]:
    """Sağlayıcının model listesini döndürür; sohbet dışı modeller elenir."""
    saglayici = saglayici.strip().lower()
    fetcher = _FETCHERS.get(saglayici)
    if fetcher is None:
        raise CatalogError(f"katalog desteklenmiyor: {saglayici}")
    if not key:
        raise CatalogError(f"{saglayici} için API anahtarı gerekli")

    cached = _CACHE.get(saglayici)
    if cached and not force and time.monotonic() - cached[0] < CACHE_TTL_SEC:
        return cached[1]

    try:
        models = fetcher(key)
    except httpx.HTTPError as exc:
        raise CatalogError(f"{saglayici}: bağlantı hatası ({type(exc).__name__})") from exc

    models = [m for m in models if not _EXCLUDE.search(m.id)]
    # Bilinen fiyatlılar önce, sonra ada göre ters (yeni sürümler üstte).
    models.sort(key=lambda m: (not m.fiyat_bilinen, m.id), reverse=False)
    _CACHE[saglayici] = (time.monotonic(), models)
    return models


def clear_cache() -> None:
    _CACHE.clear()
