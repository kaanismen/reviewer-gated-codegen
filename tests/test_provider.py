"""Sağlayıcı katmanı — PROJECT.md §8.

Üç şey sınanır: sözleşmenin sağlayıcıdan bağımsız olduğu, maliyet
hesabının tavanı besleyecek kadar güvenilir olduğu, ve kayıt/oynatmanın
gerçekten deterministik olduğu.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from src.llm import factory, pricing
from src.llm.provider import (
    CassetteMissing,
    LlmProvider,
    LlmRequest,
    LlmResponse,
    Message,
    ProviderError,
    Usage,
)
from src.llm.replay_provider import ReplayProvider
from src.security.key_vault import KeyVault
from src.transcript.models import Role

ANAHTAR = "sk-ant-api03-TESTANAHTARI-abcdefghijklmnop-9f3a"


def make_request(**overrides) -> LlmRequest:
    data = {
        "system": "Sen bir planlayıcısın.",
        "messages": (Message(rol="user", icerik="snake oyunu yaz"),),
        "model": "claude-opus-5",
        "max_tokens": 16000,
    }
    return LlmRequest(**{**data, **overrides})


class FakeProvider(LlmProvider):
    """Testler için sahte sağlayıcı; çağrı sayısını sayar."""

    name = "sahte"

    def __init__(self, metin: str = '{"karar": "KABUL"}', hata: Exception | None = None):
        super().__init__()
        self.metin = metin
        self.hata = hata
        self.cagri = 0

    def complete(self, request: LlmRequest) -> LlmResponse:
        self.cagri += 1
        if self.hata:
            raise self.hata
        return LlmResponse(
            metin=self.metin,
            kullanim=Usage.priced(request.model, 1000, 400),
            model=request.model,
            saglayici=self.name,
        )


@pytest.fixture
def vault(monkeypatch) -> KeyVault:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    for name in ("LLM_PROVIDER", "LLM_KAYIT"):
        monkeypatch.delenv(name, raising=False)
    for rol in Role:
        monkeypatch.delenv(f"LLM_PROVIDER_{rol.value.upper()}", raising=False)
        monkeypatch.delenv(f"MODEL_{rol.value.upper()}", raising=False)
    return KeyVault()


# ==========================================================================
# İstek parmak izi — kaset anahtarının temeli
# ==========================================================================


def test_ayni_istek_ayni_parmak_izi():
    assert make_request().fingerprint() == make_request().fingerprint()


@pytest.mark.parametrize(
    "degisiklik",
    [
        {"model": "claude-sonnet-5"},
        {"max_tokens": 8000},
        {"system": "Sen bir denetleyicisin."},
        {"messages": (Message(rol="user", icerik="pong oyunu yaz"),)},
    ],
)
def test_istegin_her_parcasi_parmak_izini_degistirir(degisiklik):
    assert make_request(**degisiklik).fingerprint() != make_request().fingerprint()


def test_parmak_izi_sistem_promptunu_acikta_birakmaz():
    """Kasete sistem promptunun tam metni değil hash'i yazılır."""
    canonical = make_request().canonical()
    assert "Sen bir planlayıcısın." not in json.dumps(canonical, ensure_ascii=False)
    assert len(canonical["system_sha256"]) == 16


# ==========================================================================
# Maliyet — harcama tavanını besliyor
# ==========================================================================


def test_bilinen_model_fiyati_dogru():
    # 1M girdi + 1M çıktı, Opus 5: $5 + $25
    assert pricing.estimate_cost("claude-opus-5", 1_000_000, 1_000_000) == Decimal("30")


def test_bilinmeyen_model_en_pahaliya_gore_hesaplanir():
    """Bilinmezliği ücretsiz saymak tavanı sessizce devre dışı bırakırdı."""
    (girdi, cikti), bilinen = pricing.price_for("gelecekteki-model-9")
    assert bilinen is False
    assert (girdi, cikti) == max(pricing.PRICES.values(), key=lambda p: p[1])
    assert pricing.estimate_cost("gelecekteki-model-9", 1_000_000, 0) > 0


def test_yerel_model_ucretsiz():
    assert pricing.estimate_cost("ollama/llama3.1", 1_000_000, 1_000_000) == Decimal("0.00000")


def test_onbellek_okuma_ucuz_yazma_pahali():
    okuma = pricing.estimate_cost("claude-opus-5", 0, 0, onbellek_okuma=1_000_000)
    yazma = pricing.estimate_cost("claude-opus-5", 0, 0, onbellek_yazma=1_000_000)
    tam = pricing.estimate_cost("claude-opus-5", 1_000_000, 0)
    assert okuma < tam < yazma


def test_maliyet_sema_hassasiyetine_yuvarlanir():
    """§7.1 `maliyet_usd` alanı decimal(8,5)."""
    maliyet = pricing.estimate_cost("claude-opus-5", 137, 42)
    assert maliyet.as_tuple().exponent == -5


def test_kullanim_toplam_token():
    kullanim = Usage.priced("claude-opus-5", 1000, 400)
    assert kullanim.toplam_token == 1400
    assert kullanim.maliyet_usd > 0


# ==========================================================================
# Kayıt / oynatma
# ==========================================================================


def test_kaset_yoksa_sessizce_uydurmaz(tmp_path):
    """Sahte bir yanıt üretmek, testin neyi kaçırdığını gizlerdi."""
    provider = ReplayProvider(tmp_path)
    with pytest.raises(CassetteMissing, match="kaset yok"):
        provider.complete(make_request())


def test_kayit_modu_gercek_cagriyi_kasede_yazar(tmp_path):
    inner = FakeProvider(metin='{"oyun": "snake"}')
    provider = ReplayProvider(tmp_path, inner=inner)

    ilk = provider.complete(make_request())
    assert inner.cagri == 1
    assert provider.count() == 1

    ikinci = provider.complete(make_request())
    assert inner.cagri == 1, "ikinci çağrı kasetten gelmeli"
    assert ikinci.metin == ilk.metin


def test_oynatma_kaydedilen_kullanimi_korur(tmp_path):
    inner = FakeProvider()
    ReplayProvider(tmp_path, inner=inner).complete(make_request())

    oynatilan = ReplayProvider(tmp_path).complete(make_request())
    assert oynatilan.kullanim.token_girdi == 1000
    assert oynatilan.kullanim.token_cikti == 400
    assert oynatilan.kullanim.maliyet_usd > 0


def test_farkli_istek_farkli_kaset(tmp_path):
    inner = FakeProvider()
    provider = ReplayProvider(tmp_path, inner=inner)
    provider.complete(make_request())
    provider.complete(make_request(model="claude-sonnet-5"))
    assert provider.count() == 2


def test_sir_iceren_yanit_kasete_yazilmaz(tmp_path):
    """Bir testi kolaylaştırmak için sır commit etmek kabul edilebilir
    bir takas değildir."""
    inner = FakeProvider(metin=f"anahtarın {ANAHTAR} ile devam et")
    provider = ReplayProvider(tmp_path, inner=inner)

    provider.complete(make_request())
    kaset = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert ANAHTAR not in json.dumps(kaset, ensure_ascii=False)
    assert "GİZLENDİ" in kaset["yanit"]["metin"]


def test_bozuk_kaset_anlasilir_hata_verir(tmp_path):
    request = make_request()
    provider = ReplayProvider(tmp_path)
    provider.path_for(request).parent.mkdir(parents=True, exist_ok=True)
    provider.path_for(request).write_text("{bozuk", encoding="utf-8")
    with pytest.raises(ProviderError, match="kaset okunamadı"):
        provider.complete(request)


def test_bos_kaset_dizini_sifir_sayar(tmp_path):
    assert ReplayProvider(tmp_path / "yok").count() == 0


# ==========================================================================
# Rol → sağlayıcı çözümlemesi
# ==========================================================================


def test_anahtar_yoksa_replaye_duser(vault):
    config = factory.resolve_role(Role.PLANLAYICI, vault)
    assert config.saglayici == "replay"
    assert "anahtar" in config.gerekce


def test_anahtar_varsa_anthropic_secilir(vault):
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    config = factory.resolve_role(Role.PLANLAYICI, vault)
    assert config.saglayici == "anthropic"
    assert config.model == "claude-opus-5"


def test_roller_farkli_saglayici_kullanabilir(vault):
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    vault.set(Role.UYGULAYICI, "openai", "sk-proj-DIGERANAHTAR-abcdefghijklmno")
    assert factory.resolve_role(Role.PLANLAYICI, vault).saglayici == "anthropic"
    assert factory.resolve_role(Role.UYGULAYICI, vault).saglayici == "openai"
    assert factory.resolve_role(Role.DENETLEYICI, vault).saglayici == "replay"


def test_rol_bazli_ortam_degiskeni_geneli_ezer(vault, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_PROVIDER_DENETLEYICI", "replay")
    assert factory.resolve_role(Role.PLANLAYICI, vault).saglayici == "ollama"
    assert factory.resolve_role(Role.DENETLEYICI, vault).saglayici == "replay"


def test_istenen_saglayicinin_anahtari_yoksa_replaye_duser(vault, monkeypatch):
    """Yanlış yapılandırma sistemi açılmaz yapmaz, ama sessizce de geçmez."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    config = factory.resolve_role(Role.PLANLAYICI, vault)
    assert config.saglayici == "replay"
    assert "anahtar yok" in config.gerekce


def test_taninmayan_saglayici_replaye_duser(vault, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    config = factory.resolve_role(Role.PLANLAYICI, vault)
    assert config.saglayici == "replay"
    assert "tanınmayan" in config.gerekce


def test_model_ortam_degiskeniyle_degistirilebilir(vault, monkeypatch):
    vault.set(Role.UYGULAYICI, "anthropic", ANAHTAR)
    monkeypatch.setenv("MODEL_UYGULAYICI", "claude-haiku-4-5")
    assert factory.resolve_role(Role.UYGULAYICI, vault).model == "claude-haiku-4-5"


def test_uygulayici_daha_yuksek_token_tavanina_sahip(vault):
    """Üç dosyanın tam içeriğini üretiyor; diğer roller JSON dönüyor."""
    uygulayici = factory.resolve_role(Role.UYGULAYICI, vault).max_tokens
    planlayici = factory.resolve_role(Role.PLANLAYICI, vault).max_tokens
    assert uygulayici > planlayici


def test_varsayilan_rol_model_eslemesi_projectmd_ile_uyumlu():
    assert factory.ROLE_DEFAULT_MODEL[Role.PLANLAYICI] == "claude-opus-5"
    assert factory.ROLE_DEFAULT_MODEL[Role.UYGULAYICI] == "claude-sonnet-5"
    assert factory.ROLE_DEFAULT_MODEL[Role.DENETLEYICI] == "claude-opus-5"


def test_anahtarsiz_kurulumda_replay_saglayici_kurulur(vault):
    provider = factory.build_provider(Role.PLANLAYICI, vault)
    assert isinstance(provider, ReplayProvider)
    assert provider.recording is False


def test_kayit_modu_saglayiciyi_sarmalar(vault, monkeypatch):
    monkeypatch.setenv("LLM_KAYIT", "1")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    provider = factory.build_provider(Role.PLANLAYICI, vault)
    assert isinstance(provider, ReplayProvider)
    assert provider.recording is True


# ==========================================================================
# Hata metinlerinin gizlenmesi
# ==========================================================================


def test_saglayici_hata_metni_anahtari_sizdirmaz(vault):
    """Sağlayıcı istisnası istek başlığını taşıyabilir; mesaj transkripte gider."""
    vault.set(Role.DENETLEYICI, "anthropic", ANAHTAR)

    class SizdiranProvider(LlmProvider):
        name = "sizdiran"

        def complete(self, request):
            return LlmResponse(
                metin=self.safe(f"401: Authorization: Bearer {ANAHTAR}"),
                kullanim=Usage(),
                model=request.model,
                saglayici=self.name,
            )

    provider = SizdiranProvider(redactor=vault.redact)
    metin = provider.complete(make_request()).metin
    assert ANAHTAR not in metin
    assert "GİZLENDİ" in metin


def test_safe_uzun_metni_kisaltir():
    class P(LlmProvider):
        name = "p"

        def complete(self, request):  # pragma: no cover
            raise NotImplementedError

    assert len(P().safe("x" * 5000)) <= 401
