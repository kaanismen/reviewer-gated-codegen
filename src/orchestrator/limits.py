"""Kontrol limitleri — PROJECT.md §5.

Tüm tavanlar tek yerde. Kod içinde çıplak sayı kullanmak yasaktır (§11);
bir limit gerekiyorsa buradan okunur. Her değer .env üzerinden geçersiz
kılınabilir, böylece demo sırasında (örneğin tur limiti 2'ye çekilerek)
hata senaryosu ucuza gösterilebilir.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from decimal import Decimal


def _int(var: str, default: int) -> int:
    raw = (os.getenv(var) or "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        return default
    # Sıfır veya negatif bir tavan, limitin tamamen kapanması demektir.
    return value if value > 0 else default


def _dec(var: str, default: str) -> Decimal:
    raw = (os.getenv(var) or "").strip()
    try:
        value = Decimal(raw) if raw else Decimal(default)
    except ArithmeticError:
        return Decimal(default)
    return value if value > 0 else Decimal(default)


@dataclass(frozen=True)
class Limits:
    # Orkestrasyon tavanları
    max_turns: int = 5
    max_tokens_total: int = 150_000
    max_cost_usd: Decimal = Decimal("1.00")
    max_duration_sec: int = 300
    no_progress_threshold: int = 2
    max_task_chars: int = 2_000

    # Sandbox tavanları (PROJECT.md §3.3)
    sandbox_timeout_sec: int = 30
    rlimit_cpu_sec: int = 25
    # RLIMIT_DATA olarak uygulanır, RLIMIT_AS olarak DEĞİL: V8'in pointer
    # compression için ayırdığı sanal adres alanı RLIMIT_AS'e sayılır ve
    # 512 MB'de meşru kod bile çöker. Ölçüm: tests/manual/rlimit_olcumu.py
    rlimit_memory_mb: int = 512
    rlimit_processes: int = 32
    rlimit_file_mb: int = 10

    @classmethod
    def from_env(cls) -> "Limits":
        return cls(
            max_turns=_int("MAX_TUR", 5),
            max_tokens_total=_int("MAX_TOKEN_TOPLAM", 150_000),
            max_cost_usd=_dec("MAX_MALIYET_USD", "1.00"),
            max_duration_sec=_int("MAX_SURE_SN", 300),
            no_progress_threshold=_int("ILERLEME_YOK_ESIGI", 2),
            max_task_chars=_int("MAX_GOREV_KARAKTER", 2_000),
            sandbox_timeout_sec=_int("SANDBOX_TIMEOUT_SN", 30),
            rlimit_cpu_sec=_int("RLIMIT_CPU_SN", 25),
            rlimit_memory_mb=_int("RLIMIT_BELLEK_MB", 512),
            rlimit_processes=_int("RLIMIT_SUREC", 32),
            rlimit_file_mb=_int("RLIMIT_DOSYA_MB", 10),
        )

    def as_dict(self) -> dict[str, str]:
        """Arayüzde ve transkriptte gösterim için."""
        return {f.name: str(getattr(self, f.name)) for f in fields(self)}


LIMITS = Limits.from_env()
