"""JSON çıkarma ve onarım — PROJECT.md §6/T4.

Modeller talimata rağmen JSON'u bozuk üretebiliyor. Gerçek koşuda görüldü:
minesweeper istendiğinde uygulayıcı ~9 KB üretti ve JSON yapısı bozuldu.

Onarım **katı ayrıştırma başarısız olduktan sonra** devreye girer ve yalnızca
tahmin gerektirmeyen iki hatayı düzeltir. Bu dosyanın yarısı, onarımın
neyi düzeltmediğini sınar — sessizce "geçerli" hale getirilen bozuk bir
çıktı, hatanın kendisinden tehlikelidir.
"""

from __future__ import annotations

import json

import pytest

from src.agents.base import AgentOutputError, extract_json, repair_json


# ==========================================================================
# Normal çıkarma
# ==========================================================================


def test_duz_json_okunur():
    payload, onarildi = extract_json('{"karar": "KABUL"}')
    assert payload == {"karar": "KABUL"}
    assert onarildi is False


def test_kod_blogu_icindeki_json_okunur():
    payload, _ = extract_json('```json\n{"a": 1}\n```')
    assert payload == {"a": 1}


def test_onundeki_aciklama_tolere_edilir():
    payload, _ = extract_json('İşte planınız:\n{"a": 1}')
    assert payload == {"a": 1}


def test_ic_ice_nesneler_dogru_kapanir():
    payload, _ = extract_json('{"d": {"e": {"f": 1}}, "g": 2}')
    assert payload["d"]["e"]["f"] == 1


def test_dize_icindeki_suslu_parantez_yanlis_kapatmaz():
    payload, _ = extract_json('{"kod": "function f() { return 1; }"}')
    assert payload["kod"] == "function f() { return 1; }"


# ==========================================================================
# Onarım — gerçek koşuda görülen hatalar
# ==========================================================================


def test_dize_icinde_kacissiz_satir_sonu_onarilir():
    """Modelin kodu JSON dizesine gömerken en sık yaptığı hata."""
    bozuk = '{"logic.js": "function f() {\nreturn 1;\n}"}'
    with pytest.raises(json.JSONDecodeError):
        json.loads(bozuk)

    payload, onarildi = extract_json(bozuk)
    assert onarildi is True
    assert payload["logic.js"] == "function f() {\nreturn 1;\n}"


def test_fazladan_virgul_onarilir():
    payload, onarildi = extract_json('{"a": [1, 2,], "b": 3,}')
    assert onarildi is True
    assert payload == {"a": [1, 2], "b": 3}


def test_sekme_karakteri_onarilir():
    payload, onarildi = extract_json('{"k": "girinti:\tdeger"}')
    assert onarildi is True
    assert "\t" in payload["k"]


def test_onarim_gecerli_json_e_dokunmaz():
    saglam = '{"a": "virgul, ve } parantez iceren dize", "b": [1, 2]}'
    assert json.loads(repair_json(saglam)) == json.loads(saglam)


def test_dize_icindeki_virgul_kapanis_ikilisi_bozulmaz():
    """Kör bir düzenli ifade burayı bozardı."""
    saglam = '{"metin": "dizi sonu, ] ve nesne sonu, } burada"}'
    payload, _ = extract_json(saglam)
    assert payload["metin"] == "dizi sonu, ] ve nesne sonu, } burada"


def test_kacisli_tirnak_dize_sonu_sayilmaz():
    payload, _ = extract_json('{"k": "o dedi ki: \\"merhaba\\", sonra gitti"}')
    assert payload["k"] == 'o dedi ki: "merhaba", sonra gitti'


# ==========================================================================
# Onarımın YAPMADIKLARI — tahmin gerektiren hiçbir şey
# ==========================================================================


def test_eksik_parantez_tamamlanmaz():
    """Kesilmiş çıktıyı 'tamamlamak' bozuk kodu geçerli göstermek olurdu."""
    with pytest.raises(AgentOutputError, match="kapanmamış"):
        extract_json('{"a": {"b": 1}')


def test_kivrik_tirnak_duzeltilmez():
    with pytest.raises(AgentOutputError):
        extract_json('{\u201ca\u201d: 1}')


def test_json_olmayan_metin_reddedilir():
    with pytest.raises(AgentOutputError, match="JSON nesnesi yok"):
        extract_json("Kodu inceledim, KABUL ediyorum.")


def test_bos_yanit_reddedilir():
    with pytest.raises(AgentOutputError, match="boş"):
        extract_json("   ")


def test_dizi_kok_reddedilir():
    """Şemalar nesne bekler; dizi kökü sessizce kabul edilmemeli."""
    with pytest.raises(AgentOutputError):
        extract_json("[1, 2, 3]")


def test_onarilamayan_bozukluk_hata_verir():
    with pytest.raises(AgentOutputError, match="onarım da işe yaramadı"):
        extract_json('{"a": 1 "b": 2}')
