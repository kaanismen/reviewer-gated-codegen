"""Mesaj şeması — PROJECT.md §7.

Alan adları burada Türkçedir; §11 bu istisnayı yalnızca mesaj şeması için
tanır, çünkü bunlar tel üzerindeki iş alanı terimleridir. Sınıf adları ve
türetilmiş özellikler İngilizcedir.

Tek takma ad `not` alanındadır: Python'da ayrılmış sözcük olduğu için
`note` özelliğine `alias="not"` ile bağlanmıştır.
"""

from __future__ import annotations

import re
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


class FeasibilityVerdict(str, Enum):
    UYGUN = "UYGUN"
    UYGUN_DEGIL = "UYGUN_DEGIL"


# Bilinen-iyi oyunlar. Bir izin listesi DEĞİLDİR: uygulanabilirlik kapısını
# (§2.1) kesin geçtiği bilinen örneklerdir, kural kartı deposunun çekirdeği
# ve testlerin sabit zeminidir. Listede olmayan bir oyun reddedilmez —
# değerlendirilir.
KNOWN_GOOD_GAMES: frozenset[str] = frozenset(
    {"tic-tac-toe", "snake", "pong", "breakout"}
)

# Türkçe küçük harf kuralı; oyun adı normalleştirmesinde kullanılır.
_TR_LOWER = str.maketrans({"İ": "i", "I": "ı"})

# Bir oyunun "kural karmaşıklığı" ölçütünün sayısal karşılığı. Şema iş kuralı
# olduğu için limits.py'de değil burada durur — gerekçe uzunluğu sınırları da
# öyle. transcript katmanının orchestrator'a bağımlı olması ayrıca §3.1'deki
# tek yönlü bağımlılık kuralını çiğnerdi.
MAX_SPECIAL_CASES = 10


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


class Feasibility(BaseModel):
    """Planlayıcının uygulanabilirlik değerlendirmesi.

    İsim listesi yerine ölçüt: bir oyun adı bilinmediği için değil, ölçütü
    geçemediği için kapsam dışı kalır. Değerlendirme serbest metin değil
    yapısal veri olarak döner ki denetlenebilsin ve sınanabilsin.
    """

    model_config = ConfigDict(extra="forbid")

    karar: FeasibilityVerdict
    gerekce: str = Field(min_length=10, max_length=500)
    ozel_durum_sayisi: int = Field(ge=0)
    gerekli_ozellikler: list[str] = Field(default_factory=list)
    gercek_zamanli: bool = False
    harici_varlik_gerekli: bool = False


class PlannerContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    oyun: str = Field(min_length=1, max_length=60)
    uygulanabilirlik: Feasibility
    adimlar: list[str] = Field(default_factory=list, max_length=6)
    kabul_kriterleri: list[str] = Field(default_factory=list)
    dosyalar: list[str] = Field(default_factory=list)

    @field_validator("oyun")
    @classmethod
    def _normalize_game(cls, value: str) -> str:
        """Serbest yazılan oyun adını kanonik biçime indirger.

        "Connect 4", "connect-4" ve "CONNECT 4" aynı oyundur; kural kartı
        araması ve kaset eşleşmesi bu biçime dayanır.
        """
        slug = re.sub(r"[\s_]+", "-", value.translate(_TR_LOWER).lower().strip())
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        if not slug:
            raise ValueError("oyun adı boş olamaz")
        return slug

    @field_validator("adimlar", "kabul_kriterleri", "dosyalar")
    @classmethod
    def _no_blank(cls, value: list[str]) -> list[str]:
        return _no_blank_items(value)

    @model_validator(mode="after")
    def _plan_shape_matches_verdict(self) -> "PlannerContent":
        """İçerik ya bir plandır ya bir rettir; ikisinin ortası yoktur."""
        if self.uygulanabilirlik.karar is FeasibilityVerdict.UYGUN:
            if not 2 <= len(self.adimlar) <= 6:
                raise ValueError("UYGUN kararında 2–6 adım zorunludur")
            if not self.kabul_kriterleri:
                raise ValueError("UYGUN kararında en az bir kabul kriteri zorunludur")
            if not self.dosyalar:
                raise ValueError("UYGUN kararında üretilecek dosyalar belirtilmelidir")
        else:
            if self.adimlar or self.kabul_kriterleri or self.dosyalar:
                raise ValueError(
                    "UYGUN_DEGIL kararında plan alanları boş olmalıdır"
                )
        return self

    @property
    def effective_verdict(self) -> FeasibilityVerdict:
        """§7.2 iş kuralı: planlayıcı kendi ölçümüyle çelişemez.

        §7.4'teki denetleyici kuralının eşleniği. İki geçersiz kılma nedeni
        de mevcut spesifikasyondan türetilmiştir, yeni kural icat edilmemiştir:
        harici varlık ihtiyacı §2.2'de zaten kapsam dışıdır; özel durum
        tavanı ise "kural karmaşıklığı" ölçütünün sayısal karşılığıdır.
        """
        if self.uygulanabilirlik.karar is FeasibilityVerdict.UYGUN_DEGIL:
            return FeasibilityVerdict.UYGUN_DEGIL
        if self.uygulanabilirlik.harici_varlik_gerekli:
            return FeasibilityVerdict.UYGUN_DEGIL
        if self.uygulanabilirlik.ozel_durum_sayisi > MAX_SPECIAL_CASES:
            return FeasibilityVerdict.UYGUN_DEGIL
        return FeasibilityVerdict.UYGUN

    @property
    def override_reason(self) -> str | None:
        if self.effective_verdict is self.uygulanabilirlik.karar:
            return None
        if self.uygulanabilirlik.harici_varlik_gerekli:
            return (
                "Planlayıcı UYGUN dedi ama harici varlık gerektiğini bildirdi; "
                "tek dosyalık teslim kısıtı gereği kapsam dışı (§2.2)."
            )
        return (
            f"Planlayıcı UYGUN dedi ama {self.uygulanabilirlik.ozel_durum_sayisi} "
            f"özel durum bildirdi; tavan {MAX_SPECIAL_CASES} (§7.2)."
        )

    @property
    def is_known_good(self) -> bool:
        return self.oyun in KNOWN_GOOD_GAMES


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
    def _rejection_must_be_actionable(self) -> "ReviewerContent":
        """RED, uygulayıcıya iş verecek kadar somut olmalıdır.

        Gerekçesiz veya bulgusuz bir red, revizyon turunu boşa harcar:
        uygulayıcı neyi düzelteceğini bilemez, denetleyici aynı gerekçeyle
        tekrar reddeder ve sistem ilerleme-yok tespitiyle durur.
        """
        if self.karar is Decision.RED:
            if not self.gerekce.strip():
                raise ValueError("RED kararı için gerekçe boş olamaz")
            if not self.bulgular:
                raise ValueError("RED kararı en az bir bulgu içermelidir")
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
