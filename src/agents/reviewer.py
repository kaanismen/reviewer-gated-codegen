"""Denetleyici — sistemin ana mekanizması.

Bu agent'ın **reddedebilmesi** projenin ayırt edici özelliği. İki koruma
denetleyicinin kendi beyanına güvenmemek üzerine kuruludur:

1. `test_sonucu` denetleyiciden değil, `TestRunner`ın fiilen ölçtüğü
   değerlerden alınır (§7.4 orkestratör kuralı). Denetleyici `kalan: 0`
   yazarak kendi çelişki denetimini atlatamaz.
2. Karar, `event_for_review()` üzerinden olaya çevrilir; `karar` alanına
   doğrudan bakan bir çağrı yeri yoktur.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.agents.base import Agent
from src.llm.provider import Message
from src.tools.test_runner import TestOutcome
from src.transcript.models import (
    Finding,
    PlannerContent,
    ReviewerContent,
    Role,
    Severity,
)

MAX_FILE_CHARS = 12_000


class ReviewerAgent(Agent):
    rol = Role.DENETLEYICI

    @property
    def content_model(self) -> type[BaseModel]:
        return ReviewerContent

    def messages_for(
        self,
        plan: PlannerContent,
        dosyalar: dict[str, str],
        outcome: TestOutcome,
        onceki_gerekce: str = "",
        onceki_hata: str = "",
    ) -> list[Message]:
        dosya_blogu = "\n\n".join(
            f"### {ad}\n```\n{icerik[:MAX_FILE_CHARS]}\n```"
            for ad, icerik in sorted(dosyalar.items())
        )
        bulgu_blogu = (
            "\n".join(f"- [{b.onem.value}] {b.dosya}: {b.sorun}" for b in outcome.bulgular)
            or "(sistem bulgusu yok)"
        )

        messages = [
            Message(
                rol="user",
                icerik=(
                    "## Plan\n"
                    + plan.model_dump_json(indent=2, by_alias=True)
                    + "\n\n## Üretilen dosyalar\n"
                    + dosya_blogu
                    + "\n\n## Test koşusu (sistem tarafından ölçüldü)\n"
                    + f"geçen: {outcome.test_sonucu.gecen}, "
                    + f"kalan: {outcome.test_sonucu.kalan}, "
                    + f"çalıştırıldı: {'evet' if outcome.calistirildi else 'HAYIR'}\n"
                    + f"```\n{outcome.test_sonucu.cikti[:4000]}\n```\n"
                    + "\n## Sistem bulguları\n"
                    + bulgu_blogu
                ),
            )
        ]

        if onceki_gerekce:
            messages.append(
                Message(
                    rol="user",
                    icerik=(
                        f"Önceki turdaki red gerekçen: {onceki_gerekce}\n"
                        "Yine reddedeceksen, neyin değişip neyin değişmediğini "
                        "açıkça yaz. Aynı gerekçeyi tekrarlarsan sistem "
                        "ilerleme olmadığını varsayıp durur."
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


def with_measured_tests(
    review: ReviewerContent, outcome: TestOutcome
) -> ReviewerContent:
    """Denetleyicinin beyan ettiği test sonucunu ölçülenle değiştirir.

    §7.4 orkestratör kuralı. Ayrıca sistemin kendi bulguları (statik denetim
    ihlalleri, zaman aşımı) denetleyicinin bulgularına eklenir: model onları
    bildirmemişse bile kayıtta görünmeliler.

    `RED` en az bir bulgu gerektirdiği için, ölçüm kararı RED'e çevirdiğinde
    ve ortada hiç bulgu yoksa sentetik bir bulgu üretilir — aksi hâlde
    şema doğrulaması düşerdi.
    """
    bulgular = list(review.bulgular)
    mevcut = {(b.dosya, b.sorun) for b in bulgular}
    for finding in outcome.bulgular:
        if (finding.dosya, finding.sorun) not in mevcut:
            bulgular.append(finding)

    if outcome.test_sonucu.kalan > 0 and not bulgular:
        bulgular.append(
            Finding(
                dosya="logic.test.js",
                sorun=f"{outcome.test_sonucu.kalan} test başarısız (sistem ölçümü)",
                onem=Severity.KRITIK,
            )
        )

    return ReviewerContent(
        karar=review.karar,
        gerekce=review.gerekce,
        bulgular=bulgular,
        test_sonucu=outcome.test_sonucu,
    )
