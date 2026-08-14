"""Mesaj zarfı ve transkript — PROJECT.md §7.1, §7.5, KK-07."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.transcript.models import AgentMessage, Role, SystemContent
from src.transcript.store import Transcript, TranscriptStore
from tests.conftest import make_message, make_plan, make_review


# --------------------------------------------------------------------------
# §7.1 zarf kuralları
# --------------------------------------------------------------------------


def test_agent_mesaji_koken_bilgisi_olmadan_kaydedilemez():
    """Denetlenebilirlik: hangi prompt sürümünden çıktığı bilinmeyen bir
    agent mesajı transkripte giremez (§9)."""
    with pytest.raises(ValidationError, match="köken"):
        make_message(Role.DENETLEYICI, prompt_hash=None)


def test_sistem_mesaji_prompt_istemez():
    message = make_message(Role.SISTEM)
    assert message.prompt_surumu is None


def test_rol_ile_icerik_uyusmazligi_reddedilir():
    with pytest.raises(ValidationError, match="içerik"):
        AgentMessage(
            tur=1,
            rol=Role.PLANLAYICI,
            icerik=make_review(),
            prompt_surumu="planner.v1",
            prompt_hash="0123456789ab",
            model="claude-opus-5",
        )


@pytest.mark.parametrize("bad", ["kısa", "ZZZZZZZZZZZZ", "0123456789abcd"])
def test_prompt_hash_bicimi_zorlanir(bad):
    with pytest.raises(ValidationError):
        make_message(prompt_hash=bad)


def test_zaman_utcye_normalize_edilir():
    assert make_message().zaman.utcoffset().total_seconds() == 0


def test_negatif_token_reddedilir():
    with pytest.raises(ValidationError):
        make_message(token_girdi=-1)


# --------------------------------------------------------------------------
# §7.5 transkript
# --------------------------------------------------------------------------


def build_transcript() -> Transcript:
    transcript = Transcript(gorev_id="g-001", gorev_metni="tic tac toe yaz",
                            saglayici="replay")
    transcript.add(make_message(Role.PLANLAYICI))
    transcript.add(make_message(Role.UYGULAYICI, model="claude-sonnet-5"))
    transcript.add(make_message(Role.DENETLEYICI))
    return transcript


def test_toplamlar_mesajlardan_hesaplanir():
    transcript = build_transcript()
    assert transcript.toplam_token_girdi == 3000
    assert transcript.toplam_token_cikti == 1200
    assert transcript.toplam_maliyet_usd == Decimal("0.04500")


def test_prompt_hashleri_mesajlardan_toplanir():
    transcript = build_transcript()
    assert set(transcript.prompt_hashleri) == {
        "planlayici.v1", "uygulayici.v1", "denetleyici.v1"
    }


def test_model_eslemesi_rol_bazinda_kaydedilir():
    transcript = build_transcript()
    assert transcript.model_eslemesi["uygulayici"] == "claude-sonnet-5"
    assert transcript.model_eslemesi["planlayici"] == "claude-opus-5"


def test_sistem_mesaji_model_eslemesini_kirletmez():
    transcript = build_transcript()
    transcript.add(make_message(Role.SISTEM))
    assert "sistem" not in transcript.model_eslemesi


def test_json_disa_aktarimi_prompt_hashlerini_icerir():
    """KK-07: dışa aktarım prompt sürüm hash'lerini taşımalıdır."""
    transcript = build_transcript()
    transcript.close("KABUL_EDILDI", {"uygulanan_kural": "G6"})
    payload = json.loads(transcript.to_json())
    assert payload["prompt_hashleri"]["planlayici.v1"] == "0123456789ab"
    assert payload["toplamlar"]["token_girdi"] == 3000
    assert payload["son_durum"] == "KABUL_EDILDI"


def test_markdown_disa_aktarimi_uretilir():
    transcript = build_transcript()
    transcript.close("KABUL_EDILDI")
    markdown = transcript.to_markdown()
    assert "# Transkript — g-001" in markdown
    assert "planlayici.v1" in markdown
    assert "KABUL_EDILDI" in markdown


def test_diske_yazilip_geri_okunur(tmp_path):
    transcript = build_transcript()
    transcript.close("KABUL_EDILDI", {"uygulanan_kural": "G6"})
    store = TranscriptStore(tmp_path)
    path = store.save(transcript)

    assert path.exists()
    assert (path.parent / "transkript.md").exists()

    loaded = store.load("g-001")
    assert loaded.gorev_metni == transcript.gorev_metni
    assert loaded.son_durum == "KABUL_EDILDI"
    assert len(loaded.mesajlar) == 3
    assert loaded.toplam_maliyet_usd == transcript.toplam_maliyet_usd


def test_planlayici_icerigi_sema_disi_veriyi_reddeder():
    with pytest.raises(ValidationError):
        make_plan(adimlar=["tek adım"])  # §7.2: 2–6 adım

    with pytest.raises(ValidationError):
        make_plan(kabul_kriterleri=[])  # §7.2: en az 1 kriter

    with pytest.raises(ValidationError):
        make_plan(oyun="satranç")  # kapsam dışı oyun


def test_bos_dizeli_liste_ogesi_reddedilir():
    with pytest.raises(ValidationError):
        make_plan(kabul_kriterleri=["   "])
