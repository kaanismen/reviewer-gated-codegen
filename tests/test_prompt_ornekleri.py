"""Prompt örnekleri ile şemaların uyumu.

Prompt'lar insan tarafından yazılır (kural K4), şemalar kod tarafından
zorlanır. İkisi ayrı ayrı doğru olup **birbiriyle çelişebilir** — nitekim
v1'de çelişti: planlayıcı prompt'u `durum` alanı üretiyordu, şemada öyle bir
alan yok; denetleyici prompt'u `"düşük"` yazıyordu, şema `"dusuk"` bekliyor.
İkisi de çalıştırılsa doğrulamadan geçemezdi.

Bu dosya prompt'lardaki her JSON örneğini gerçek şemaya karşı doğrular.
Prompt ile kod arasındaki sapma artık sessizce oluşamaz.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.config import PROMPTS_DIR
from src.transcript.models import (
    FeasibilityVerdict,
    PlannerContent,
    ReviewerContent,
)

_JSON_BLOCK = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)

# Örneklerde kasten yer tutucu bırakılan alanlar; JSON olarak geçerli
# oldukları sürece sorun değil.
PLACEHOLDER = "<"


def json_blocks(name: str) -> list[dict]:
    path = Path(PROMPTS_DIR) / name
    if not path.is_file():
        pytest.skip(f"prompt dosyası yok: {name}")
    blocks = []
    for raw in _JSON_BLOCK.findall(path.read_text(encoding="utf-8")):
        try:
            blocks.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            pytest.fail(f"{name}: JSON örneği ayrıştırılamadı — {exc}\n{raw[:200]}")
    return blocks


# --------------------------------------------------------------------------
# Planlayıcı
# --------------------------------------------------------------------------


def test_planlayici_ornekleri_semaya_uyuyor():
    blocks = json_blocks("planner.v1.md")
    assert blocks, "planner.v1.md içinde JSON örneği bulunamadı"
    for block in blocks:
        PlannerContent.model_validate(block)


def test_planlayici_hem_plan_hem_ret_ornegi_iceriyor():
    """Prompt her iki dalı da göstermeli, yoksa model biri için körleşir."""
    verdicts = {
        PlannerContent.model_validate(b).effective_verdict
        for b in json_blocks("planner.v1.md")
    }
    assert FeasibilityVerdict.UYGUN in verdicts
    assert FeasibilityVerdict.UYGUN_DEGIL in verdicts


def test_planlayici_ornekleri_sabit_oyun_listesine_bagli_degil():
    """Kapsam ölçüte bağlandı; örnekler de bilinen-iyi dördün dışına çıkmalı."""
    oyunlar = {PlannerContent.model_validate(b).oyun for b in json_blocks("planner.v1.md")}
    assert oyunlar - {"tic-tac-toe", "snake", "pong", "breakout"}, (
        "örneklerin en az biri listede olmayan bir oyunu göstermeli"
    )


def test_ret_ornegi_plan_alani_tasimiyor():
    for block in json_blocks("planner.v1.md"):
        plan = PlannerContent.model_validate(block)
        if plan.effective_verdict is FeasibilityVerdict.UYGUN_DEGIL:
            assert plan.adimlar == []
            assert plan.kabul_kriterleri == []


# --------------------------------------------------------------------------
# Denetleyici
# --------------------------------------------------------------------------


def test_denetleyici_ornekleri_semaya_uyuyor():
    blocks = json_blocks("reviewer.v1.md")
    assert blocks, "reviewer.v1.md içinde JSON örneği bulunamadı"
    for block in blocks:
        ReviewerContent.model_validate(block)


def test_denetleyici_ornekleri_karar_tutarliligini_ihlal_etmiyor():
    """Prompt'taki bir örnek §7.4 kuralını çiğniyorsa model onu taklit eder."""
    for block in json_blocks("reviewer.v1.md"):
        review = ReviewerContent.model_validate(block)
        assert review.override_reason is None, (
            f"prompt örneği kendi test sonucuyla çelişiyor: {review.gerekce}"
        )


# --------------------------------------------------------------------------
# Uygulayıcı — kendi tel biçimi, transkript şeması değil
# --------------------------------------------------------------------------


def test_uygulayici_ornegi_beklenen_anahtarlari_tasiyor():
    """Uygulayıcının LLM çıktısı dosya İÇERİKLERİDİR; transkriptteki
    `ImplementerContent` kaydı orkestratör tarafından dosyalar yazıldıktan
    sonra üretilir. Bu yüzden burada şema değil anahtar kontrolü yapılır."""
    blocks = json_blocks("implementer.v1.md")
    wire = [b for b in blocks if "dosyalar" in b]
    assert wire, "implementer.v1.md çıktı formatı örneği içermeli"
    for block in wire:
        assert set(block["dosyalar"]) == {"logic.js", "logic.test.js", "game.html"}
        assert "degisiklik_notu" in block


# --------------------------------------------------------------------------
# Ortak
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dosya", ["planner.v1.md", "implementer.v1.md", "reviewer.v1.md"]
)
def test_prompt_dosyasi_var_ve_bos_degil(dosya):
    path = Path(PROMPTS_DIR) / dosya
    assert path.is_file(), f"{dosya} yok — Faz 4'ün ön koşulu (kural K4)"
    assert len(path.read_text(encoding="utf-8")) > 500
