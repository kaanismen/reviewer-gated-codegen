"""Oyun kütüphanesi — listeleme, kimlik üretimi ve yol koruması.

Görev kimliği URL yolundan gelir; bu modül yeni bir saldırı yüzeyidir.
Testlerin yarısı bu yüzden kaçış denemeleridir.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.transcript.library import GameLibrary, slugify

ISO = "2026-08-14T10:00:00+00:00"


def write_task(root, gorev_id, *, oyun="snake", son_durum="KABUL_EDILDI",
               baslangic=ISO, tur=2, maliyet="0.18", game_html=True,
               bozuk=False, transkript=True):
    directory = root / gorev_id
    directory.mkdir(parents=True, exist_ok=True)
    if game_html:
        (directory / "game.html").write_text("<html>oyun</html>", encoding="utf-8")
    if not transkript:
        return directory
    if bozuk:
        (directory / "transkript.json").write_text("{bozuk", encoding="utf-8")
        return directory
    payload = {
        "gorev_id": gorev_id,
        "gorev_metni": f"{oyun} yaz",
        "baslangic": baslangic,
        "son_durum": son_durum,
        "mesajlar": [{"rol": "planlayici", "icerik": {"oyun": oyun}}],
        "toplamlar": {"tur": tur, "maliyet_usd": maliyet},
    }
    (directory / "transkript.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    return directory


@pytest.fixture
def library(tmp_path) -> GameLibrary:
    return GameLibrary(tmp_path)


# --------------------------------------------------------------------------
# Kimlik üretimi
# --------------------------------------------------------------------------


def test_kimlik_siralanabilir_ve_okunabilir(library):
    moment = datetime(2026, 8, 14, 15, 30, 22, tzinfo=timezone.utc)
    assert library.new_task_id("connect-4", now=moment) == "20260814-153022-connect-4"


def test_ayni_saniyede_ikinci_gorev_cakismaz(library, tmp_path):
    moment = datetime(2026, 8, 14, 15, 30, 22, tzinfo=timezone.utc)
    first = library.new_task_id("snake", now=moment)
    (tmp_path / first).mkdir()
    assert library.new_task_id("snake", now=moment) == f"{first}-2"


@pytest.mark.parametrize(
    "girdi,beklenen",
    [
        ("Connect 4", "connect-4"),
        ("tic-tac-toe", "tic-tac-toe"),
        ("Işık Oyunu", "isik-oyunu"),
        ("çöp/../kaçış", "cop-kacis"),
        ("", "oyun"),
        ("!!!", "oyun"),
    ],
)
def test_slug_dizin_adinda_guvenli(girdi, beklenen):
    assert slugify(girdi) == beklenen


# --------------------------------------------------------------------------
# Listeleme
# --------------------------------------------------------------------------


def test_oyunlar_en_yeniden_eskiye_siralanir(library, tmp_path):
    write_task(tmp_path, "eski", baslangic="2026-08-13T10:00:00+00:00")
    write_task(tmp_path, "yeni", baslangic="2026-08-14T10:00:00+00:00")
    assert [e.gorev_id for e in library.entries()] == ["yeni", "eski"]


def test_kayit_alanlari_transkriptten_okunur(library, tmp_path):
    write_task(tmp_path, "g-001", oyun="connect-4", tur=3, maliyet="0.42")
    entry = library.entries()[0]
    assert entry.oyun == "connect-4"
    assert entry.tur == 3
    assert entry.maliyet_usd == Decimal("0.42")
    assert entry.oynanabilir is True


def test_kabul_edilmemis_gorev_oynanabilir_sayilmaz(library, tmp_path):
    write_task(tmp_path, "g-002", son_durum="LIMIT_ASILDI")
    entry = library.entries()[0]
    assert entry.oynanabilir is False
    assert library.playable() == []


def test_kapsam_disi_gorev_de_listelenir(library, tmp_path):
    """Gerekçeli ret de bir kayıttır; demo için görünür kalmalı."""
    write_task(tmp_path, "g-003", oyun="satranç", son_durum="KAPSAM_DISI",
               game_html=False)
    entry = library.entries()[0]
    assert entry.son_durum == "KAPSAM_DISI"
    assert entry.oynanabilir is False


def test_game_html_yoksa_oynanabilir_degil(library, tmp_path):
    write_task(tmp_path, "g-004", game_html=False)
    assert library.entries()[0].oynanabilir is False


def test_transkriptsiz_dizin_listelenmez(library, tmp_path):
    """Yarım kalmış bir koşunun artığı oyunmuş gibi görünmemeli."""
    write_task(tmp_path, "yarim", transkript=False)
    assert library.entries() == []


def test_bozuk_transkript_listeyi_cokertmez(library, tmp_path):
    write_task(tmp_path, "bozuk", bozuk=True)
    write_task(tmp_path, "saglam")
    assert [e.gorev_id for e in library.entries()] == ["saglam"]


def test_bos_kok_bos_liste_dondurur(library):
    assert library.entries() == []


def test_olmayan_kok_hata_vermez(tmp_path):
    assert GameLibrary(tmp_path / "yok").entries() == []


# --------------------------------------------------------------------------
# Yol koruması — kimlik URL'den gelir
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kotu",
    ["../gizli", "../../etc", "/etc/passwd", "g-001/../../kacis", "..", "."],
)
def test_kacis_denemeleri_reddedilir(library, tmp_path, kotu):
    write_task(tmp_path, "g-001")
    assert library.get(kotu) is None
    assert library.file_path(kotu, "game.html") is None
    assert library.delete(kotu) is False


def test_izin_listesi_disindaki_dosya_sunulmaz(library, tmp_path):
    directory = write_task(tmp_path, "g-001")
    (directory / "gizli.env").write_text("ANAHTAR=sk-ant-xxx", encoding="utf-8")
    assert library.file_path("g-001", "gizli.env") is None
    assert library.file_path("g-001", "transkript.json") is not None


def test_izinli_ama_var_olmayan_dosya_none_doner(library, tmp_path):
    write_task(tmp_path, "g-001", game_html=False)
    assert library.file_path("g-001", "game.html") is None


def test_oynanabilir_oyun_dosyasi_sunulur(library, tmp_path):
    write_task(tmp_path, "g-001")
    path = library.file_path("g-001", "game.html")
    assert path is not None and path.read_text(encoding="utf-8") == "<html>oyun</html>"


def test_silme_dizini_kaldirir(library, tmp_path):
    write_task(tmp_path, "g-001")
    assert library.delete("g-001") is True
    assert library.entries() == []


def test_olmayan_gorev_silinemez(library):
    assert library.delete("yok") is False
