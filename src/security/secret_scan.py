"""Sır taraması — PROJECT.md §6, tehdit T5.

Desen tabanlıdır ve bu bilinçli bir sınırdır (bilinen sınır S3): bilinmeyen
biçimde bir anahtar yakalanmayabilir. İki telafi vardır — (1) `KeyVault`
bilinen anahtarları birebir eşleşmeyle siler, desene ihtiyaç duymaz;
(2) alt sürece hiçbir anahtar geçirilmez, dolayısıyla üretilen kodun
sızdıracak bir anahtarı yoktur.

Bulgular anahtarın kendisini ASLA taşımaz; yalnızca tür, konum ve maske.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# (ad, desen). Sıra anlamlı değil; hepsi taranır.
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("anthropic", re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}")),
    ("openai", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}")),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github", re.compile(r"(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{36}")),
    ("github-pat", re.compile(r"github_pat_[A-Za-z0-9_]{22,}")),
    ("google", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("slack", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]+")),
    ("bearer", re.compile(r"[Bb]earer\s+[A-Za-z0-9._\-]{20,}")),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
)


@dataclass(frozen=True)
class SecretFinding:
    """Bulgu; sırrın kendisini içermez."""

    tur: str
    maske: str
    konum: int

    def as_dict(self) -> dict[str, object]:
        return {"tur": self.tur, "maske": self.maske, "konum": self.konum}


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}…{value[-4:]}"


def scan(text: str) -> list[SecretFinding]:
    """Metinde sır arar. Bulgular konuma göre sıralı döner."""
    findings: list[SecretFinding] = []
    for name, pattern in PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                SecretFinding(tur=name, maske=_mask(match.group(0)), konum=match.start())
            )
    findings.sort(key=lambda f: (f.konum, f.tur))
    return findings


def is_clean(text: str) -> bool:
    """G6 koruma koşulunun beslendiği kontrol."""
    return not scan(text)


def redact(text: str) -> str:
    """Desenle eşleşen sırları maskeler.

    `KeyVault.redact()` ile birlikte kullanılır: kasa bilinenleri birebir
    siler, bu işlev bilinmeyen ama tanıdık biçimdekileri yakalar.
    """
    for _, pattern in PATTERNS:
        text = pattern.sub("[SIR GİZLENDİ]", text)
    return text
