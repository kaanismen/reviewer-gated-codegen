"""Mesaj şeması — PROJECT.md §7.

Alan adları burada Türkçedir; §11 bu istisnayı yalnızca mesaj şeması için
tanır, çünkü bunlar tel üzerindeki iş alanı terimleridir. Sınıf adları ve
türetilmiş özellikler İngilizcedir.

Tek takma ad `not` alanındadır: Python'da ayrılmış sözcük olduğu için
`note` özelliğine `alias="not"` ile bağlanmıştır.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Union
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# --------------------------------------------------------------------------
# Sabit kümeler
# --------------------------------------------------------------------------


class Role(str, Enum):
    PLANLAYICI = "planlayici"
    UYGULAYICI = "uygulayici"
    DENETLEYICI = "denetleyici"
    SISTEM = "sistem"


class Game(str, Enum):
    TIC_TAC_TOE = "tic-tac-toe"
    SNAKE = "snake"
    PONG = "pong"
    BREAKOUT = "breakout"


class Decision(str, Enum):
    KABUL = "KABUL"
    RED = "RED"


class Severity(str, Enum):
    KRITIK = "kritik"
    ORTA = "orta"
    DUSUK = "dusuk"


AGENT_ROLES = frozenset({Role.PLANLAYICI, Role.UYGULAYICI, Role.DENETLEYICI})


def _no_blank_items(items: list[str]) -> list[str]:
    cleaned = [item.strip() for item in items]
    if any(not item for item in cleaned):
        raise ValueError("liste boş öğe içeremez")
    return cleaned


# --------------------------------------------------------------------------
# §7.2 planlayıcı
# --------------------------------------------------------------------------


class PlannerContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    oyun: Game
    adimlar: list[str] = Field(min_length=2, max_length=6)
    kabul_kriterleri: list[str] = Field(min_length=1)
    dosyalar: list[str] = Field(min_length=1)

    @field_validator("adimlar", "kabul_kriterleri", "dosyalar")
    @classmethod
    def _no_blank(cls, value: list[str]) -> list[str]:
        return _no_blank_items(value)


# --------------------------------------------------------------------------
# §7.3 uygulayıcı
# --------------------------------------------------------------------------


class WrittenFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yol: str = Field(min_length=1)
    bayt: int = Field(ge=0)
    hash: str = Field(min_length=8)


class ToolCall(BaseModel):
    """MCP/araç çağrı kaydı.

    §7.3 bu alanı zorunlu kılar ama iç şemasını tanımlamaz; şema Faz 1'de
    burada somutlaştırılmıştır (bkz. PROJECT.md v1.4 değişiklik kaydı).
    """

    model_config = ConfigDict(extra="forbid")

    arac: str = Field(min_length=1)
    ozet: str = ""
    basarili: bool = True


class ImplementerContent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    yazilan_dosyalar: list[WrittenFile] = Field(min_length=1)
    arac_cagrilari: list[ToolCall]
    note: str | None = Field(default=None, alias="not")


# --------------------------------------------------------------------------
# §7.4 denetleyici — kritik şema
# --------------------------------------------------------------------------


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dosya: str = Field(min_length=1)
    sorun: str = Field(min_length=1)
    onem: Severity


class TestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gecen: int = Field(ge=0)
    kalan: int = Field(ge=0)
    cikti: str = ""


class ReviewerContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    karar: Decision
    gerekce: str = Field(min_length=10, max_length=500)
    bulgular: list[Finding]
    test_sonucu: TestResult

    @model_validator(mode="after")
    def _gerekce_required_for_rejection(self) -> "ReviewerContent":
        if self.karar is Decision.RED and not self.gerekce.strip():
            raise ValueError("RED kararı için gerekçe boş olamaz")
        return self

    @property
    def effective_decision(self) -> Decision:
        """§7.4 iş kuralı: denetleyici kendi test sonucuyla çelişemez.

        `karar = KABUL` iken başarısız test varsa karar RED sayılır. Bu kural
        modelde durur, orkestratörde değil: kararı okuyan HER yer aynı sonucu
        görmeli, kuralı uygulamayı unutan bir çağrı yeri olmamalı.
        """
        if self.karar is Decision.KABUL and self.test_sonucu.kalan > 0:
            return Decision.RED
        return self.karar

    @property
    def override_reason(self) -> str | None:
        """Karar geçersiz kılındıysa nedeni; transkripte yazılır."""
        if self.effective_decision is not self.karar:
            return (
                f"Denetleyici KABUL dedi ama {self.test_sonucu.kalan} test "
                f"başarısız; karar RED'e çevrildi (§7.4)."
            )
        return None


# --------------------------------------------------------------------------
# sistem mesajları — durum geçişleri ve limit raporları
# --------------------------------------------------------------------------


class SystemContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    olay: str = Field(min_length=1)
    ayrinti: str = ""


Content = Union[PlannerContent, ImplementerContent, ReviewerContent, SystemContent]

_CONTENT_FOR_ROLE: dict[Role, type[BaseModel]] = {
    Role.PLANLAYICI: PlannerContent,
    Role.UYGULAYICI: ImplementerContent,
    Role.DENETLEYICI: ReviewerContent,
    Role.SISTEM: SystemContent,
}


# --------------------------------------------------------------------------
# §7.1 ortak zarf
# --------------------------------------------------------------------------


class AgentMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    tur: int = Field(ge=0)
    rol: Role
    zaman: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    icerik: Content
    prompt_surumu: str | None = None
    prompt_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{12}$")
    model: str | None = None
    token_girdi: int = Field(default=0, ge=0)
    token_cikti: int = Field(default=0, ge=0)
    maliyet_usd: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=5)

    @field_validator("zaman")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _content_matches_role(self) -> "AgentMessage":
        expected = _CONTENT_FOR_ROLE[self.rol]
        if not isinstance(self.icerik, expected):
            raise ValueError(
                f"rol={self.rol.value} için içerik {expected.__name__} olmalı, "
                f"{type(self.icerik).__name__} geldi"
            )
        return self

    @model_validator(mode="after")
    def _provenance_required_for_agents(self) -> "AgentMessage":
        """Denetlenebilirlik: bir agent mesajı hangi prompt sürümünden ve hangi
        modelden çıktığını kanıtlamadan transkripte giremez (§9).

        §7.1 bu üç alanı koşulsuz zorunlu sayar; sistem mesajlarının promptu
        olmadığı için kural rol bazlı hale getirilmiştir (PROJECT.md v1.4).
        """
        if self.rol in AGENT_ROLES:
            missing = [
                name
                for name in ("prompt_surumu", "prompt_hash", "model")
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(
                    f"agent mesajında zorunlu köken alanları eksik: {', '.join(missing)}"
                )
        return self
