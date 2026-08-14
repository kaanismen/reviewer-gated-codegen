"""Transkript kaydı, kalıcılık ve dışa aktarım — PROJECT.md §7.5.

Kalıcılık kararı: her görev kendi workspace dizininde `transkript.json` ve
`transkript.md` olarak saklanır. Oturum kapansa da denetlenebilir kalır.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.transcript.models import AgentMessage, Role


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Transcript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gorev_id: str
    gorev_metni: str
    baslangic: datetime = Field(default_factory=_utcnow)
    bitis: datetime | None = None
    son_durum: str | None = None
    saglayici: str = ""
    model_eslemesi: dict[str, str] = Field(default_factory=dict)
    prompt_hashleri: dict[str, str] = Field(default_factory=dict)
    mesajlar: list[AgentMessage] = Field(default_factory=list)
    rapor: dict[str, object] = Field(default_factory=dict)

    # -- biriktirme ---------------------------------------------------------

    def add(self, message: AgentMessage) -> None:
        """Mesajı ekler ve köken bilgisini üstveriye yansıtır.

        Prompt hash'leri mesajlardan toplanır, ayrıca elle tutulmaz: tek
        kaynak mesajın kendisidir, iki yerin birbirinden sapması imkânsız olur.
        """
        self.mesajlar.append(message)
        if message.prompt_surumu and message.prompt_hash:
            self.prompt_hashleri[message.prompt_surumu] = message.prompt_hash
        if message.model and message.rol is not Role.SISTEM:
            self.model_eslemesi[message.rol.value] = message.model

    def close(self, son_durum: str, rapor: dict[str, object] | None = None) -> None:
        self.bitis = _utcnow()
        self.son_durum = son_durum
        self.rapor = rapor or {}

    # -- toplamlar ----------------------------------------------------------

    @property
    def toplam_token_girdi(self) -> int:
        return sum(m.token_girdi for m in self.mesajlar)

    @property
    def toplam_token_cikti(self) -> int:
        return sum(m.token_cikti for m in self.mesajlar)

    @property
    def toplam_maliyet_usd(self) -> Decimal:
        return sum((m.maliyet_usd for m in self.mesajlar), Decimal("0"))

    @property
    def tur_sayisi(self) -> int:
        return max((m.tur for m in self.mesajlar), default=0)

    # -- dışa aktarım -------------------------------------------------------

    def to_json(self) -> str:
        payload = json.loads(self.model_dump_json(by_alias=True))
        payload["toplamlar"] = {
            "token_girdi": self.toplam_token_girdi,
            "token_cikti": self.toplam_token_cikti,
            "maliyet_usd": str(self.toplam_maliyet_usd),
            "tur": self.tur_sayisi,
            "mesaj": len(self.mesajlar),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            f"# Transkript — {self.gorev_id}",
            "",
            f"**Görev:** {self.gorev_metni}",
            "",
            "| Alan | Değer |",
            "|---|---|",
            f"| Başlangıç | {self.baslangic.isoformat()} |",
            f"| Bitiş | {self.bitis.isoformat() if self.bitis else '—'} |",
            f"| Son durum | {self.son_durum or '—'} |",
            f"| Sağlayıcı | {self.saglayici or '—'} |",
            f"| Tur | {self.tur_sayisi} |",
            f"| Token (girdi/çıktı) | {self.toplam_token_girdi} / {self.toplam_token_cikti} |",
            f"| Maliyet | ${self.toplam_maliyet_usd} |",
            "",
            "## Prompt sürümleri",
            "",
        ]
        if self.prompt_hashleri:
            lines += ["| Sürüm | sha256 (ilk 12) |", "|---|---|"]
            lines += [f"| `{k}` | `{v}` |" for k, v in sorted(self.prompt_hashleri.items())]
        else:
            lines.append("_Kayıt yok._")

        lines += ["", "## Mesajlar", ""]
        for message in self.mesajlar:
            kaynak = message.prompt_surumu or "sistem"
            lines += [
                f"### Tur {message.tur} · {message.rol.value} · `{kaynak}`",
                "",
                "```json",
                message.icerik.model_dump_json(indent=2, by_alias=True),
                "```",
                "",
            ]

        if self.rapor:
            lines += ["## Son rapor", "", "```json",
                      json.dumps(self.rapor, ensure_ascii=False, indent=2), "```", ""]
        return "\n".join(lines)


class TranscriptStore:
    """Transkripti diske yazar. Yol üretimi tek yerde toplanır."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def directory_for(self, gorev_id: str) -> Path:
        return self.root / gorev_id

    def save(self, transcript: Transcript) -> Path:
        directory = self.directory_for(transcript.gorev_id)
        directory.mkdir(parents=True, exist_ok=True)
        json_path = directory / "transkript.json"
        json_path.write_text(transcript.to_json(), encoding="utf-8")
        (directory / "transkript.md").write_text(
            transcript.to_markdown(), encoding="utf-8"
        )
        return json_path

    def load(self, gorev_id: str) -> Transcript:
        path = self.directory_for(gorev_id) / "transkript.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("toplamlar", None)  # türetilmiş alan, modele geri yazılmaz
        return Transcript.model_validate(data)
