"""Statik içe aktarma denetimi — PROJECT.md §6, tehdit T2b.

Üretilen kod **çalıştırılmadan önce** taranır. Yaklaşım izin listesidir,
yasak listesi değil: bilinmeyen bir modül adı reddedilir, çünkü üretilen
oyun mantığının meşru ihtiyacı üç şeyle sınırlıdır — test çatısı, doğrulama,
ve kendi göreli modülleri.

Bu, ağ ad alanı izolasyonunun yokluğunu telafi eden katmandır (bilinen
sınır S1). Desen tabanlıdır ve yeterince gizlenmiş kod tarafından teorik
olarak aşılabilir (S2); aşılsa dahi ayrıcalık düşürme, rlimit'ler ve
konteyner sınırı devrede kalır.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Üretilen kodun içe aktarabileceği TEK modül kümesi.
ALLOWED_MODULES: frozenset[str] = frozenset(
    {"node:test", "node:assert", "node:assert/strict"}
)

# import ... from "X" / import "X" / require("X") / import("X")
_SPECIFIER = re.compile(
    r"""(?:
          \bfrom\s*['"](?P<from>[^'"]+)['"]
        | \bimport\s*\(\s*['"](?P<dyn>[^'"]+)['"]\s*\)
        | \bimport\s+['"](?P<bare>[^'"]+)['"]
        | \brequire\s*\(\s*['"](?P<req>[^'"]+)['"]\s*\)
    )""",
    re.VERBOSE,
)

# Modül adı dize sabiti OLMAYAN dinamik biçimler. Bunlar izin listesiyle
# denetlenemez, bu yüzden topluca reddedilir.
_DYNAMIC = (
    (re.compile(r"\brequire\s*\(\s*(?!['\"])"), "dinamik require()"),
    (re.compile(r"\bimport\s*\(\s*(?!['\"])"), "dinamik import()"),
)

# Modül içe aktarmadan erişilebilen tehlikeli yetenekler.
_FORBIDDEN_CONSTRUCTS = (
    (re.compile(r"\beval\s*\("), "eval()"),
    (re.compile(r"\bnew\s+Function\s*\("), "new Function()"),
    (re.compile(r"\bfetch\s*\("), "fetch()"),
    (re.compile(r"\bXMLHttpRequest\b"), "XMLHttpRequest"),
    (re.compile(r"\bnavigator\s*\.\s*sendBeacon\b"), "navigator.sendBeacon"),
    (re.compile(r"\bprocess\s*\.\s*binding\b"), "process.binding"),
    (re.compile(r"\bprocess\s*\.\s*dlopen\b"), "process.dlopen"),
    (re.compile(r"\bprocess\s*\.\s*env\b"), "process.env"),
    (re.compile(r"\bWebAssembly\s*\.\s*(?:compile|instantiate)\b"), "WebAssembly"),
)


@dataclass(frozen=True)
class ImportViolation:
    dosya: str
    sorun: str
    satir: int

    def as_finding(self) -> dict[str, str]:
        """Denetleyiciye giden bulgu biçimi (§7.4). Her zaman kritik."""
        return {
            "dosya": self.dosya,
            "sorun": f"{self.sorun} (satır {self.satir})",
            "onem": "kritik",
        }


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _is_relative(specifier: str) -> bool:
    return specifier.startswith("./") or specifier.startswith("../")


def scan_source(source: str, filename: str = "<kaynak>") -> list[ImportViolation]:
    """Tek bir kaynak metnini denetler."""
    violations: list[ImportViolation] = []

    for match in _SPECIFIER.finditer(source):
        specifier = next(g for g in match.groups() if g is not None)
        if specifier in ALLOWED_MODULES:
            continue
        if _is_relative(specifier):
            # Göreli yollar ayrıca yol koruması tarafından denetlenir.
            if ".." in specifier:
                violations.append(
                    ImportViolation(
                        filename,
                        f"workspace dışına çıkan içe aktarma: {specifier!r}",
                        _line_of(source, match.start()),
                    )
                )
            continue
        violations.append(
            ImportViolation(
                filename,
                f"izin verilmeyen modül: {specifier!r}",
                _line_of(source, match.start()),
            )
        )

    for pattern, label in _DYNAMIC + _FORBIDDEN_CONSTRUCTS:
        for match in pattern.finditer(source):
            violations.append(
                ImportViolation(
                    filename, f"yasak yapı: {label}", _line_of(source, match.start())
                )
            )

    violations.sort(key=lambda v: (v.satir, v.sorun))
    return violations


def scan_workspace(workspace: Path, suffixes: tuple[str, ...] = (".js", ".mjs")) -> list[ImportViolation]:
    """Workspace'teki tüm JavaScript dosyalarını denetler.

    `game.html` taranmaz: tarayıcıda çalışır, sandbox'ta değil. Onun
    güvenliği tarayıcının kendi kum havuzuna bırakılmıştır — ancak
    `logic.js`'i içe aktardığı için mantık yine bu denetimden geçer.
    """
    violations: list[ImportViolation] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            violations.append(ImportViolation(path.name, f"okunamadı: {exc}", 0))
            continue
        violations.extend(scan_source(source, path.name))
    return violations
