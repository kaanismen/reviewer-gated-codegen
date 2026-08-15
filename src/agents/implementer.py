"""Uygulayıcı — planı sıfır bağımlılıklı JavaScript'e çevirir.

Bu agent'ın LLM çıktısı ile transkript kaydı **farklı şeylerdir**:

- LLM `{"dosyalar": {...}, "degisiklik_notu": "..."}` döndürür — bu dosya
  içerikleridir (`ImplementerWire`).
- Transkripte yazılan `ImplementerContent` ise dosyalar **MCP üzerinden
  yazıldıktan sonra** üretilir: hangi yol, kaç bayt, hangi hash, hangi araç
  çağrıları yapıldı (§7.3).

Ayrım bilinçli: transkript "model ne dedi"yi değil "fiilen ne oldu"yu
kaydeder. Model bir dosya döndürüp yazım başarısız olsaydı, kayıt bunu
gösterirdi.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.agents.base import Agent
from src.llm.provider import Message
from src.transcript.models import PlannerContent, ReviewerContent, Role

EXPECTED_FILES = ("logic.js", "logic.test.js", "game.html")


class ImplementerWire(BaseModel):
    """Uygulayıcının LLM çıktı biçimi — `prompts/implementer.v1.md` ile eşleşir."""

    model_config = ConfigDict(extra="forbid")

    dosyalar: dict[str, str] = Field(min_length=1)
    degisiklik_notu: str = ""

    def eksik_dosyalar(self) -> list[str]:
        return [name for name in EXPECTED_FILES if name not in self.dosyalar]


class ImplementerAgent(Agent):
    rol = Role.UYGULAYICI

    @property
    def content_model(self) -> type[BaseModel]:
        return ImplementerWire

    def messages_for(
        self,
        plan: PlannerContent,
        onceki_denetim: ReviewerContent | None = None,
        onceki_hata: str = "",
    ) -> list[Message]:
        """İlk tur planı, revizyon turları planı + red gerekçesini taşır."""
        messages = [
            Message(
                rol="user",
                icerik=(
                    "Aşağıdaki planı uygula.\n\n"
                    + plan.model_dump_json(indent=2, by_alias=True)
                ),
            )
        ]

        if onceki_denetim is not None:
            bulgular = "\n".join(
                f"- [{b.onem.value}] {b.dosya}: {b.sorun}"
                for b in onceki_denetim.bulgular
            )
            messages.append(
                Message(
                    rol="user",
                    icerik=(
                        "Önceki turun denetimi RED ile sonuçlandı.\n"
                        f"Gerekçe: {onceki_denetim.gerekce}\n"
                        f"Bulgular:\n{bulgular}\n\n"
                        "Yalnızca bu bulguları hedefle. Çalışan kodu değiştirme. "
                        "Yine de her dosyanın tam içeriğini döndür."
                    ),
                )
            )

        if onceki_hata:
            messages.append(
                Message(
                    rol="user",
                    icerik=(
                        f"Önceki yanıtın şemaya uymadı. Hata: {onceki_hata}\n"
                        "Yalnızca geçerli JSON döndür, başka metin yazma."
                    ),
                )
            )
        return messages
