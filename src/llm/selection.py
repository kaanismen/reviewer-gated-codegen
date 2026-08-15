"""Rol bazlı model seçimi — kalıcı, çünkü sır değil.

Anahtarlar bilinçli olarak bellekte tutulur ve konteyner durunca kaybolur
(§3.3). Model seçimi farklı: gizli bir değer değil, bir tercih. Her
yeniden başlatmada yeniden seçtirmek gereksiz sürtünme yaratır, bu yüzden
diske yazılır.

Dosya `data/model-secimleri.json`; host'a bağlanmış bir dizinde durur.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.transcript.models import AGENT_ROLES, Role


@dataclass(frozen=True)
class RoleSelection:
    saglayici: str
    model: str

    def as_dict(self) -> dict[str, str]:
        return {"saglayici": self.saglayici, "model": self.model}


class SelectionStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._entries: dict[Role, RoleSelection] = {}
        self._load()

    # -- okuma --------------------------------------------------------------

    def get(self, rol: Role) -> RoleSelection | None:
        return self._entries.get(rol)

    def model_for(self, rol: Role, saglayici: str) -> str | None:
        """Yalnızca AYNI sağlayıcı için yapılmış seçim geçerlidir.

        Kullanıcı Anthropic için model seçip sonra OpenAI'a geçerse, eski
        seçim yeni sağlayıcıya gönderilmemeli — bu tam da düzeltilen
        hatanın kendisiydi.
        """
        entry = self._entries.get(rol)
        if entry is None or entry.saglayici != saglayici.strip().lower():
            return None
        return entry.model

    def as_dict(self) -> dict[str, dict[str, str]]:
        return {rol.value: sel.as_dict() for rol, sel in sorted(
            self._entries.items(), key=lambda kv: kv[0].value)}

    # -- yazma --------------------------------------------------------------

    def set(self, rol: Role, saglayici: str, model: str) -> RoleSelection:
        if rol not in AGENT_ROLES:
            raise ValueError(f"'{rol.value}' bir agent rolü değil")
        if not model.strip():
            raise ValueError("model kimliği boş olamaz")
        selection = RoleSelection(saglayici.strip().lower(), model.strip())
        self._entries[rol] = selection
        self._save()
        return selection

    def clear(self, rol: Role | None = None) -> None:
        if rol is None:
            self._entries.clear()
        else:
            self._entries.pop(rol, None)
        self._save()

    # -- kalıcılık ----------------------------------------------------------

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Bozuk seçim dosyası sistemi açılmaz yapmamalı; varsayılana düşülür.
            return
        for key, value in (data or {}).items():
            try:
                rol = Role(key)
            except ValueError:
                continue
            if rol in AGENT_ROLES and isinstance(value, dict):
                saglayici = str(value.get("saglayici") or "").lower()
                model = str(value.get("model") or "")
                if saglayici and model:
                    self._entries[rol] = RoleSelection(saglayici, model)

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.as_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            # Yazamamak bir tercih kaybıdır, koşuyu durdurmaz.
            pass
