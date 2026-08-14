"""Anahtar kasası — PROJECT.md §6, tehdit T7 ve T8.

Bu dosyanın tek konusu şu: son kullanıcının emanet ettiği anahtar sistemden
DIŞARI ÇIKAMAZ. Her test bir sızıntı yolunu kapatır.
"""

from __future__ import annotations

import json

import pytest

from src.security.key_vault import (
    MASK,
    MIN_KEY_LENGTH,
    KeyRejected,
    KeyVault,
)
from src.transcript.models import Role
from src.transcript.store import Transcript
from tests.conftest import make_message

ANAHTAR = "sk-ant-api03-TESTANAHTARI-abcdefghijklmnop-9f3a"
DIGER = "sk-proj-TESTANAHTARI-qrstuvwxyz012345-7b21"


@pytest.fixture
def vault(monkeypatch) -> KeyVault:
    # Ortam anahtarları testleri kirletmesin
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return KeyVault()


# --------------------------------------------------------------------------
# Temel sözleşme
# --------------------------------------------------------------------------


def test_rol_bazinda_anahtar_saklanir(vault):
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    vault.set(Role.UYGULAYICI, "openai", DIGER)
    assert vault.get(Role.PLANLAYICI, "anthropic") == ANAHTAR
    assert vault.get(Role.UYGULAYICI, "openai") == DIGER


def test_baska_rolun_anahtari_sizmaz(vault):
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    assert vault.get(Role.DENETLEYICI, "anthropic") is None


def test_saglayici_uyusmazsa_anahtar_verilmez(vault):
    """anthropic için girilen anahtar openai istemcisine geçemez."""
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    assert vault.get(Role.PLANLAYICI, "openai") is None


def test_temizleme_anahtari_siler(vault):
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    vault.clear(Role.PLANLAYICI)
    assert vault.get(Role.PLANLAYICI, "anthropic") is None
    assert vault.fingerprints() == []


def test_toplu_temizleme(vault):
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    vault.set(Role.UYGULAYICI, "openai", DIGER)
    vault.clear()
    assert vault.fingerprints() == []


# --------------------------------------------------------------------------
# Dışarı yalnızca maske çıkar
# --------------------------------------------------------------------------


def test_parmak_izi_anahtarin_kendisini_icermez(vault):
    fingerprint = vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    serialized = json.dumps(fingerprint.as_dict(), ensure_ascii=False)
    assert ANAHTAR not in serialized
    assert fingerprint.son_dort == "9f3a"
    assert fingerprint.maske == "••••9f3a"


def test_parmak_izi_en_fazla_dort_karakter_gosterir(vault):
    fingerprint = vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    assert len(fingerprint.son_dort) == 4
    assert ANAHTAR[:-4] not in fingerprint.maske


def test_repr_anahtari_dokmez(vault):
    """Bir istisna izinde (traceback) kasa yazdırılırsa anahtar görünmemeli."""
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    assert ANAHTAR not in repr(vault)
    assert ANAHTAR not in str(vault)
    assert ANAHTAR not in f"{vault}"


def test_parmak_izi_listesi_siralidir(vault):
    vault.set(Role.UYGULAYICI, "openai", DIGER)
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    assert [f.rol for f in vault.fingerprints()] == ["planlayici", "uygulayici"]


# --------------------------------------------------------------------------
# Doğrulama — hata mesajı anahtarı yankılamaz
# --------------------------------------------------------------------------


def test_kisa_anahtar_reddedilir_ama_mesaja_yazilmaz(vault):
    kisa = "sk-123"
    with pytest.raises(KeyRejected) as err:
        vault.set(Role.PLANLAYICI, "anthropic", kisa)
    assert kisa not in str(err.value)
    assert str(MIN_KEY_LENGTH) in str(err.value)


def test_bosluklu_anahtar_reddedilir(vault):
    with pytest.raises(KeyRejected):
        vault.set(Role.PLANLAYICI, "anthropic", "sk-ant " + "a" * 30)


def test_anahtarsiz_saglayicilar_anahtar_kabul_etmez(vault):
    for provider in ("ollama", "replay"):
        with pytest.raises(KeyRejected, match="anahtar"):
            vault.set(Role.PLANLAYICI, provider, ANAHTAR)


def test_bilinmeyen_saglayici_reddedilir(vault):
    with pytest.raises(KeyRejected):
        vault.set(Role.PLANLAYICI, "gemini", ANAHTAR)


# --------------------------------------------------------------------------
# Ortam değişkeni ile ilişki
# --------------------------------------------------------------------------


def test_ortam_anahtari_yedek_olarak_kullanilir(vault, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", ANAHTAR)
    assert vault.get(Role.DENETLEYICI, "anthropic") == ANAHTAR


def test_arayuz_anahtari_ortami_gecersiz_kilar(vault, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", DIGER)
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    assert vault.get(Role.PLANLAYICI, "anthropic") == ANAHTAR


# --------------------------------------------------------------------------
# Sızıntı önleme — birebir eşleşmeyle gizleme
# --------------------------------------------------------------------------


def test_metindeki_anahtar_gizlenir(vault):
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    metin = f"istek başarısız: Authorization: Bearer {ANAHTAR} (401)"
    temiz = vault.redact(metin)
    assert ANAHTAR not in temiz
    assert MASK in temiz
    assert "401" in temiz  # bağlam korunur


def test_ayni_anahtarin_tum_gecisleri_gizlenir(vault):
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    temiz = vault.redact(f"{ANAHTAR} ve tekrar {ANAHTAR}")
    assert ANAHTAR not in temiz
    assert temiz.count(MASK) == 2


def test_ortamdaki_anahtar_da_gizlenir(vault, monkeypatch):
    """Anahtarın .env'den gelmiş olması onu transkripte yazılabilir yapmaz."""
    monkeypatch.setenv("OPENAI_API_KEY", DIGER)
    assert vault.contains_secret(f"hata: {DIGER}") is True
    assert DIGER not in vault.redact(f"hata: {DIGER}")


def test_temiz_metin_degismez(vault):
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    metin = "kazanma kontrolü çapraz hatları atlıyor"
    assert vault.redact(metin) == metin


def test_kasa_bosken_hicbir_sey_gizlenmez(vault):
    metin = f"bu bir anahtar gibi görünüyor: {ANAHTAR}"
    assert vault.redact(metin) == metin


# --------------------------------------------------------------------------
# Transkripte sızıntı — asıl senaryo
# --------------------------------------------------------------------------


def test_saglayici_hatasi_transkripte_anahtarla_girmez(vault):
    """Gerçekçi sızıntı yolu: 401 yanıtı sistem mesajı olarak transkripte
    yazılırsa ve içinde istek başlığı varsa anahtar diske yazılırdı."""
    vault.set(Role.DENETLEYICI, "anthropic", ANAHTAR)

    ham_hata = f"401 Unauthorized — gönderilen anahtar: {ANAHTAR}"
    transcript = Transcript(gorev_id="g-002", gorev_metni="snake yaz")
    transcript.add(
        make_message(
            Role.SISTEM,
            icerik={"olay": "saglayici_hatasi", "ayrinti": vault.redact(ham_hata)},
        )
    )

    disa_aktarim = transcript.to_json() + transcript.to_markdown()
    assert ANAHTAR not in disa_aktarim
    assert MASK in disa_aktarim


def test_gorev_metnine_yapistirilan_anahtar_tespit_edilir(vault):
    """Kullanıcı anahtarını sohbet kutusuna yapıştırırsa yakalanmalı."""
    vault.set(Role.PLANLAYICI, "anthropic", ANAHTAR)
    gorev = f"snake yaz, anahtarım {ANAHTAR}"
    assert vault.contains_secret(gorev) is True
