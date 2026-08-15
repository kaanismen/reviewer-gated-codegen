"""Sandbox davranış testleri — PROJECT.md §6, tehdit T2.

Bu dosya GERÇEKTEN süreç başlatır. Faz 0'daki elle ölçümün (
`tests/manual/rlimit_olcumu.py`) otomatik karşılığıdır: orada iddia
ölçüldü, burada sürekli sınanır.

Node yoksa atlanır — testler konteynerde koşar, hostta değil.
"""

from __future__ import annotations

import shutil
import textwrap

import pytest

from src.orchestrator.limits import Limits
from src.sandbox.process_runner import CLEAN_ENV, ProcessRunner
from src.tools.test_runner import TestRunner, parse_tap

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node yok (konteyner dışında koşuluyor)"
)

HIZLI = Limits(
    sandbox_timeout_sec=10,
    rlimit_cpu_sec=3,
    rlimit_memory_mb=256,
    rlimit_processes=32,
    rlimit_file_mb=1,
)


@pytest.fixture
def runner():
    return ProcessRunner(HIZLI)


def write(workspace, **files) -> None:
    (workspace / "package.json").write_text('{"type":"module"}', encoding="utf-8")
    for name, content in files.items():
        (workspace / name.replace("__", ".")).write_text(
            textwrap.dedent(content), encoding="utf-8"
        )


# ==========================================================================
# Meşru kod engellenmemeli
# ==========================================================================


def test_mesru_kod_calisir(runner, sandbox_workspace):
    result = runner.run(["node", "-e", "console.log('merhaba')"], sandbox_workspace)
    assert result.ok
    assert "merhaba" in result.stdout


def test_ayricalik_dusuruldu(runner, sandbox_workspace):
    result = runner.run(["node", "-e", "console.log(process.getuid())"], sandbox_workspace)
    assert result.ok
    assert result.stdout.strip() != "0", "alt süreç root olarak çalışmamalı"


# ==========================================================================
# Kaynak limitleri
# ==========================================================================


def test_sonsuz_dongu_cpu_limitiyle_oldurulur(runner, sandbox_workspace):
    result = runner.run(["node", "-e", "while(true){Math.sqrt(Math.random())}"], sandbox_workspace)
    assert not result.ok
    assert result.signal_number is not None or result.timed_out


def test_duvar_saati_asimi_sigkill_ile_biter(sandbox_workspace):
    """CPU harcamayan ama askıda kalan süreç: rlimit yakalamaz, saat yakalar."""
    runner = ProcessRunner(Limits(sandbox_timeout_sec=2, rlimit_cpu_sec=60))
    result = runner.run(["node", "-e", "setTimeout(()=>{}, 600000)"], sandbox_workspace)
    assert result.timed_out
    assert result.duration_sec < 20
    assert "zaman aşımı" in result.summary


def test_bellek_balonu_durdurulur(runner, sandbox_workspace):
    result = runner.run(
        ["node", "-e", "const a=[];for(;;){a.push(Buffer.alloc(16*1024*1024))}"],
        sandbox_workspace,
    )
    assert not result.ok


def test_buyuk_dosya_yazimi_engellenir(runner, sandbox_workspace):
    result = runner.run(
        [
            "node",
            "-e",
            "require('fs').writeFileSync('buyuk.bin', Buffer.alloc(50*1024*1024))",
        ],
        sandbox_workspace,
    )
    assert not result.ok


def test_dev_cikti_kesilir(runner, sandbox_workspace):
    result = runner.run(
        ["node", "-e", "for(let i=0;i<200000;i++)console.log('x'.repeat(100))"],
        sandbox_workspace,
    )
    assert len(result.stdout) < 200_000
    assert "kesildi" in result.stdout


# ==========================================================================
# Ortam temizliği (T7)
# ==========================================================================


def test_api_anahtari_alt_surece_gecmez(runner, sandbox_workspace, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-SIZMAMALI-abcdefghijklmnop")
    result = runner.run(
        ["node", "-e", "console.log(Object.keys(process.env).sort().join(','))"],
        sandbox_workspace,
    )
    assert "ANTHROPIC_API_KEY" not in result.stdout
    assert "SIZMAMALI" not in result.stdout


def test_temiz_ortam_dar_tutulmus():
    assert set(CLEAN_ENV) == {"PATH", "HOME", "LANG", "NODE_ENV"}


def test_calisma_dizini_yoksa_hata_dondurur(runner, sandbox_workspace):
    result = runner.run(["node", "-e", "1"], sandbox_workspace / "olmayan")
    assert not result.ok
    assert "çalışma dizini yok" in result.stderr


# ==========================================================================
# Test koşucusu — statik denetim ÖNCE
# ==========================================================================


def test_gecen_testler_dogru_sayilir(sandbox_workspace):
    write(
        sandbox_workspace,
        logic__js="export const topla = (a, b) => a + b;",
        logic_test__js="""
            import { test } from 'node:test';
            import assert from 'node:assert/strict';
            import { topla } from './logic.js';
            test('toplar', () => assert.equal(topla(2, 3), 5));
            test('sifir', () => assert.equal(topla(0, 0), 0));
        """,
    )
    outcome = TestRunner(HIZLI).run(sandbox_workspace)
    assert outcome.calistirildi
    assert outcome.test_sonucu.gecen == 2
    assert outcome.test_sonucu.kalan == 0
    assert outcome.passed


def test_basarisiz_testler_bulgu_uretir(sandbox_workspace):
    write(
        sandbox_workspace,
        logic__js="export const topla = (a, b) => a - b;",
        logic_test__js="""
            import { test } from 'node:test';
            import assert from 'node:assert/strict';
            import { topla } from './logic.js';
            test('toplar', () => assert.equal(topla(2, 3), 5));
        """,
    )
    outcome = TestRunner(HIZLI).run(sandbox_workspace)
    assert outcome.test_sonucu.kalan == 1
    assert not outcome.passed
    assert outcome.bulgular


def test_yasak_modul_kullanan_kod_hic_calistirilmaz(sandbox_workspace):
    """En önemli test: reddedilen kod çalıştırılmaz, sadece başarısız olmaz."""
    write(
        sandbox_workspace,
        logic__js="import net from 'node:net';\nexport const x = () => net;",
        logic_test__js="""
            import { test } from 'node:test';
            test('bos', () => {});
        """,
    )
    outcome = TestRunner(HIZLI).run(sandbox_workspace)
    assert outcome.calistirildi is False
    assert outcome.sandbox is None, "sandbox hiç başlatılmamalı"
    assert outcome.test_sonucu.kalan == 1, "çalıştırılamamış kod geçmiş sayılamaz"
    assert outcome.bulgular[0].onem.value == "kritik"
    assert "ÇALIŞTIRILMADI" in outcome.test_sonucu.cikti


def test_sonsuz_donguyu_test_kosucusu_da_yakalar(sandbox_workspace):
    write(
        sandbox_workspace,
        logic__js="export const x = 1;",
        logic_test__js="""
            import { test } from 'node:test';
            test('asilir', () => { while (true) {} });
        """,
    )
    outcome = TestRunner(Limits(sandbox_timeout_sec=3, rlimit_cpu_sec=2)).run(sandbox_workspace)
    assert outcome.test_sonucu.kalan >= 1
    assert not outcome.passed


# ==========================================================================
# TAP ayrıştırma
# ==========================================================================


def test_ayni_kod_ayni_cikti_uretir(sandbox_workspace):
    """Kayıt/oynatmanın ön koşulu: aynı kod aynı metni üretmeli.

    Bu tutmazsa denetleyiciye giden istek her koşuda farklı olur ve kaset
    parmak izi asla eşleşmez. Temiz klon testinde tam olarak bu oldu:
    çıktıdaki `duration_ms` değerleri her koşuda değişiyordu.
    """
    write(
        sandbox_workspace,
        logic__js="export const topla = (a, b) => a + b;",
        logic_test__js="""
            import { test } from 'node:test';
            import assert from 'node:assert/strict';
            import { topla } from './logic.js';
            test('toplar', () => assert.equal(topla(2, 3), 5));
        """,
    )
    runner = TestRunner(HIZLI)
    ilk = runner.run(sandbox_workspace).test_sonucu.cikti
    ikinci = runner.run(sandbox_workspace).test_sonucu.cikti
    assert ilk == ikinci, "aynı kod iki koşuda farklı çıktı üretiyor"
    assert "duration_ms" not in ilk


def test_normalizasyon_gurultuyu_temizler():
    from src.tools.test_runner import normalize_output

    ham = (
        "ok 1 - kazanir\n"
        "  ---\n"
        "  duration_ms: 1.064724\n"
        "  ...\n"
        "# duration_ms 74.818849\n"
        "hata: /workspaces/20260815-103817-tic-tac-toe/logic.js:12\n"
    )
    temiz = normalize_output(ham)
    assert "duration_ms" not in temiz
    assert "20260815" not in temiz
    assert "<workspace>/logic.js:12" in temiz
    assert "ok 1 - kazanir" in temiz


def test_tap_ozeti_ayristirilir():
    assert parse_tap("# tests 5\n# pass 4\n# fail 1\n") == (4, 1)


def test_ozet_yoksa_basari_varsayilmaz():
    """Belirsizliği başarı saymak sistemi kandırmanın en ucuz yolu olurdu."""
    assert parse_tap("ok 1 - bir şey\n") == (0, 1)
    assert parse_tap("") == (0, 1)


def test_enjekte_edilmis_sahte_ozet_yaniltmaz():
    """Üretilen kod öne sahte bir TAP özeti basarak kandırmaya çalışabilir.

    Gerçek özet çıktının SONUNDADIR; ayrıştırıcı son eşleşmeyi alır.
    """
    kirli = "# pass 99\n# fail 0\nok 1\nnot ok 2\n# tests 2\n# pass 1\n# fail 1\n"
    assert parse_tap(kirli) == (1, 1)


def test_sahte_ozet_test_kosucusunu_da_kandiramaz(sandbox_workspace):
    """Uçtan uca: kod sahte özet bassa bile çıkış kodu bağımsız kanıttır."""
    write(
        sandbox_workspace,
        logic__js="export const x = 1;",
        logic_test__js="""
            import { test } from 'node:test';
            import assert from 'node:assert/strict';
            console.log('# tests 99');
            console.log('# pass 99');
            console.log('# fail 0');
            test('gercekte basarisiz', () => assert.equal(1, 2));
        """,
    )
    outcome = TestRunner(HIZLI).run(sandbox_workspace)
    assert outcome.test_sonucu.kalan >= 1
    assert not outcome.passed
