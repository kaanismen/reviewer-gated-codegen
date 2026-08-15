"""Model seçimi ve sağlayıcı-farkında varsayılanlar.

Bu dosyanın varlık sebebi somut bir hata: `ROLE_DEFAULT_MODEL` tek bir
tablodaydı ve yalnızca OpenAI anahtarı giren bir kullanıcı
`openai` + `claude-opus-5` yapılandırması alıyordu — çağrı anında
patlayan, ama hiçbir testin yakalamadığı bir durum.
"""

from __future__ import annotations

import json

import pytest

from src.llm import factory
from src.llm.selection import SelectionStore
from src.security.key_vault import KeyVault
from src.transcript.models import Role

ANTHROPIC_KEY = "sk-ant-api03-TESTANAHTARI-abcdefghijklmnop-9f3a"
OPENAI_KEY = "sk-proj-TESTANAHTARI-qrstuvwxyz012345-7b21"


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


@pytest.fixture
def store(tmp_path) -> SelectionStore:
    return SelectionStore(tmp_path / "model-secimleri.json")


# ==========================================================================
# Düzeltilen hata
# ==========================================================================


def test_openai_anahtari_claude_modeli_secmez(vault, store):
    """Asıl hata buydu: sağlayıcı değişiyor, model Claude kalıyordu."""
    vault.set(Role.PLANLAYICI, "openai", OPENAI_KEY)
    config = factory.resolve_role(Role.PLANLAYICI, vault, store)
    assert config.saglayici == "openai"
    assert not config.model.startswith("claude"), (
        "OpenAI sağlayıcısına Claude model kimliği gönderilemez"
    )


def test_anthropic_anahtari_claude_modeli_secer(vault, store):
    vault.set(Role.PLANLAYICI, "anthropic", ANTHROPIC_KEY)
    config = factory.resolve_role(Role.PLANLAYICI, vault, store)
    assert config.model == "claude-opus-5"
    assert config.model_kaynagi == "varsayilan"


def test_openai_varsayilani_yedek_olarak_isaretlenir(vault, store):
    """Hesabın hangi modellere eriştiğini bilemeyiz; arayüz uyarmalı."""
    vault.set(Role.UYGULAYICI, "openai", OPENAI_KEY)
    config = factory.resolve_role(Role.UYGULAYICI, vault, store)
    assert config.model_kaynagi == "yedek"
    assert "katalogdan seçin" in config.gerekce


def test_roller_farkli_saglayici_ve_model_alabilir(vault, store):
    vault.set(Role.PLANLAYICI, "anthropic", ANTHROPIC_KEY)
    vault.set(Role.UYGULAYICI, "openai", OPENAI_KEY)
    planlayici = factory.resolve_role(Role.PLANLAYICI, vault, store)
    uygulayici = factory.resolve_role(Role.UYGULAYICI, vault, store)
    assert planlayici.model.startswith("claude")
    assert not uygulayici.model.startswith("claude")


# ==========================================================================
# Seçim önceliği
# ==========================================================================


def test_secim_varsayilani_ezer(vault, store):
    vault.set(Role.PLANLAYICI, "anthropic", ANTHROPIC_KEY)
    store.set(Role.PLANLAYICI, "anthropic", "claude-haiku-4-5")
    config = factory.resolve_role(Role.PLANLAYICI, vault, store)
    assert config.model == "claude-haiku-4-5"
    assert config.model_kaynagi == "secim"


def test_secim_ortam_degiskenini_de_ezer(vault, store, monkeypatch):
    monkeypatch.setenv("MODEL_PLANLAYICI", "claude-opus-4-6")
    vault.set(Role.PLANLAYICI, "anthropic", ANTHROPIC_KEY)
    store.set(Role.PLANLAYICI, "anthropic", "claude-haiku-4-5")
    assert factory.resolve_role(Role.PLANLAYICI, vault, store).model == "claude-haiku-4-5"


def test_secim_yokken_ortam_degiskeni_kullanilir(vault, store, monkeypatch):
    monkeypatch.setenv("MODEL_PLANLAYICI", "claude-opus-4-6")
    vault.set(Role.PLANLAYICI, "anthropic", ANTHROPIC_KEY)
    config = factory.resolve_role(Role.PLANLAYICI, vault, store)
    assert config.model == "claude-opus-4-6"
    assert config.model_kaynagi == "ortam"


def test_baska_saglayici_icin_yapilan_secim_kullanilmaz(vault, store):
    """Anthropic için seçilen model OpenAI'a gönderilemez — düzeltilen
    hatanın tam olarak kendisi."""
    store.set(Role.PLANLAYICI, "anthropic", "claude-haiku-4-5")
    vault.set(Role.PLANLAYICI, "openai", OPENAI_KEY)
    config = factory.resolve_role(Role.PLANLAYICI, vault, store)
    assert config.model != "claude-haiku-4-5"
    assert config.saglayici == "openai"


# ==========================================================================
# Kalıcılık — seçim sır değil, tercihtir
# ==========================================================================


def test_secim_diske_yazilir_ve_geri_okunur(tmp_path):
    path = tmp_path / "secim.json"
    SelectionStore(path).set(Role.DENETLEYICI, "openai", "gpt-4.1-mini")
    assert path.is_file()

    yeniden = SelectionStore(path)
    assert yeniden.get(Role.DENETLEYICI).model == "gpt-4.1-mini"


def test_secim_dosyasi_anahtar_icermez(tmp_path):
    """Kasa belleğe, seçim diske yazılır. İkisi karışmamalı."""
    path = tmp_path / "secim.json"
    SelectionStore(path).set(Role.PLANLAYICI, "anthropic", "claude-opus-5")
    icerik = path.read_text(encoding="utf-8")
    assert "sk-" not in icerik
    assert set(json.loads(icerik)["planlayici"]) == {"saglayici", "model"}


def test_bozuk_secim_dosyasi_sistemi_acilmaz_yapmaz(tmp_path):
    path = tmp_path / "secim.json"
    path.write_text("{bozuk", encoding="utf-8")
    assert SelectionStore(path).as_dict() == {}


def test_bilinmeyen_rol_dosyadan_yuklenmez(tmp_path):
    path = tmp_path / "secim.json"
    path.write_text(json.dumps({
        "sistem": {"saglayici": "anthropic", "model": "x"},
        "hacker": {"saglayici": "anthropic", "model": "y"},
        "planlayici": {"saglayici": "anthropic", "model": "claude-opus-5"},
    }), encoding="utf-8")
    assert list(SelectionStore(path).as_dict()) == ["planlayici"]


def test_sistem_rolu_secim_alamaz(store):
    with pytest.raises(ValueError, match="agent rolü değil"):
        store.set(Role.SISTEM, "anthropic", "claude-opus-5")


def test_bos_model_reddedilir(store):
    with pytest.raises(ValueError, match="boş olamaz"):
        store.set(Role.PLANLAYICI, "anthropic", "   ")


def test_secim_temizlenebilir(store):
    store.set(Role.PLANLAYICI, "anthropic", "claude-opus-5")
    store.set(Role.UYGULAYICI, "anthropic", "claude-sonnet-5")
    store.clear(Role.PLANLAYICI)
    assert list(store.as_dict()) == ["uygulayici"]
    store.clear()
    assert store.as_dict() == {}


# ==========================================================================
# Sağlayıcı varsayılan tablosu
# ==========================================================================


def test_her_saglayicinin_kendi_varsayilani_var():
    for saglayici, tablo in factory.PROVIDER_DEFAULT_MODEL.items():
        assert set(tablo) == {Role.PLANLAYICI, Role.UYGULAYICI, Role.DENETLEYICI}
        for model in tablo.values():
            assert model


def test_anthropic_varsayilanlari_projectmd_ile_uyumlu():
    tablo = factory.PROVIDER_DEFAULT_MODEL["anthropic"]
    assert tablo[Role.PLANLAYICI] == "claude-opus-5"
    assert tablo[Role.UYGULAYICI] == "claude-sonnet-5"
    assert tablo[Role.DENETLEYICI] == "claude-opus-5"
