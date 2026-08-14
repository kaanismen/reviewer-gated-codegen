"""Test yardımcıları — geçerli nesneleri tek satırda kurmak için.

Testler bir kuralı sınamalı, nesne kurmayı değil. Fabrikalar varsayılan
olarak GEÇERLİ nesne üretir; her test yalnızca sınadığı alanı değiştirir.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.orchestrator.limits import Limits
from src.transcript.models import (
    AgentMessage,
    Decision,
    Finding,
    Game,
    ImplementerContent,
    PlannerContent,
    ReviewerContent,
    Role,
    Severity,
    TestResult,
    ToolCall,
    WrittenFile,
)


def make_plan(**overrides) -> PlannerContent:
    data = {
        "oyun": Game.TIC_TAC_TOE,
        "adimlar": ["mantığı yaz", "testleri yaz", "arayüzü yaz"],
        "kabul_kriterleri": ["üç aynı işaret kazanır"],
        "dosyalar": ["logic.js", "logic.test.js", "game.html"],
    }
    return PlannerContent(**{**data, **overrides})


def make_implementation(**overrides) -> ImplementerContent:
    data = {
        "yazilan_dosyalar": [WrittenFile(yol="logic.js", bayt=512, hash="ab12cd34ef56")],
        "arac_cagrilari": [ToolCall(arac="fs_mcp.write", ozet="logic.js")],
    }
    return ImplementerContent(**{**data, **overrides})


def make_review(
    karar: Decision = Decision.RED,
    gerekce: str = "kazanma kontrolü çapraz hatları atlıyor",
    gecen: int = 1,
    kalan: int = 1,
    bulgular: list[Finding] | None = None,
) -> ReviewerContent:
    return ReviewerContent(
        karar=karar,
        gerekce=gerekce,
        bulgular=bulgular if bulgular is not None else [],
        test_sonucu=TestResult(gecen=gecen, kalan=kalan, cikti="# fail 1"),
    )


def make_accepted_review(**overrides) -> ReviewerContent:
    return make_review(
        karar=Decision.KABUL,
        gerekce="tüm testler geçti, mantık kabul kriterlerini karşılıyor",
        gecen=4,
        kalan=0,
        **overrides,
    )


def make_message(rol: Role = Role.DENETLEYICI, **overrides) -> AgentMessage:
    icerik = {
        Role.PLANLAYICI: make_plan,
        Role.UYGULAYICI: make_implementation,
        Role.DENETLEYICI: make_review,
    }
    data: dict[str, object] = {"tur": 1, "rol": rol}
    if rol is Role.SISTEM:
        from src.transcript.models import SystemContent

        data["icerik"] = SystemContent(olay="durum_degisti", ayrinti="PLANLANIYOR")
    else:
        data["icerik"] = icerik[rol]()
        data["prompt_surumu"] = f"{rol.value}.v1"
        data["prompt_hash"] = "0123456789ab"
        data["model"] = "claude-opus-5"
        data["token_girdi"] = 1000
        data["token_cikti"] = 400
        data["maliyet_usd"] = Decimal("0.01500")
    return AgentMessage(**{**data, **overrides})


class FakeClock:
    """Elle ilerletilen saat — süre aşımı testleri gerçekten beklemesin."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def limits() -> Limits:
    """Varsayılan limitler — ortam değişkenlerinden bağımsız.

    LIMITS küresel nesnesi .env'den etkilenir; testler ondan değil bundan
    beslenir ki makineye göre sonuç değişmesin.
    """
    return Limits()


# Fabrikaları fixture olarak da sun
@pytest.fixture
def plan() -> PlannerContent:
    return make_plan()
