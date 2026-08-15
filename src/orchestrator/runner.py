"""Görev yürütücüsü — tek eşzamanlı koşu, arka planda.

Varsayım V3 gereği aynı anda tek görev çalışır. İkinci istek sıraya
alınmaz, **reddedilir**: sıraya almak, kullanıcıya bitmiş gibi görünen ama
dakikalarca bekleyen bir iş bırakırdı.

Koşu ayrı bir iş parçacığında yürür; HTTP isteği dakikalarca açık
tutulmaz. Mesajlar biriktirilir, arayüz yoklayarak (veya Faz 5'te SSE ile)
okur.
"""

from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from src.orchestrator.limits import LIMITS, Limits
from src.orchestrator.loop import Orchestrator
from src.security.input_guard import InputRejected
from src.security.key_vault import KeyVault
from src.transcript.library import GameLibrary
from src.transcript.models import AgentMessage

JobState = Literal["calisiyor", "bitti", "hata"]


class TaskBusy(RuntimeError):
    """Halihazırda çalışan bir görev var (V3)."""


@dataclass
class Job:
    gorev_metni: str
    durum: JobState = "calisiyor"
    gorev_id: str = ""
    son_durum: str = ""
    rapor: dict[str, object] = field(default_factory=dict)
    hata: str = ""
    baslangic: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    mesajlar: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "durum": self.durum,
            "gorev_metni": self.gorev_metni,
            "gorev_id": self.gorev_id,
            "son_durum": self.son_durum,
            "rapor": self.rapor,
            "hata": self.hata,
            "baslangic": self.baslangic.isoformat(),
            "mesaj_sayisi": len(self.mesajlar),
            "mesajlar": self.mesajlar,
        }


class TaskRunner:
    def __init__(self, vault: KeyVault, library: GameLibrary, limits: Limits | None = None):
        self.vault = vault
        self.library = library
        self.limits = limits or LIMITS
        self._lock = threading.Lock()
        self._job: Job | None = None
        self._thread: threading.Thread | None = None

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def job(self) -> Job | None:
        return self._job

    def start(self, gorev_metni: str) -> Job:
        with self._lock:
            if self.busy:
                raise TaskBusy(
                    "halihazırda çalışan bir görev var; bitmesini bekleyin (V3)"
                )
            job = Job(gorev_metni=gorev_metni)
            self._job = job
            self._thread = threading.Thread(
                target=self._execute, args=(job,), daemon=True
            )
            self._thread.start()
            return job

    def _execute(self, job: Job) -> None:
        def sink(message: AgentMessage) -> None:
            job.mesajlar.append(
                {
                    "tur": message.tur,
                    "rol": message.rol.value,
                    "zaman": message.zaman.isoformat(),
                    "prompt_surumu": message.prompt_surumu,
                    "model": message.model,
                    "token_girdi": message.token_girdi,
                    "token_cikti": message.token_cikti,
                    "maliyet_usd": str(message.maliyet_usd),
                    "icerik": message.icerik.model_dump(mode="json", by_alias=True),
                }
            )

        orchestrator = Orchestrator(
            vault=self.vault,
            library=self.library,
            limits=self.limits,
            on_message=sink,
        )
        try:
            outcome = orchestrator.run(job.gorev_metni)
        except InputRejected as exc:
            job.durum, job.hata = "hata", str(exc)
            return
        except Exception as exc:  # noqa: BLE001 - iş parçacığı sessizce ölmemeli
            job.durum = "hata"
            job.hata = self.vault.redact(
                f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-600:]}"
            )
            return

        job.gorev_id = outcome.gorev_id
        job.son_durum = outcome.durum.value
        job.rapor = outcome.rapor
        job.durum = "bitti"
