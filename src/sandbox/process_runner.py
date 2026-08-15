"""Sandbox süreç koşucusu — PROJECT.md §6, tehdit T2.

Katmanlar (§3.3): ayrıcalık düşürme · rlimit'ler · duvar saati · yol kısıtı ·
ortam temizliği. Statik içe aktarma denetimi bu modülden ÖNCE çalışır
(bkz. `tools/test_runner.py`) — reddedilen kod hiç çalıştırılmaz.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from src.orchestrator.limits import LIMITS, Limits

LAUNCHER = Path(__file__).resolve().parent / "launcher.py"

# Üretilen kod devasa çıktı üreterek belleği doldurmaya çalışabilir.
MAX_OUTPUT_BYTES = 64 * 1024

# Alt sürecin göreceği TEK ortam. API anahtarları, PYTHONPATH, ev dizini —
# hiçbiri geçmez (§6/T7).
CLEAN_ENV: dict[str, str] = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": "/tmp",
    "LANG": "C.UTF-8",
    "NODE_ENV": "test",
}


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    timed_out: bool
    signal_number: int | None
    privileges_dropped: bool

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    @property
    def summary(self) -> str:
        if self.timed_out:
            return f"zaman aşımı ({self.duration_sec:.1f} sn) — SIGKILL"
        if self.signal_number is not None:
            return f"sinyal {self.signal_number} ile sonlandırıldı"
        return f"çıkış kodu {self.exit_code}"


def _truncate(raw: bytes) -> str:
    text = raw[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    if len(raw) > MAX_OUTPUT_BYTES:
        text += f"\n… çıktı kesildi ({len(raw)} bayt)"
    return text


class ProcessRunner:
    def __init__(
        self,
        limits: Limits | None = None,
        user: str = "runner",
    ) -> None:
        self.limits = limits if limits is not None else LIMITS
        self.user = user

    def grant_access(self, workspace: Path) -> bool:
        """Workspace'i sandbox kullanıcısına devreder.

        Ayrıcalık düşürmenin doğrudan sonucu: app kökü root olarak dizin
        açar, ama kodu `runner` çalıştırır. Devir yapılmazsa `node` dizini
        `stat` bile edemez ve hata "üretilen kod bozuk" gibi görünür —
        gerçek sebep izin olduğu hâlde.

        Root değilsek gereksizdir ve sessizce atlanır.
        """
        if os.getuid() != 0 or not self.user:
            return False

        import pwd

        try:
            entry = pwd.getpwnam(self.user)
        except KeyError:
            return False

        workspace = Path(workspace)
        for path in [workspace, *workspace.rglob("*")]:
            try:
                os.chown(path, entry.pw_uid, entry.pw_gid)
            except OSError:
                return False
        return True

    def _argv(self, command: list[str], cwd: Path) -> list[str]:
        return [
            sys.executable,
            str(LAUNCHER),
            "--cpu", str(self.limits.rlimit_cpu_sec),
            "--mem-mb", str(self.limits.rlimit_memory_mb),
            "--nproc", str(self.limits.rlimit_processes),
            "--fsize-mb", str(self.limits.rlimit_file_mb),
            "--user", self.user,
            "--cwd", str(cwd),
            "--", *command,
        ]

    def run(self, command: list[str], cwd: Path) -> SandboxResult:
        """Komutu sandbox içinde çalıştırır. İstisna fırlatmaz.

        Sandbox'ın işi kötü kodu güvenle çalıştırmaktır; kötü kodun çökmesi
        beklenen bir sonuçtur, çağıranın yakalayacağı bir hata değil.
        """
        cwd = Path(cwd)
        if not cwd.is_dir():
            return SandboxResult(
                exit_code=126, stdout="", stderr=f"çalışma dizini yok: {cwd}",
                duration_sec=0.0, timed_out=False, signal_number=None,
                privileges_dropped=False,
            )

        started = time.monotonic()
        timed_out = False

        # start_new_session: alt süreç kendi süreç grubunu kurar; zaman
        # aşımında yalnızca node değil, çatalladığı her şey öldürülebilir.
        process = subprocess.Popen(
            self._argv(command, cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=CLEAN_ENV,
            cwd=str(cwd),
            start_new_session=True,
        )

        try:
            out, err = process.communicate(timeout=self.limits.sandbox_timeout_sec)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._kill_group(process)
            out, err = process.communicate()

        duration = time.monotonic() - started
        code = process.returncode
        return SandboxResult(
            exit_code=code,
            stdout=_truncate(out or b""),
            stderr=_truncate(err or b""),
            duration_sec=duration,
            timed_out=timed_out,
            signal_number=-code if code is not None and code < 0 else None,
            privileges_dropped=bool(self.user) and os.getuid() == 0,
        )

    @staticmethod
    def _kill_group(process: subprocess.Popen) -> None:
        """Süreç grubunu SIGKILL ile sonlandırır.

        SIGTERM denenmez: zaman aşımına uğramış kodun temiz kapanma hakkı
        yoktur ve sinyal işleyicisiyle SIGTERM'i yok sayabilir.
        """
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            process.kill()
