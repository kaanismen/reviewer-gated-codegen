"""Sağlayıcı sözleşmesi — PROJECT.md §8.2.

**Orkestratör hangi sağlayıcının çalıştığını bilmez.** Tek bir yöntem vardır:
sistem promptu + mesaj listesi al, metin + token sayısı + maliyet döndür.
Sağlayıcı değişimi tek satır yapılandırma değişikliğidir.

İki tasarım kararı bu dosyada yaşıyor:

1. **İstek parmak izi burada üretilir**, sağlayıcıda değil. Aynı istek hangi
   sağlayıcıya giderse gitsin aynı kaset anahtarını üretir; record/replay
   sağlayıcıdan bağımsızdır.
2. **Hata mesajları gizlemeden geçer.** Sağlayıcı istisnaları istek
   başlıklarını veya anahtarı taşıyabilir; `ProviderError` mesajı transkripte
   ve arayüze düşeceği için ham bırakılamaz.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from src.llm import pricing

DEFAULT_MAX_TOKENS = 16_000


class ProviderError(RuntimeError):
    """Sağlayıcı kaynaklı hata. Mesajı gizlemeden geçmiştir."""


class ProviderAuthError(ProviderError):
    """Anahtar yok, geçersiz veya yetkisiz."""


class ProviderRateLimited(ProviderError):
    """Kota veya hız sınırı."""


class ProviderUnavailable(ProviderError):
    """Ağ hatası veya sunucu tarafı arıza."""


class CassetteMissing(ProviderError):
    """Replay modunda bu istek için kayıt yok."""


@dataclass(frozen=True)
class Message:
    rol: str  # "user" | "assistant"
    icerik: str


@dataclass(frozen=True)
class LlmRequest:
    system: str
    messages: tuple[Message, ...]
    model: str
    max_tokens: int = DEFAULT_MAX_TOKENS

    def canonical(self) -> dict[str, object]:
        """Parmak izinin hesaplandığı kanonik biçim.

        Sistem promptunun tamamı yerine hash'i kullanılır: prompt dosyaları
        zaten depoda sürümlü duruyor, kasette ikinci kopya tutmak gereksiz
        ve senkronizasyon riski.
        """
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system_sha256": hashlib.sha256(self.system.encode("utf-8")).hexdigest()[:16],
            "messages": [{"rol": m.rol, "icerik": m.icerik} for m in self.messages],
        }

    def fingerprint(self) -> str:
        payload = json.dumps(self.canonical(), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Usage:
    token_girdi: int = 0
    token_cikti: int = 0
    onbellek_yazma: int = 0
    onbellek_okuma: int = 0
    maliyet_usd: Decimal = Decimal("0")

    @property
    def toplam_token(self) -> int:
        return self.token_girdi + self.token_cikti

    def as_dict(self) -> dict[str, object]:
        return {
            "token_girdi": self.token_girdi,
            "token_cikti": self.token_cikti,
            "onbellek_yazma": self.onbellek_yazma,
            "onbellek_okuma": self.onbellek_okuma,
            "maliyet_usd": str(self.maliyet_usd),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Usage":
        return cls(
            token_girdi=int(data.get("token_girdi") or 0),
            token_cikti=int(data.get("token_cikti") or 0),
            onbellek_yazma=int(data.get("onbellek_yazma") or 0),
            onbellek_okuma=int(data.get("onbellek_okuma") or 0),
            maliyet_usd=Decimal(str(data.get("maliyet_usd") or "0")),
        )

    @classmethod
    def priced(
        cls,
        model: str,
        token_girdi: int,
        token_cikti: int,
        onbellek_yazma: int = 0,
        onbellek_okuma: int = 0,
    ) -> "Usage":
        return cls(
            token_girdi=token_girdi,
            token_cikti=token_cikti,
            onbellek_yazma=onbellek_yazma,
            onbellek_okuma=onbellek_okuma,
            maliyet_usd=pricing.estimate_cost(
                model, token_girdi, token_cikti, onbellek_yazma, onbellek_okuma
            ),
        )


@dataclass(frozen=True)
class LlmResponse:
    metin: str
    kullanim: Usage
    model: str
    saglayici: str
    durdurma_nedeni: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "metin": self.metin,
            "model": self.model,
            "saglayici": self.saglayici,
            "durdurma_nedeni": self.durdurma_nedeni,
            "kullanim": self.kullanim.as_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LlmResponse":
        return cls(
            metin=str(data.get("metin") or ""),
            kullanim=Usage.from_dict(data.get("kullanim") or {}),
            model=str(data.get("model") or ""),
            saglayici=str(data.get("saglayici") or ""),
            durdurma_nedeni=str(data.get("durdurma_nedeni") or ""),
        )


Redactor = Callable[[str], str]


def _identity(text: str) -> str:
    return text


class LlmProvider(ABC):
    """Tüm sağlayıcıların uyduğu tek sözleşme."""

    name: str = "temel"

    def __init__(self, redactor: Redactor | None = None) -> None:
        self._redact = redactor or _identity

    @abstractmethod
    def complete(self, request: LlmRequest) -> LlmResponse:
        """Tek çağrı. Hata durumunda `ProviderError` türevi fırlatır."""

    # -- yardımcılar --------------------------------------------------------

    def safe(self, text: str, limit: int = 400) -> str:
        """Dışarıya çıkacak metni gizlemeden geçirir ve kısaltır.

        Sağlayıcı istisnaları istek gövdesini veya `Authorization` başlığını
        içerebilir; bu metin transkripte ve arayüze gider.
        """
        cleaned = self._redact(text)
        return cleaned if len(cleaned) <= limit else cleaned[:limit] + "…"

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r}>"
