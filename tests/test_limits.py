"""Kontrol limitleri — PROJECT.md §5, tehdit T6.

Sınır durumları sahte saatle sınanır; hiçbir test gerçekten beklemez.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.orchestrator.limits import BudgetTracker, Limits


# --------------------------------------------------------------------------
# Yapılandırma
# --------------------------------------------------------------------------


def test_varsayilanlar_projectmd_ile_uyumlu():
    limits = Limits()
    assert limits.max_turns == 5
    assert limits.max_tokens_total == 150_000
    assert limits.max_cost_usd == Decimal("1.00")
    assert limits.max_duration_sec == 300
    assert limits.sandbox_timeout_sec == 30
    assert limits.no_progress_threshold == 2
    assert limits.max_task_chars == 2_000


def test_ortam_degiskeni_limiti_gecersiz_kilar(monkeypatch):
    monkeypatch.setenv("MAX_TUR", "3")
    monkeypatch.setenv("MAX_MALIYET_USD", "0.25")
    limits = Limits.from_env()
    assert limits.max_turns == 3
    assert limits.max_cost_usd == Decimal("0.25")


@pytest.mark.parametrize("value", ["0", "-1", "abc", ""])
def test_gecersiz_deger_varsayilana_duser(monkeypatch, value):
    """Sıfır veya bozuk bir tavan, limitin sessizce kapanması demek olurdu.

    Yanlış yapılandırma bir korumayı devre dışı bırakmamalı; varsayılana
    dönmek güvenli taraftır.
    """
    monkeypatch.setenv("MAX_TUR", value)
    assert Limits.from_env().max_turns == 5


# --------------------------------------------------------------------------
# Bütçe izleme
# --------------------------------------------------------------------------


def test_temiz_baslangicta_ihlal_yok(clock, limits):
    tracker = BudgetTracker(limits, clock)
    assert tracker.check(turn=1) is None


def test_tur_tavani_asilinca_ihlal(clock, limits):
    tracker = BudgetTracker(limits, clock)
    assert tracker.check(turn=5) is None
    breach = tracker.check(turn=6)
    assert breach is not None and breach.limit_name == "MAX_TUR"


def test_token_tavani(clock, limits):
    tracker = BudgetTracker(limits, clock)
    tracker.add_usage(100_000, 50_000, Decimal("0"))
    assert tracker.check(turn=1) is None  # tam tavanda, henüz aşılmadı
    tracker.add_usage(1, 0, Decimal("0"))
    breach = tracker.check(turn=1)
    assert breach is not None and breach.limit_name == "MAX_TOKEN_TOPLAM"


def test_maliyet_tavani(clock, limits):
    tracker = BudgetTracker(limits, clock)
    tracker.add_usage(0, 0, Decimal("1.01"))
    breach = tracker.check(turn=1)
    assert breach is not None and breach.limit_name == "MAX_MALIYET_USD"
    assert "1.01" in breach.detail


def test_duvar_saati_tavani(clock, limits):
    tracker = BudgetTracker(limits, clock)
    clock.advance(300)
    assert tracker.check(turn=1) is None
    clock.advance(1)
    breach = tracker.check(turn=1)
    assert breach is not None and breach.limit_name == "MAX_SURE_SN"


def test_ihlal_sirasi_tur_once(clock, limits):
    """Aynı anda birden fazla tavan dolduysa en anlaşılır gerekçe verilir."""
    tracker = BudgetTracker(limits, clock)
    tracker.add_usage(200_000, 0, Decimal("5"))
    clock.advance(9_999)
    breach = tracker.check(turn=99)
    assert breach is not None and breach.limit_name == "MAX_TUR"


def test_kullanim_birikir(clock, limits):
    tracker = BudgetTracker(limits, clock)
    tracker.add_usage(10, 5, Decimal("0.001"))
    tracker.add_usage(20, 10, Decimal("0.002"))
    assert tracker.tokens_total == 45
    assert tracker.cost_usd == Decimal("0.003")
