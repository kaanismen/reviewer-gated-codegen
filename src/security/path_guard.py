"""Yol koruması — PROJECT.md §6, tehdit T1.

Tek kural: üretilen kodun dokunabileceği her yol, görevin workspace kökü
altında kalmalıdır. Kontrol dize karşılaştırmasıyla değil, **kanonikleştirme
sonrası** yapılır — `logic/../../../etc/passwd` dize olarak masum görünür.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

# Sürücü harfi (C:), UNC (\\sunucu) gibi Windows mutlak yol biçimleri.
_WINDOWS_ABSOLUTE = re.compile(r"^(?:[A-Za-z]:|\\\\)")


class PathViolation(ValueError):
    """Workspace dışına çıkma girişimi. Kurtarma yoktur (G5)."""


def _reject(relative: str, reason: str) -> PathViolation:
    return PathViolation(f"yol reddedildi ({reason}): {relative!r}")


def safe_join(workspace_root: Path, relative: str) -> Path:
    """Göreli yolu workspace köküne güvenli biçimde ekler.

    Kanonikleştirme sembolik bağlantıları da çözer: workspace içindeki bir
    sembolik bağlantı dışarıyı gösteriyorsa bu kontrol onu yakalar.
    """
    if not relative or not relative.strip():
        raise _reject(relative, "boş")
    if "\x00" in relative:
        raise _reject(relative, "null bayt")
    if "\\" in relative:
        # Linux'ta ters bölü geçerli bir dosya adı karakteridir, ama üretilen
        # oyun dosyalarında meşru bir kullanımı yoktur ve yol ayracı
        # belirsizliği yaratır.
        raise _reject(relative, "ters bölü")
    if relative.startswith("/") or _WINDOWS_ABSOLUTE.match(relative):
        raise _reject(relative, "mutlak yol")

    candidate = PurePosixPath(relative)
    if any(part == ".." for part in candidate.parts):
        raise _reject(relative, "üst dizin başvurusu")

    root = Path(workspace_root).resolve()
    resolved = (root / candidate).resolve()

    if resolved == root:
        raise _reject(relative, "kökün kendisi")
    if not resolved.is_relative_to(root):
        # Sembolik bağlantı dışarı çıkıyorsa buraya düşer.
        raise _reject(relative, "workspace dışına çözümlendi")
    return resolved


def is_inside(workspace_root: Path, candidate: Path) -> bool:
    """Var olan bir yolun kök altında kalıp kalmadığını söyler."""
    try:
        return Path(candidate).resolve().is_relative_to(Path(workspace_root).resolve())
    except (OSError, ValueError):
        return False


def all_inside(workspace_root: Path, paths: list[str]) -> bool:
    """Durum makinesi G4 koruma koşulunun beslendiği kontrol."""
    for relative in paths:
        try:
            safe_join(workspace_root, relative)
        except PathViolation:
            return False
    return True
