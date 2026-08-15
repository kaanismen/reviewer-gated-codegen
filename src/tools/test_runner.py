"""Test koşucusu — denetleyicinin elindeki tek nesnel ölçüm.

Sıra bağlayıcıdır: **önce statik denetim, sonra çalıştırma.** İzin verilmeyen
bir modül kullanan kod hiç çalıştırılmaz; bulgu denetleyiciye kritik olarak
gider ve revizyon turu başlatır (§3.3).

Çalıştırılamamış kod hiçbir koşulda "testler geçti" sayılmaz: bu durumda
`kalan = 1` döner, §7.4 iş kuralı da denetleyicinin KABUL'ünü geçersiz kılar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from src.orchestrator.limits import LIMITS, Limits
from src.sandbox.import_guard import ImportViolation, scan_workspace
from src.sandbox.process_runner import ProcessRunner, SandboxResult
from src.transcript.models import Finding, Severity, TestResult

_PASS = re.compile(r"^#\s*pass\s+(\d+)\s*$", re.MULTILINE)
_FAIL = re.compile(r"^#\s*fail\s+(\d+)\s*$", re.MULTILINE)
_TESTS = re.compile(r"^#\s*tests\s+(\d+)\s*$", re.MULTILINE)

MAX_OUTPUT_CHARS = 4_000


@dataclass(frozen=True)
class TestOutcome:
    test_sonucu: TestResult
    bulgular: list[Finding] = field(default_factory=list)
    calistirildi: bool = True
    sandbox: SandboxResult | None = None

    @property
    def passed(self) -> bool:
        return self.calistirildi and self.test_sonucu.kalan == 0 and self.test_sonucu.gecen > 0


def _clip(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n… ({len(text)} karakter, kısaltıldı)"


def _findings_from(violations: list[ImportViolation]) -> list[Finding]:
    return [
        Finding(dosya=v.dosya, sorun=f"{v.sorun} (satır {v.satir})", onem=Severity.KRITIK)
        for v in violations
    ]


def parse_tap(output: str) -> tuple[int, int]:
    """Node'un TAP özetinden (geçen, kalan) çıkarır.

    **Son eşleşme alınır, ilk değil.** Gerçek özet çıktının sonundadır;
    üretilen kod `console.log('# pass 99')` yazarak öne sahte bir özet
    enjekte edebilir. Son satırı almak bu enjeksiyonu etkisiz kılar.

    Özet satırı hiç yoksa güvenli tarafa düşülür: hiçbir test geçmemiş
    sayılır. Belirsizliği "başarı" olarak yorumlamak sistemi kandırmanın en
    ucuz yolu olurdu.
    """
    passed = _PASS.findall(output)
    failed = _FAIL.findall(output)
    if not passed and not failed:
        return 0, 1
    return int(passed[-1]) if passed else 0, int(failed[-1]) if failed else 0


class TestRunner:
    # pytest bu sınıfı "Test" önekinden dolayı toplamaya çalışmasın.
    __test__ = False

    def __init__(
        self,
        limits: Limits | None = None,
        runner: ProcessRunner | None = None,
    ) -> None:
        self.limits = limits if limits is not None else LIMITS
        self.runner = runner if runner is not None else ProcessRunner(self.limits)

    def run(self, workspace: Path) -> TestOutcome:
        workspace = Path(workspace)

        violations = scan_workspace(workspace)
        if violations:
            ozet = "; ".join(f"{v.dosya}:{v.satir} {v.sorun}" for v in violations[:5])
            return TestOutcome(
                test_sonucu=TestResult(
                    gecen=0,
                    kalan=1,
                    cikti=(
                        "Kod ÇALIŞTIRILMADI — statik içe aktarma denetimi reddetti.\n"
                        f"{ozet}"
                    ),
                ),
                bulgular=_findings_from(violations),
                calistirildi=False,
            )

        # Statik denetim geçti; ancak şimdi çalıştırma dizini ayrıcalıksız
        # kullanıcıya devredilir. Sıra bilinçli: reddedilen kodun bulunduğu
        # dizin hiç devredilmez.
        self.runner.grant_access(workspace)
        result = self.runner.run(["node", "--test"], workspace)

        if result.timed_out:
            return TestOutcome(
                test_sonucu=TestResult(
                    gecen=0,
                    kalan=1,
                    cikti=(
                        f"Zaman aşımı: {self.limits.sandbox_timeout_sec} sn içinde "
                        f"bitmedi, süreç SIGKILL ile sonlandırıldı.\n"
                        f"{_clip(result.stdout)}"
                    ),
                ),
                bulgular=[
                    Finding(
                        dosya="logic.test.js",
                        sorun="testler zaman aşımına uğradı (sonsuz döngü olabilir)",
                        onem=Severity.KRITIK,
                    )
                ],
                sandbox=result,
            )

        gecen, kalan = parse_tap(result.stdout)

        # Çıkış kodu bağımsız bir kanıttır ve enjekte edilemez: TAP özeti
        # ne derse desin, node sıfırdan farklı döndüyse koşu başarısızdır.
        # Sinyalle öldürülme (bellek, CPU) de buraya düşer.
        if result.exit_code != 0 and kalan == 0:
            kalan = max(kalan, 1)

        bulgular: list[Finding] = []
        if kalan > 0:
            bulgular.append(
                Finding(
                    dosya="logic.test.js",
                    sorun=f"{kalan} test başarısız ({result.summary})",
                    onem=Severity.ORTA,
                )
            )

        return TestOutcome(
            test_sonucu=TestResult(
                gecen=gecen,
                kalan=kalan,
                cikti=_clip(result.stdout or result.stderr),
            ),
            bulgular=bulgular,
            sandbox=result,
        )
