"""Planlayıcı — görevi adımlara ve test edilebilir kabul kriterlerine böler.

Kullanıcı görevi prompta gömülmez; sınırlandırılmış bir veri bloğu olarak
iletilir (§6/T3). Sınırlayıcıyı taklit eden içerik `input_guard` tarafından
zaten etkisizleştirilmiştir.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.agents.base import Agent
from src.llm.provider import Message
from src.security.input_guard import as_data_block
from src.transcript.models import PlannerContent, Role


class PlannerAgent(Agent):
    rol = Role.PLANLAYICI

    @property
    def content_model(self) -> type[BaseModel]:
        return PlannerContent

    def messages_for(self, gorev_metni: str, onceki_hata: str = "") -> list[Message]:
        """Planlayıcıya gidecek mesaj listesi.

        `onceki_hata` yalnızca ilk denemede şema hatası olduğunda dolar
        (G3r). Hatanın ne olduğu modele geri verilir — aksi hâlde aynı
        hatayı tekrarlaması beklenir.
        """
        messages = [Message(rol="user", icerik=as_data_block(gorev_metni))]
        if onceki_hata:
            messages.append(
                Message(
                    rol="user",
                    icerik=(
                        "Önceki yanıtın şemaya uymadı ve reddedildi. "
                        f"Hata: {onceki_hata}\n"
                        "Yalnızca geçerli JSON döndür, başka metin yazma."
                    ),
                )
            )
        return messages
