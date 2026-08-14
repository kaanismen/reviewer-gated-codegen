"""Durum makinesi testleri — PROJECT.md §4.2'deki 13 geçiş + tablo boşlukları.

Her koruma koşulunun hem GEÇEN hem DÜŞEN hali sınanır: bir koruma koşulu
yalnızca doğru durumda geçtiğinde değil, yanlış durumda düştüğünde de
doğrudur.
"""

from __future__ import annotations

import pytest

from src.orchestrator.limits import Limits
from src.orchestrator.state_machine import (
    Event,
    IllegalTransition,
    Payload,
    RunContext,
    State,
    StateMachine,
    event_for_review,
)
from src.transcript.models import Decision, Finding, Severity
from tests.conftest import make_accepted_review, make_plan, make_review

GOREV = "tic tac toe oyunu yaz"


def new_machine(limits: Limits | None = None, task: str = GOREV) -> StateMachine:
    return StateMachine(RunContext(limits=limits or Limits(), task_text=task))


def at_planning(**kw) -> StateMachine:
    machine = new_machine(**kw)
    machine.fire(Event.TASK_RECEIVED)
    return machine


def at_implementing(**kw) -> StateMachine:
    machine = at_planning(**kw)
    machine.fire(Event.PLAN_PRODUCED, Payload(plan=make_plan()))
    return machine


def at_reviewing(**kw) -> StateMachine:
    machine = at_implementing(**kw)
    machine.fire(Event.FILES_WRITTEN, Payload(written_file_count=3))
    return machine


def at_rejected(reason: str = "kazanma kontrolü eksik", **kw) -> StateMachine:
    machine = at_reviewing(**kw)
    machine.fire(Event.REVIEW_REJECTED, Payload(review=make_review(gerekce=reason)))
    return machine


# --------------------------------------------------------------------------
# G1 — görev alındı
# --------------------------------------------------------------------------


def test_g1_gecerli_gorev_planlamayi_baslatir():
    machine = new_machine()
    result = machine.fire(Event.TASK_RECEIVED)
    assert result.rule == "G1"
    assert machine.state is State.PLANNING
    assert machine.context.turn == 1


def test_g1_bos_gorev_reddedilir():
    machine = new_machine(task="   ")
    with pytest.raises(IllegalTransition):
        machine.fire(Event.TASK_RECEIVED)
    assert machine.state is None


def test_g1_karakter_sinirini_asan_gorev_reddedilir():
    limits = Limits(max_task_chars=10)
    machine = new_machine(limits=limits, task="a" * 11)
    with pytest.raises(IllegalTransition):
        machine.fire(Event.TASK_RECEIVED)


def test_g1_sinirdaki_gorev_kabul_edilir():
    limits = Limits(max_task_chars=10)
    machine = new_machine(limits=limits, task="a" * 10)
    assert machine.fire(Event.TASK_RECEIVED).target is State.PLANNING


# --------------------------------------------------------------------------
# G2, G3 — planlama
# --------------------------------------------------------------------------


def test_g2_plan_uretildi():
    machine = at_planning()
    result = machine.fire(Event.PLAN_PRODUCED, Payload(plan=make_plan()))
    assert result.rule == "G2"
    assert machine.state is State.IMPLEMENTING


def test_g2_plan_yoksa_gecis_yok():
    machine = at_planning()
    with pytest.raises(IllegalTransition):
        machine.fire(Event.PLAN_PRODUCED, Payload(plan=None))
    assert machine.state is State.PLANNING


def test_g3r_ilk_sema_hatasi_yeniden_dener():
    machine = at_planning()
    result = machine.fire(Event.PLAN_SCHEMA_ERROR)
    assert result.rule == "G3r"
    assert machine.state is State.PLANNING
    assert machine.context.plan_schema_errors == 1


def test_g3_ikinci_sema_hatasi_hataya_dusurur():
    machine = at_planning()
    machine.fire(Event.PLAN_SCHEMA_ERROR)
    result = machine.fire(Event.PLAN_SCHEMA_ERROR, Payload(detail="şema geçersiz"))
    assert result.rule == "G3"
    assert machine.state is State.ERROR


# --------------------------------------------------------------------------
# G4, G5 — uygulama
# --------------------------------------------------------------------------


def test_g4_dosyalar_yazildi():
    machine = at_implementing()
    result = machine.fire(Event.FILES_WRITTEN, Payload(written_file_count=3))
    assert result.rule == "G4"
    assert machine.state is State.REVIEWING


def test_g4_hic_dosya_yazilmadiysa_gecis_yok():
    machine = at_implementing()
    with pytest.raises(IllegalTransition):
        machine.fire(Event.FILES_WRITTEN, Payload(written_file_count=0))


def test_g4_yol_workspace_disindaysa_gecis_yok():
    machine = at_implementing()
    with pytest.raises(IllegalTransition):
        machine.fire(
            Event.FILES_WRITTEN,
            Payload(written_file_count=2, all_paths_inside_workspace=False),
        )


def test_g5_yol_ihlali_kurtarilamaz():
    machine = at_implementing()
    result = machine.fire(Event.PATH_VIOLATION, Payload(detail="../../etc/passwd"))
    assert result.rule == "G5"
    assert machine.state is State.ERROR
    assert "etc/passwd" in machine.context.last_error


# --------------------------------------------------------------------------
# G6 — kabul ve KK-06
# --------------------------------------------------------------------------


def test_g6_testler_gecti_ve_sir_temiz():
    machine = at_reviewing()
    result = machine.fire(
        Event.REVIEW_ACCEPTED,
        Payload(review=make_accepted_review(), secret_scan_clean=True),
    )
    assert result.rule == "G6"
    assert machine.state is State.ACCEPTED


def test_g6s_sir_bulunursa_kabul_gecersizdir():
    """KK-06: sır taraması bulgu verdiyse KABUL kabul değildir, RED turudur."""
    machine = at_reviewing()
    result = machine.fire(
        Event.REVIEW_ACCEPTED,
        Payload(review=make_accepted_review(), secret_scan_clean=False),
    )
    assert result.rule == "G6s"
    assert machine.state is State.REJECTED
    assert machine.context.rejection_reasons == ["sır taraması bulgu verdi"]


# --------------------------------------------------------------------------
# G7, G8 — red ve tur tavanı
# --------------------------------------------------------------------------


def test_g7_tur_hakki_varken_red():
    machine = at_reviewing()
    result = machine.fire(Event.REVIEW_REJECTED, Payload(review=make_review()))
    assert result.rule == "G7"
    assert machine.state is State.REJECTED
    assert len(machine.context.rejection_reasons) == 1


def test_g8_tur_tavani_dolunca_limit_asildi():
    """KK-02: 5. turda hâlâ red geliyorsa sistem durur ve rapor üretir."""
    limits = Limits(max_turns=2)
    machine = at_reviewing(limits=limits)
    machine.context.turn = 2  # son tur
    result = machine.fire(Event.REVIEW_REJECTED, Payload(review=make_review()))
    assert result.rule == "G8"
    assert machine.state is State.LIMIT_EXCEEDED

    report = machine.final_report()
    assert report["son_durum"] == "LIMIT_ASILDI"
    assert report["son_red_gerekcesi"]


# --------------------------------------------------------------------------
# G9 — ayrıştırılamayan karar (T4 / KK-05)
# --------------------------------------------------------------------------


def test_g9r_ilk_ayristirma_hatasi_yeniden_dener():
    machine = at_reviewing()
    result = machine.fire(Event.REVIEW_UNPARSABLE)
    assert result.rule == "G9r"
    assert machine.state is State.REVIEWING


def test_g9_ikinci_ayristirma_hatasi_kabul_sayilmaz():
    machine = at_reviewing()
    machine.fire(Event.REVIEW_UNPARSABLE)
    result = machine.fire(Event.REVIEW_UNPARSABLE)
    assert result.rule == "G9"
    assert machine.state is State.ERROR
    assert machine.state is not State.ACCEPTED


# --------------------------------------------------------------------------
# G10, G11 — revizyon ve ilerleme yok (KK-03)
# --------------------------------------------------------------------------


def test_g10_yeni_gerekce_revizyon_turu_baslatir():
    machine = at_rejected(reason="kazanma kontrolü eksik")
    result = machine.fire(Event.REVISION_REQUESTED)
    assert result.rule == "G10"
    assert machine.state is State.IMPLEMENTING
    assert machine.context.turn == 2


def test_g11_ayni_gerekce_iki_kez_ust_uste_durdurur():
    """KK-03: üçüncü tur başlatılmadan durulur."""
    machine = at_rejected(reason="kazanma kontrolü eksik")
    machine.fire(Event.REVISION_REQUESTED)
    machine.fire(Event.FILES_WRITTEN, Payload(written_file_count=3))
    machine.fire(
        Event.REVIEW_REJECTED,
        Payload(review=make_review(gerekce="kazanma kontrolü eksik")),
    )
    result = machine.fire(Event.REVISION_REQUESTED)
    assert result.rule == "G11"
    assert machine.state is State.LIMIT_EXCEEDED
    assert machine.context.turn == 2  # üçüncü tur hiç başlamadı


def test_ilerleme_tespiti_bicimsel_farki_yok_sayar():
    ctx = RunContext(limits=Limits(no_progress_threshold=2))
    ctx.rejection_reasons = ["Kazanma  kontrolü EKSİK", "kazanma kontrolü eksik"]
    assert ctx.no_progress is True


@pytest.mark.parametrize(
    "yazim", ["EKSİK", "eksik", "Eksik", "eksİk", "  eksik  "]
)
def test_turkce_buyuk_kucuk_harf_ayni_gerekce_sayilir(yazim):
    """Python'un lower() metodu 'İ'yi birleşik noktayla açar; düzeltilmezse
    aynı gerekçenin farklı yazımı "yeni gerekçe" sayılır ve ilerleme-yok
    koruması sessizce çalışmaz olurdu."""
    ctx = RunContext(limits=Limits(no_progress_threshold=2))
    ctx.rejection_reasons = ["eksik", yazim]
    assert ctx.no_progress is True


def test_turkce_noktasiz_i_de_dogru_kucuktur():
    ctx = RunContext(limits=Limits(no_progress_threshold=2))
    ctx.rejection_reasons = ["IŞIK yok", "ışık yok"]
    assert ctx.no_progress is True


def test_farkli_gerekceler_ilerleme_sayilir():
    ctx = RunContext(limits=Limits(no_progress_threshold=2))
    ctx.rejection_reasons = ["kazanma kontrolü eksik", "beraberlik durumu eksik"]
    assert ctx.no_progress is False


def test_esikten_az_red_ilerleme_yok_sayilmaz():
    ctx = RunContext(limits=Limits(no_progress_threshold=2))
    ctx.rejection_reasons = ["aynı"]
    assert ctx.no_progress is False


# --------------------------------------------------------------------------
# G12, G13 — her durumdan çıkış
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "builder", [at_planning, at_implementing, at_reviewing, at_rejected]
)
def test_g12_limit_her_durumdan_calisir(builder):
    machine = builder()
    result = machine.fire(Event.LIMIT_HIT, Payload(limit_name="MAX_TOKEN_TOPLAM"))
    assert result.rule == "G12"
    assert machine.state is State.LIMIT_EXCEEDED
    assert machine.final_report()["dolan_limit"] == "MAX_TOKEN_TOPLAM"


@pytest.mark.parametrize(
    "builder", [at_planning, at_implementing, at_reviewing, at_rejected]
)
def test_g13_beklenmeyen_hata_her_durumdan_calisir(builder):
    machine = builder()
    result = machine.fire(Event.UNEXPECTED_ERROR, Payload(detail="bağlantı koptu"))
    assert result.rule == "G13"
    assert machine.state is State.ERROR
    assert machine.final_report()["hata"] == "bağlantı koptu"


# --------------------------------------------------------------------------
# Son durum davranışı ve rapor
# --------------------------------------------------------------------------


def test_son_durumdan_sonra_olay_islenemez():
    machine = at_reviewing()
    machine.fire(Event.REVIEW_ACCEPTED, Payload(review=make_accepted_review()))
    with pytest.raises(IllegalTransition, match="son durum"):
        machine.fire(Event.REVIEW_REJECTED, Payload(review=make_review()))


def test_son_duruma_ulasmadan_rapor_uretilemez():
    machine = at_reviewing()
    with pytest.raises(RuntimeError):
        machine.final_report()


def test_rapor_hangi_kuralla_durulduğunu_yazar():
    machine = at_implementing()
    machine.fire(Event.PATH_VIOLATION, Payload(detail="workspace dışı"))
    report = machine.final_report()
    assert report["uygulanan_kural"] == "G5"
    assert report["gerekce"]
    assert report["tur"] == 1


def test_gecmis_tum_gecisleri_tutar():
    machine = at_rejected()
    assert [t.rule for t in machine.history] == ["G1", "G2", "G4", "G7"]


# --------------------------------------------------------------------------
# T4 — olay seçimi karar alanına değil, iş kuralına bağlıdır
# --------------------------------------------------------------------------


def test_kabul_diyen_ama_testi_kalan_denetim_red_olayina_donusur():
    review = make_review(karar=Decision.KABUL, gerekce="her şey yolunda görünüyor", kalan=2)
    assert event_for_review(review) is Event.REVIEW_REJECTED


def test_gercek_kabul_kabul_olayina_donusur():
    assert event_for_review(make_accepted_review()) is Event.REVIEW_ACCEPTED


def test_gecersiz_kilinan_kabul_gerekce_olarak_kaydedilir():
    machine = at_reviewing()
    review = make_review(karar=Decision.KABUL, gerekce="her şey yolunda görünüyor", kalan=3)
    machine.fire(event_for_review(review), Payload(review=review))
    assert machine.state is State.REJECTED
    assert "3 test" in machine.context.rejection_reasons[0]


def test_kritik_bulgulu_kabul_su_an_kabul_sayilir():
    """Bilinçli olarak sınanan BOŞLUK.

    §7.4 yalnızca test sonucu kuralını tanımlar; kritik bulgu ile KABUL
    çelişkisi spesifikasyonda yoktur. Kural icat etmek yerine mevcut
    davranış burada kayda geçirilmiştir — karar insana bırakılmıştır.
    """
    review = make_accepted_review(
        bulgular=[Finding(dosya="logic.js", sorun="ağ modülü içe aktarılmış",
                          onem=Severity.KRITIK)]
    )
    assert event_for_review(review) is Event.REVIEW_ACCEPTED
