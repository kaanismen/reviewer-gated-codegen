"""Uygulanabilirlik kapısı — PROJECT.md §2.1 ve §7.2.

Kapsam artık isim listesiyle değil ölçütle belirlenir. Bu dosya iki şeyi
sınar: ölçütün listede olmayan oyunları kabul ettiğini, ve planlayıcının
kendi ölçümüyle çelişemediğini.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.transcript.models import (
    MAX_SPECIAL_CASES,
    FeasibilityVerdict,
    PlannerContent,
)
from tests.conftest import make_feasibility, make_plan, make_refusal


# --------------------------------------------------------------------------
# Kapsam artık bir liste değil
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "oyun", ["connect-4", "othello", "2048", "minesweeper", "reversi"]
)
def test_listede_olmayan_oyunlar_reddedilmez(oyun):
    """Eski enum bunları kapsam dışı sayardı; ölçüt saymıyor."""
    plan = make_plan(oyun=oyun)
    assert plan.effective_verdict is FeasibilityVerdict.UYGUN
    assert plan.is_known_good is False


def test_bilinen_iyi_oyunlar_isaretlenir():
    assert make_plan(oyun="snake").is_known_good is True


@pytest.mark.parametrize(
    "yazim,beklenen",
    [
        ("Connect 4", "connect-4"),
        ("CONNECT-4", "connect-4"),
        ("  connect   4  ", "connect-4"),
        ("tic_tac_toe", "tic-tac-toe"),
        ("İkili Satranç", "ikili-satranç"),
    ],
)
def test_oyun_adi_kanonik_bicime_indirgenir(yazim, beklenen):
    """Kural kartı araması ve kaset eşleşmesi bu biçime dayanır."""
    assert make_plan(oyun=yazim).oyun == beklenen


def test_bos_oyun_adi_reddedilir():
    with pytest.raises(ValidationError):
        make_plan(oyun="   ")


# --------------------------------------------------------------------------
# İçerik ya plandır ya rettir
# --------------------------------------------------------------------------


def test_ret_icerigi_plan_alanlarini_bos_birakir():
    refusal = make_refusal()
    assert refusal.effective_verdict is FeasibilityVerdict.UYGUN_DEGIL
    assert refusal.adimlar == []
    assert refusal.kabul_kriterleri == []


def test_ret_icerigi_plan_tasiyamaz():
    with pytest.raises(ValidationError, match="UYGUN_DEGIL"):
        make_refusal(adimlar=["yine de deneyelim", "bakalım"])


def test_uygun_karari_kabul_kriteri_olmadan_gecersiz():
    with pytest.raises(ValidationError, match="kabul kriteri"):
        make_plan(kabul_kriterleri=[])


def test_uygun_karari_adim_sayisina_tabi():
    with pytest.raises(ValidationError, match="adım"):
        make_plan(adimlar=["tek adım"])
    with pytest.raises(ValidationError):
        make_plan(adimlar=[f"adım {i}" for i in range(7)])


# --------------------------------------------------------------------------
# §7.2 iş kuralı — planlayıcı kendi ölçümüyle çelişemez
# --------------------------------------------------------------------------


def test_ozel_durum_tavani_asilirsa_uygun_karari_gecersiz():
    plan = make_plan(
        uygulanabilirlik=make_feasibility(ozel_durum_sayisi=MAX_SPECIAL_CASES + 1)
    )
    assert plan.uygulanabilirlik.karar is FeasibilityVerdict.UYGUN  # ham alan
    assert plan.effective_verdict is FeasibilityVerdict.UYGUN_DEGIL
    assert "özel durum" in (plan.override_reason or "")


def test_tam_tavanda_uygun_kalir():
    plan = make_plan(
        uygulanabilirlik=make_feasibility(ozel_durum_sayisi=MAX_SPECIAL_CASES)
    )
    assert plan.effective_verdict is FeasibilityVerdict.UYGUN


def test_harici_varlik_gerekiyorsa_uygun_karari_gecersiz():
    """§2.2 harici görsel/ses varlıklarını zaten kapsam dışı bırakıyor.

    Yeni bir kural icat edilmiyor; var olan kapsam kuralı ölçüte bağlanıyor.
    """
    plan = make_plan(uygulanabilirlik=make_feasibility(harici_varlik_gerekli=True))
    assert plan.effective_verdict is FeasibilityVerdict.UYGUN_DEGIL
    assert "harici varlık" in (plan.override_reason or "")


def test_gercek_zamanli_olmak_tek_basina_diskalifiye_etmez():
    """Pong ve breakout gerçek zamanlıdır ve kapsam içindedir."""
    plan = make_plan(oyun="pong", uygulanabilirlik=make_feasibility(gercek_zamanli=True))
    assert plan.effective_verdict is FeasibilityVerdict.UYGUN


def test_tutarli_kararda_gecersiz_kilma_nedeni_yok():
    assert make_plan().override_reason is None


def test_degerlendirme_serbest_metin_degil_yapisal():
    """Gerekçe zorunlu ve sınırlı; "olmaz" diye geçiştirilemez."""
    with pytest.raises(ValidationError):
        make_plan(uygulanabilirlik={"karar": "UYGUN", "ozel_durum_sayisi": 1})

    with pytest.raises(ValidationError):
        make_plan(uygulanabilirlik=make_feasibility(gerekce="olmaz").model_dump())


def test_negatif_ozel_durum_sayisi_reddedilir():
    with pytest.raises(ValidationError):
        PlannerContent.model_validate(
            {
                "oyun": "snake",
                "uygulanabilirlik": {
                    "karar": "UYGUN",
                    "gerekce": "yeterince basit bir oyun mantığı",
                    "ozel_durum_sayisi": -1,
                },
                "adimlar": ["a", "b"],
                "kabul_kriterleri": ["c"],
                "dosyalar": ["logic.js"],
            }
        )
