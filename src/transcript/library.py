"""Oyun kütüphanesi — üretilmiş oyunların listelenmesi ve sunulması.

Her görev kendi dizinini alır (`workspaces/<gorev_id>/`) ve orada kalır.
Ayrı bir dizin/indeks dosyası **tutulmaz**: kütüphane, her görevin
`transkript.json` dosyasını okuyarak listeyi türetir. Gerekçe, indeksin
gerçekle sapamamasıdır — iki kayıt yerine tek kaynak.

Dizin adları dışarıdan (URL yolundan) gelebileceği için her erişim yol
korumasından geçer; bu modül `workspaces/` dışına asla çıkmaz.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.security.path_guard import PathViolation, safe_join

# Tarayıcıya sunulabilecek dosyalar. İzin listesidir: üretilen dizinde
# beklenmedik bir dosya oluşursa (ör. bir kaçış denemesinin artığı)
# sunulmaz.
SERVABLE_FILES: frozenset[str] = frozenset(
    {"game.html", "logic.js", "logic.test.js", "transkript.json", "transkript.md"}
)

PLAYABLE_ENTRY = "game.html"
ACCEPTED_STATE = "KABUL_EDILDI"

_SLUG_UNSAFE = re.compile(r"[^a-z0-9-]+")


@dataclass(frozen=True)
class GameEntry:
    gorev_id: str
    oyun: str
    gorev_metni: str
    son_durum: str
    olusturma: datetime
    tur: int
    maliyet_usd: Decimal
    oynanabilir: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "gorev_id": self.gorev_id,
            "oyun": self.oyun,
            "gorev_metni": self.gorev_metni,
            "son_durum": self.son_durum,
            "olusturma": self.olusturma.isoformat(),
            "tur": self.tur,
            "maliyet_usd": str(self.maliyet_usd),
            "oynanabilir": self.oynanabilir,
        }


def slugify(text: str) -> str:
    """Oyun adını dizin adında kullanılabilir hale getirir."""
    lowered = text.translate(str.maketrans({"İ": "i", "I": "ı"})).lower()
    replacements = {"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c"}
    for source, target in replacements.items():
        lowered = lowered.replace(source, target)
    slug = _SLUG_UNSAFE.sub("-", lowered).strip("-")
    return slug[:32] or "oyun"


class GameLibrary:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # -- kimlik üretimi -----------------------------------------------------

    def new_task_id(self, oyun_ipucu: str = "", now: datetime | None = None) -> str:
        """Sıralanabilir ve okunabilir bir görev kimliği üretir.

        Zaman öneki sayesinde dizin listesi kronolojik sıralanır; oyun adı
        eki sayesinde eğitmen dosya sisteminde de ne olduğunu görür.
        """
        moment = now or datetime.now(timezone.utc)
        stamp = moment.strftime("%Y%m%d-%H%M%S")
        base = f"{stamp}-{slugify(oyun_ipucu)}" if oyun_ipucu else stamp

        candidate, suffix = base, 2
        while (self.root / candidate).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def create(self, gorev_id: str) -> Path:
        directory = self.directory_for(gorev_id)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    # -- güvenli erişim -----------------------------------------------------

    def directory_for(self, gorev_id: str) -> Path:
        """Görev dizinini döndürür. Kimlik dışarıdan gelir, doğrulanır."""
        return safe_join(self.root, gorev_id)

    def file_path(self, gorev_id: str, filename: str) -> Path | None:
        """Sunulabilir bir dosyanın yolu; yoksa veya izinli değilse None.

        İki katmanlı: önce izin listesi (hangi dosya adları sunulur), sonra
        yol koruması (kimlik `..` veya mutlak yol içeremez).
        """
        if filename not in SERVABLE_FILES:
            return None
        try:
            path = safe_join(self.root, f"{gorev_id}/{filename}")
        except PathViolation:
            return None
        return path if path.is_file() else None

    # -- listeleme ----------------------------------------------------------

    def entries(self) -> list[GameEntry]:
        """Tüm görevleri, en yeniden eskiye. Bozuk kayıtlar atlanır."""
        if not self.root.is_dir():
            return []
        found: list[GameEntry] = []
        for directory in self.root.iterdir():
            if not directory.is_dir():
                continue
            entry = self._read(directory)
            if entry is not None:
                found.append(entry)
        found.sort(key=lambda e: e.olusturma, reverse=True)
        return found

    def playable(self) -> list[GameEntry]:
        return [e for e in self.entries() if e.oynanabilir]

    def get(self, gorev_id: str) -> GameEntry | None:
        try:
            directory = self.directory_for(gorev_id)
        except PathViolation:
            return None
        return self._read(directory) if directory.is_dir() else None

    def _read(self, directory: Path) -> GameEntry | None:
        """Bir görev dizinini kayda çevirir.

        Transkripti bozuk veya eksik olan dizin listelenmez: yarım kalmış
        bir koşunun artığı, kullanıcıya oynanabilir bir oyunmuş gibi
        görünmemeli.
        """
        transcript_path = directory / "transkript.json"
        if not transcript_path.is_file():
            return None
        try:
            data = json.loads(transcript_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        try:
            created = datetime.fromisoformat(str(data.get("baslangic")))
        except (TypeError, ValueError):
            created = datetime.fromtimestamp(
                transcript_path.stat().st_mtime, tz=timezone.utc
            )
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        son_durum = str(data.get("son_durum") or "")
        totals = data.get("toplamlar") or {}

        return GameEntry(
            gorev_id=directory.name,
            oyun=self._game_name(data),
            gorev_metni=str(data.get("gorev_metni") or ""),
            son_durum=son_durum,
            olusturma=created,
            tur=int(totals.get("tur") or 0),
            maliyet_usd=Decimal(str(totals.get("maliyet_usd") or "0")),
            oynanabilir=(
                son_durum == ACCEPTED_STATE and (directory / PLAYABLE_ENTRY).is_file()
            ),
        )

    @staticmethod
    def _game_name(data: dict) -> str:
        """Oyun adını planlayıcı mesajından çıkarır."""
        for message in data.get("mesajlar") or []:
            if message.get("rol") == "planlayici":
                oyun = (message.get("icerik") or {}).get("oyun")
                if oyun:
                    return str(oyun)
        return "bilinmiyor"

    # -- silme --------------------------------------------------------------

    def delete(self, gorev_id: str) -> bool:
        import shutil

        try:
            directory = self.directory_for(gorev_id)
        except PathViolation:
            return False
        if not directory.is_dir():
            return False
        shutil.rmtree(directory, ignore_errors=True)
        return not directory.exists()
