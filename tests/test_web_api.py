"""HTTP uçları — anahtar girişi ve kütüphane sunumu.

Anahtar uçları güvenlik yüzeyidir: bu dosyanın tek işi anahtarın HTTP
yanıtlarından geri çıkmadığını göstermektir.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.llm.selection import SelectionStore
from src.web import app as app_module
from src.web.app import app, vault

ANAHTAR = "sk-ant-api03-TESTANAHTARI-abcdefghijklmnop-9f3a"


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Uçları host durumundan YALITIR.

    `src.web.app` modül düzeyinde gerçek seçim dosyasını (`data/`) yükler.
    Yalıtılmazsa testler geliştiricinin kendi model seçimlerine bağımlı
    hale gelir — nitekim geldi ve bir test o yüzden düştü. Kasa da her
    testte boşaltılır.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    for name in ("LLM_PROVIDER", "MODEL_PLANLAYICI", "MODEL_UYGULAYICI",
                 "MODEL_DENETLEYICI"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        app_module, "selections", SelectionStore(tmp_path / "model-secimleri.json")
    )
    vault.clear()
    with TestClient(app) as test_client:
        yield test_client
    vault.clear()


# ==========================================================================
# Sağlık ucu
# ==========================================================================


def test_saglik_ucu_rol_yapilandirmasini_gosterir(client):
    data = client.get("/api/health").json()
    assert data["durum"] == "ayakta"
    assert {r["rol"] for r in data["roller"]} == {
        "planlayici", "uygulayici", "denetleyici"
    }
    for rol in data["roller"]:
        assert rol["gerekce"], "her rolün seçim gerekçesi görünmeli"


def test_anahtarsiz_kurulum_cevrimdisi_isaretlenir(client):
    data = client.get("/api/health").json()
    assert data["cevrimdisi_mod"] is True
    assert all(r["saglayici"] == "replay" for r in data["roller"])


# ==========================================================================
# Anahtar uçları — T8
# ==========================================================================


def test_anahtar_kaydedilir_ve_maskeli_doner(client):
    response = client.post(
        "/api/anahtarlar",
        json={"rol": "planlayici", "saglayici": "anthropic", "anahtar": ANAHTAR},
    )
    assert response.status_code == 200
    body = response.json()
    assert ANAHTAR not in response.text
    assert body["maske"] == "••••9f3a"
    assert body["rol"] == "planlayici"


def test_anahtar_yaniti_onbellege_alinmaz(client):
    response = client.post(
        "/api/anahtarlar",
        json={"rol": "planlayici", "saglayici": "anthropic", "anahtar": ANAHTAR},
    )
    assert response.headers.get("cache-control") == "no-store"


def test_anahtar_listesi_sadece_maske_dondurur(client):
    client.post(
        "/api/anahtarlar",
        json={"rol": "denetleyici", "saglayici": "anthropic", "anahtar": ANAHTAR},
    )
    response = client.get("/api/anahtarlar")
    assert ANAHTAR not in response.text
    assert response.json()["anahtarlar"][0]["maske"].endswith("9f3a")


def test_anahtar_girisi_rol_saglayici_secimini_degistirir(client):
    client.post(
        "/api/anahtarlar",
        json={"rol": "uygulayici", "saglayici": "anthropic", "anahtar": ANAHTAR},
    )
    roller = {r["rol"]: r for r in client.get("/api/health").json()["roller"]}
    assert roller["uygulayici"]["saglayici"] == "anthropic"
    assert roller["planlayici"]["saglayici"] == "replay"


def test_kisa_anahtar_reddedilir_ve_yankilanmaz(client):
    kisa = "sk-kisa"
    response = client.post(
        "/api/anahtarlar",
        json={"rol": "planlayici", "saglayici": "anthropic", "anahtar": kisa},
    )
    assert response.status_code == 400
    assert kisa not in response.text


def test_anahtarsiz_saglayici_reddedilir(client):
    response = client.post(
        "/api/anahtarlar",
        json={"rol": "planlayici", "saglayici": "ollama", "anahtar": ANAHTAR},
    )
    assert response.status_code == 400


def test_sistem_rolu_anahtar_alamaz(client):
    """`sistem` rolü LLM'e gitmez; ona anahtar emanet etmek hiçbir zaman
    kullanılmayacak bir sırrı bellekte tutmak olurdu."""
    response = client.post(
        "/api/anahtarlar",
        json={"rol": "sistem", "saglayici": "anthropic", "anahtar": ANAHTAR},
    )
    assert response.status_code == 400
    assert "agent rolü değil" in response.json()["detail"]


def test_taninmayan_rol_reddedilir(client):
    response = client.post(
        "/api/anahtarlar",
        json={"rol": "hacker", "saglayici": "anthropic", "anahtar": ANAHTAR},
    )
    assert response.status_code == 422


def test_fazladan_alan_reddedilir(client):
    response = client.post(
        "/api/anahtarlar",
        json={
            "rol": "planlayici",
            "saglayici": "anthropic",
            "anahtar": ANAHTAR,
            "kalici": True,
        },
    )
    assert response.status_code == 422


def test_model_secimi_kaydedilir_ve_rolu_degistirir(client):
    """Seçim hem sağlayıcıyı hem modeli belirler (v2.3)."""
    client.post(
        "/api/anahtarlar",
        json={"rol": "planlayici", "saglayici": "anthropic", "anahtar": ANAHTAR},
    )
    r = client.post(
        "/api/modeller/secim",
        json={"rol": "planlayici", "saglayici": "anthropic", "model": "claude-haiku-4-5"},
    )
    assert r.status_code == 200

    rol = next(x for x in client.get("/api/health").json()["roller"]
               if x["rol"] == "planlayici")
    assert rol["model"] == "claude-haiku-4-5"
    assert rol["model_kaynagi"] == "secim"
    assert rol["saglayici_kaynagi"] == "secim"


def test_secim_kaldirilinca_otomatige_doner(client):
    client.post(
        "/api/anahtarlar",
        json={"rol": "planlayici", "saglayici": "anthropic", "anahtar": ANAHTAR},
    )
    client.post(
        "/api/modeller/secim",
        json={"rol": "planlayici", "saglayici": "anthropic", "model": "claude-haiku-4-5"},
    )
    client.delete("/api/modeller/secim?rol=planlayici")

    rol = next(x for x in client.get("/api/health").json()["roller"]
               if x["rol"] == "planlayici")
    assert rol["saglayici_kaynagi"] == "anahtar"
    assert rol["model"] == "claude-opus-5"


def test_karisik_kurulum_kosudan_once_uyarir(client):
    """Gerçek koşuda yaşandı: anahtar yalnızca planlayıcıya girildi,
    planlayıcı gerçek bir plan üretti, uygulayıcı replay'de kaset bulamadı
    ve koşu ortada kaldı. Sistem bunu başlamadan önce biliyordu."""
    client.post(
        "/api/anahtarlar",
        json={"rol": "planlayici", "saglayici": "anthropic", "anahtar": ANAHTAR},
    )
    uyari = client.get("/api/health").json()["yapilandirma_uyarisi"]
    assert uyari
    assert "planlayici" in uyari
    assert "uygulayici" in uyari


def test_tum_roller_anahtarliysa_uyari_yok(client):
    for rol in ("planlayici", "uygulayici", "denetleyici"):
        client.post(
            "/api/anahtarlar",
            json={"rol": rol, "saglayici": "anthropic", "anahtar": ANAHTAR},
        )
    data = client.get("/api/health").json()
    assert data["yapilandirma_uyarisi"] == ""
    assert data["cevrimdisi_mod"] is False


def test_hicbir_anahtar_yoksa_uyari_yok(client):
    """Saf replay tutarlı bir kurulumdur; uyarı gerektirmez."""
    data = client.get("/api/health").json()
    assert data["yapilandirma_uyarisi"] == ""
    assert data["cevrimdisi_mod"] is True


def test_replayde_kasetsiz_model_secimi_uyarir(client):
    """Gerçek koşuda yaşandı: demo kopyasında kalmış bir model seçimi
    (denetleyici → claude-sonnet-5) kasetlerle uyuşmadığı için kayıtlı
    senaryo denetleyici adımında düştü."""
    client.post(
        "/api/modeller/secim",
        json={"rol": "denetleyici", "saglayici": "anthropic", "model": "yok-boyle-model"},
    )
    uyari = client.get("/api/health").json()["yapilandirma_uyarisi"]
    assert "cassettes" in uyari
    assert "yok-boyle-model" in uyari


def test_katalog_anahtarsiz_reddedilir(client):
    r = client.get("/api/modeller?saglayici=anthropic")
    assert r.status_code == 400
    assert "API key" in r.json()["detail"]


def test_anahtarlar_temizlenebilir(client):
    client.post(
        "/api/anahtarlar",
        json={"rol": "planlayici", "saglayici": "anthropic", "anahtar": ANAHTAR},
    )
    assert client.delete("/api/anahtarlar").status_code == 200
    assert client.get("/api/anahtarlar").json()["anahtarlar"] == []


# ==========================================================================
# Kütüphane uçları
# ==========================================================================


def test_bos_kutuphane(client):
    data = client.get("/api/oyunlar").json()
    assert data["toplam"] == data["oynanabilir"]


def test_olmayan_gorev_404(client):
    assert client.get("/api/oyunlar/yok-boyle-bir-sey").status_code == 404


@pytest.mark.parametrize("kotu", ["..", "../gizli", "g-1/../../kacis"])
def test_yol_kacisi_reddedilir(client, kotu):
    assert client.get(f"/api/oyunlar/{kotu}").status_code == 404


def test_izin_listesi_disindaki_dosya_sunulmaz(client):
    assert client.get("/oyun/g-1/gizli.env").status_code == 404


def test_ana_sayfa_acilir(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Agent Workshop" in response.text
