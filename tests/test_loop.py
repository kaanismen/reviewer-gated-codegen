"""Ana döngü — uçtan uca, gerçek API çağrısı olmadan.

Sağlayıcı senaryolanmış sahte bir sınıfla değiştirilir; geri kalan her şey
gerçektir: MCP sunucusu alt süreç olarak çalışır, dosyalar diske yazılır,
`node --test` sandbox'ta koşar, transkript kaydedilir.

Bu, "LLM'i sahteleştir, gerisini sahteleştirme" ilkesinin uygulanmasıdır:
öngörülemez olan tek parça izole edilir, sistemin kendi mantığı gerçek
koşullarda sınanır.
"""

from __future__ import annotations

import json
import shutil
from uuid import uuid4

import pytest

from src.config import WORKSPACES_ROOT
from src.llm.provider import LlmProvider, LlmResponse, Usage
from src.orchestrator.limits import Limits
from src.orchestrator.loop import Orchestrator
from src.orchestrator.state_machine import State
from src.security.key_vault import KeyVault
from src.transcript.library import GameLibrary
from src.transcript.models import Role

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node yok (konteyner dışında koşuluyor)"
)

HIZLI = Limits(
    max_turns=3,
    sandbox_timeout_sec=15,
    rlimit_cpu_sec=5,
    rlimit_memory_mb=256,
    no_progress_threshold=2,
)

# --------------------------------------------------------------------------
# Senaryo parçaları
# --------------------------------------------------------------------------

PLAN = {
    "oyun": "tic-tac-toe",
    "uygulanabilirlik": {
        "karar": "UYGUN",
        "gerekce": "3x3 ızgara tek dizide tutulur, kazanma kontrolü saf fonksiyondur",
        "ozel_durum_sayisi": 2,
        "gerekli_ozellikler": ["ızgara durumu", "kazanma kontrolü"],
        "gercek_zamanli": False,
        "harici_varlik_gerekli": False,
    },
    "adimlar": ["tahtayı modelle", "kazanan() yaz", "arayüzü bağla"],
    "kabul_kriterleri": ["Üç aynı işaret yan yana gelince kazanan() o işareti döndürür"],
    "dosyalar": ["logic.js", "logic.test.js", "game.html"],
}

RET_PLANI = {
    "oyun": "satranç",
    "uygulanabilirlik": {
        "karar": "UYGUN_DEGIL",
        "gerekce": "rok, en passant ve şah/mat tespiti özel durum tavanını aşıyor",
        "ozel_durum_sayisi": 24,
        "gerekli_ozellikler": ["hamle üretimi", "şah tespiti"],
        "gercek_zamanli": False,
        "harici_varlik_gerekli": False,
    },
    "adimlar": [],
    "kabul_kriterleri": [],
    "dosyalar": [],
}

DOGRU_LOGIC = """
function kazanan(t) {
  const h = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
  for (const [a,b,c] of h) if (t[a] && t[a]===t[b] && t[a]===t[c]) return t[a];
  return null;
}
if (typeof module !== 'undefined' && module.exports) { module.exports = { kazanan }; }
"""

BOZUK_LOGIC = """
function kazanan(t) {
  const h = [[0,1,2],[3,4,5],[6,7,8]];
  for (const [a,b,c] of h) if (t[a] && t[a]===t[b] && t[a]===t[c]) return t[a];
  return null;
}
if (typeof module !== 'undefined' && module.exports) { module.exports = { kazanan }; }
"""

TEST_DOSYASI = """
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { kazanan } = require('./logic.js');
test('AC1: capraz kazanma', () => {
  assert.strictEqual(kazanan(['X',null,null,null,'X',null,null,null,'X']), 'X');
});
"""

AG_KULLANAN_LOGIC = """
const net = require('node:net');
function kazanan(t) { return null; }
if (typeof module !== 'undefined' && module.exports) { module.exports = { kazanan }; }
"""

OYUN_HTML = "<!doctype html><html><body><script src='logic.js'></script></body></html>"


def uygulama(logic: str = DOGRU_LOGIC, not_metni: str = "") -> dict:
    return {
        "dosyalar": {
            "logic.js": logic,
            "logic.test.js": TEST_DOSYASI,
            "game.html": OYUN_HTML,
        },
        "degisiklik_notu": not_metni,
    }


def denetim(karar: str, gerekce: str, gecen: int, kalan: int, bulgular=None) -> dict:
    return {
        "karar": karar,
        "gerekce": gerekce,
        "bulgular": bulgular
        if bulgular is not None
        else ([] if karar == "KABUL" else [
            {"dosya": "logic.js", "sorun": "çapraz hatlar eksik", "onem": "kritik"}
        ]),
        "test_sonucu": {"gecen": gecen, "kalan": kalan, "cikti": ""},
    }


# --------------------------------------------------------------------------
# Senaryolu sahte sağlayıcı
# --------------------------------------------------------------------------


class ScriptedProvider(LlmProvider):
    """Rol için sırayla verilen yanıtları döndürür."""

    name = "senaryo"

    def __init__(self, rol: Role, yanitlar: list) -> None:
        super().__init__()
        self.rol = rol
        self.yanitlar = list(yanitlar)
        self.cagri = 0

    def complete(self, request):
        self.cagri += 1
        if not self.yanitlar:
            raise AssertionError(f"{self.rol.value} için fazladan çağrı yapıldı")
        payload = self.yanitlar.pop(0)
        metin = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        return LlmResponse(
            metin=metin,
            kullanim=Usage.priced(request.model, 1200, 500),
            model=request.model,
            saglayici=self.name,
        )


@pytest.fixture
def library():
    """Gerçek workspace kökü altında geçici bir kütüphane.

    `tmp_path` kullanılmaz: ayrıcalık düşürülen sandbox süreci pytest'in
    dizin ağacına giremiyor (bkz. tests/conftest.py).
    """
    root = WORKSPACES_ROOT / f"loop-{uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield GameLibrary(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def build(library, plan, uygulamalar, denetimler, limits=HIZLI) -> Orchestrator:
    providers = {
        Role.PLANLAYICI: ScriptedProvider(Role.PLANLAYICI, plan),
        Role.UYGULAYICI: ScriptedProvider(Role.UYGULAYICI, uygulamalar),
        Role.DENETLEYICI: ScriptedProvider(Role.DENETLEYICI, denetimler),
    }
    return Orchestrator(
        vault=KeyVault(),
        library=library,
        limits=limits,
        provider_builder=lambda rol, config: providers[rol],
    )


# ==========================================================================
# Mutlu senaryo
# ==========================================================================


def test_tek_turda_kabul(library):
    orch = build(library, [PLAN], [uygulama()], [denetim("KABUL", "tüm testler geçti ve kriter karşılandı", 1, 0)])
    outcome = orch.run("tic tac toe oyunu yaz")

    assert outcome.durum is State.ACCEPTED
    assert outcome.basarili
    assert (outcome.workspace / "game.html").is_file()
    assert (outcome.workspace / "logic.js").is_file()


def test_transkript_diske_yazilir_ve_kutuphanede_gorunur(library):
    orch = build(library, [PLAN], [uygulama()], [denetim("KABUL", "tüm testler geçti ve kriter karşılandı", 1, 0)])
    outcome = orch.run("tic tac toe oyunu yaz")

    assert (outcome.workspace / "transkript.json").is_file()
    assert (outcome.workspace / "transkript.md").is_file()

    entries = library.entries()
    assert len(entries) == 1
    assert entries[0].oyun == "tic-tac-toe"
    assert entries[0].oynanabilir is True


def test_transkript_koken_bilgisini_tasir(library):
    orch = build(library, [PLAN], [uygulama()], [denetim("KABUL", "tüm testler geçti ve kriter karşılandı", 1, 0)])
    transcript = orch.run("tic tac toe oyunu yaz").transcript

    assert set(transcript.prompt_hashleri) >= {"planner.v1", "implementer.v1", "reviewer.v1"}
    assert transcript.toplam_maliyet_usd > 0
    assert transcript.toplam_token_girdi > 0


def test_mcp_cagrilari_transkripte_kaydedilir(library):
    """Sunumun 'en az bir MCP çağrısı' şartının kanıtı transkriptte durur."""
    orch = build(library, [PLAN], [uygulama()], [denetim("KABUL", "tüm testler geçti ve kriter karşılandı", 1, 0)])
    transcript = orch.run("tic tac toe oyunu yaz").transcript

    uygulayici = next(m for m in transcript.mesajlar if m.rol is Role.UYGULAYICI)
    araclar = [c.arac for c in uygulayici.icerik.arac_cagrilari]
    assert araclar == ["mcp:dosya_yaz"] * 3
    assert all(c.basarili for c in uygulayici.icerik.arac_cagrilari)


# ==========================================================================
# Red ve revizyon — sistemin ana mekanizması
# ==========================================================================


def test_red_sonrasi_revizyon_ve_kabul(library):
    orch = build(
        library,
        [PLAN],
        [uygulama(BOZUK_LOGIC), uygulama(DOGRU_LOGIC, "çapraz hatlar eklendi")],
        [
            denetim("RED", "kazanan() çapraz hatları kontrol etmiyor", 0, 1),
            denetim("KABUL", "çapraz hatlar eklendi, tüm testler geçti", 1, 0),
        ],
    )
    outcome = orch.run("tic tac toe oyunu yaz")

    assert outcome.durum is State.ACCEPTED
    assert outcome.rapor["tur"] == 2

    kararlar = [
        m.icerik.karar.value
        for m in outcome.transcript.mesajlar
        if m.rol is Role.DENETLEYICI
    ]
    assert kararlar == ["RED", "KABUL"]


def test_denetleyici_beyani_degil_olculen_sonuc_kaydedilir(library):
    """§7.4: denetleyici `kalan: 0` yazarak çelişki denetimini atlatamaz."""
    orch = build(
        library,
        [PLAN],
        [uygulama(BOZUK_LOGIC)],
        [
            denetim("KABUL", "bence her şey yolunda görünüyor", 99, 0),
            denetim("RED", "çapraz hatlar hâlâ eksik", 0, 1),
        ],
    )
    outcome = orch.run("tic tac toe oyunu yaz")

    ilk = next(m for m in outcome.transcript.mesajlar if m.rol is Role.DENETLEYICI)
    assert ilk.icerik.test_sonucu.gecen != 99, "beyan edilen sayı kullanılmamalı"
    assert ilk.icerik.test_sonucu.kalan > 0
    assert ilk.icerik.effective_decision.value == "RED"
    assert outcome.durum is not State.ACCEPTED


def test_ayni_gerekceyle_iki_red_ilerleme_yok_sayilir(library):
    orch = build(
        library,
        [PLAN],
        [uygulama(BOZUK_LOGIC), uygulama(BOZUK_LOGIC)],
        [
            denetim("RED", "çapraz hatlar eksik", 0, 1),
            denetim("RED", "Çapraz  hatlar EKSİK", 0, 1),
        ],
    )
    outcome = orch.run("tic tac toe oyunu yaz")

    assert outcome.durum is State.LIMIT_EXCEEDED
    assert outcome.rapor["uygulanan_kural"] == "G11"


def test_tur_tavani_dolunca_durur(library):
    limits = Limits(max_turns=2, sandbox_timeout_sec=15, rlimit_cpu_sec=5,
                    no_progress_threshold=5)
    orch = build(
        library,
        [PLAN],
        [uygulama(BOZUK_LOGIC)] * 2,
        [
            denetim("RED", "birinci sorun: çapraz hatlar eksik", 0, 1),
            denetim("RED", "ikinci sorun: beraberlik kontrolü yok", 0, 1),
        ],
        limits=limits,
    )
    outcome = orch.run("tic tac toe oyunu yaz")

    assert outcome.durum is State.LIMIT_EXCEEDED
    assert outcome.rapor["dolan_limit"]
    assert outcome.rapor["son_red_gerekcesi"]


# ==========================================================================
# Kapsam dışı — gerekçeli ret
# ==========================================================================


def test_kapsam_disi_hata_degildir(library):
    orch = build(library, [RET_PLANI], [], [])
    outcome = orch.run("satranç motoru yaz")

    assert outcome.durum is State.OUT_OF_SCOPE
    assert outcome.durum is not State.ERROR
    assert "en passant" in str(outcome.rapor["ret_gerekcesi"])
    assert library.entries()[0].oynanabilir is False


# ==========================================================================
# Hata yolları
# ==========================================================================


def test_kesilen_uygulayici_yaniti_yeniden_denenir(library):
    """Gerçek koşuda görüldü: token tavanına takılıp yarıda kesilen bir
    yanıt tek denemede HATA'ya düşürüyordu. Planlayıcı ve denetleyicinin
    yeniden deneme hakkı vardı, uygulayıcının yoktu."""
    kesik = json.dumps(uygulama())[:200]  # JSON ortadan kesilmiş
    orch = build(
        library,
        [PLAN],
        [kesik, uygulama()],
        [denetim("KABUL", "tüm testler geçti ve kriter karşılandı", 1, 0)],
    )
    outcome = orch.run("tic tac toe oyunu yaz")

    assert outcome.durum is State.ACCEPTED
    olaylar = [m.icerik.olay for m in outcome.transcript.mesajlar if m.rol is Role.SISTEM]
    assert "uygulayici_sema_hatasi" in olaylar


def test_iki_kez_kesilen_uygulayici_hataya_dusurur(library):
    kesik = json.dumps(uygulama())[:200]
    orch = build(library, [PLAN], [kesik, kesik], [])
    outcome = orch.run("tic tac toe oyunu yaz")

    assert outcome.durum is State.ERROR
    assert outcome.rapor["uygulanan_kural"] == "G4e"


def test_iki_kez_bozuk_plan_hataya_dusurur(library):
    orch = build(library, ["bu JSON değil", "yine JSON değil"], [], [])
    outcome = orch.run("tic tac toe oyunu yaz")

    assert outcome.durum is State.ERROR
    assert outcome.rapor["uygulanan_kural"] == "G3"


def test_ilk_bozuk_plan_yeniden_denenir(library):
    orch = build(
        library,
        ["bu JSON değil", PLAN],
        [uygulama()],
        [denetim("KABUL", "tüm testler geçti ve kriter karşılandı", 1, 0)],
    )
    assert orch.run("tic tac toe oyunu yaz").durum is State.ACCEPTED


def test_yasak_modul_kullanan_kod_calistirilmadan_reddedilir(library):
    """Statik denetim testten önce gelir; kod hiç çalıştırılmaz."""
    orch = build(
        library,
        [PLAN],
        [uygulama(AG_KULLANAN_LOGIC), uygulama(DOGRU_LOGIC, "ağ modülü kaldırıldı")],
        [
            denetim("RED", "ağ modülü içe aktarılmış, sandbox politikası ihlali", 0, 1),
            denetim("KABUL", "ağ modülü kaldırıldı, testler geçti", 1, 0),
        ],
    )
    outcome = orch.run("tic tac toe oyunu yaz")

    ilk = next(m for m in outcome.transcript.mesajlar if m.rol is Role.DENETLEYICI)
    assert "ÇALIŞTIRILMADI" in ilk.icerik.test_sonucu.cikti
    assert any(b.onem.value == "kritik" for b in ilk.icerik.bulgular)
    assert outcome.durum is State.ACCEPTED  # revizyon turu düzeltti


def test_sistem_mesajlari_akisi_anlatir(library):
    orch = build(library, [PLAN], [uygulama()], [denetim("KABUL", "tüm testler geçti ve kriter karşılandı", 1, 0)])
    transcript = orch.run("tic tac toe oyunu yaz").transcript

    olaylar = [
        m.icerik.olay for m in transcript.mesajlar if m.rol is Role.SISTEM
    ]
    assert "gorev_alindi" in olaylar
    assert "test_kosuldu" in olaylar


def test_bos_gorev_reddedilir(library):
    orch = build(library, [], [], [])
    from src.security.input_guard import InputRejected

    with pytest.raises(InputRejected):
        orch.run("   ")


def test_olay_dinleyicisi_her_mesaji_gorur(library):
    gorulen = []
    orch = build(library, [PLAN], [uygulama()], [denetim("KABUL", "tüm testler geçti ve kriter karşılandı", 1, 0)])
    orch.on_message = gorulen.append
    outcome = orch.run("tic tac toe oyunu yaz")

    assert len(gorulen) == len(outcome.transcript.mesajlar)
