"""Ana döngü — durum makinesini gerçek agent'larla sürer.

Durum makinesi saftır (LLM yok, disk yok); bu dosya onun yan etkilerini
üstlenir: sağlayıcı çağrısı, MCP üzerinden dosya yazımı, sandbox'ta test
koşusu, transkript kaydı.

Sıra bağlayıcıdır ve tesadüfi değildir:

    plan → dosya yazımı → **statik denetim** → test koşusu → denetim

Statik denetim testten önce gelir çünkü reddedilen kod hiç çalıştırılmamalı;
test koşusu denetleyiciden önce gelir çünkü denetleyicinin kararı ölçülen
sonuçla karşılaştırılacak.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Callable

from src.agents.base import AgentOutputError, PromptMissing
from src.agents.implementer import ImplementerAgent, ImplementerWire
from src.agents.planner import PlannerAgent
from src.agents.reviewer import ReviewerAgent, with_measured_tests
from src.llm import factory
from src.llm.pricing import price_for
from src.llm.provider import ProviderError
from src.llm.selection import SelectionStore
from src.orchestrator.limits import LIMITS, BudgetTracker, Limits
from src.orchestrator.state_machine import (
    Event,
    IllegalTransition,
    Payload,
    RunContext,
    State,
    StateMachine,
    event_for_review,
)
from src.security import secret_scan
from src.security.input_guard import InputRejected, sanitize
from src.security.key_vault import KeyVault
from src.tools.mcp_client import McpClient, McpError
from src.tools.test_runner import TestRunner
from src.transcript.library import GameLibrary
from src.transcript.models import (
    AgentMessage,
    ImplementerContent,
    PlannerContent,
    ReviewerContent,
    Role,
    SystemContent,
    WrittenFile,
)
from src.transcript.store import Transcript, TranscriptStore

EventSink = Callable[[AgentMessage], None]


@dataclass
class RunOutcome:
    gorev_id: str
    durum: State
    rapor: dict[str, object]
    transcript: Transcript
    workspace: Path

    @property
    def basarili(self) -> bool:
        return self.durum is State.ACCEPTED


@dataclass
class Orchestrator:
    vault: KeyVault
    library: GameLibrary
    limits: Limits = field(default_factory=lambda: LIMITS)
    on_message: EventSink | None = None
    selections: SelectionStore | None = None
    # Testler sağlayıcıyı buradan enjekte eder; üretimde `factory` kullanılır.
    provider_builder: Callable[[Role, object], object] | None = None

    def _provider(self, rol: Role, config):
        if self.provider_builder is not None:
            return self.provider_builder(rol, config)
        return factory.build_provider(rol, self.vault, config, self.selections)

    # -- yardımcılar --------------------------------------------------------

    def _emit(self, transcript: Transcript, message: AgentMessage) -> None:
        transcript.add(message)
        if self.on_message is not None:
            self.on_message(message)

    def _system(
        self, transcript: Transcript, tur: int, olay: str, ayrinti: str = ""
    ) -> None:
        self._emit(
            transcript,
            AgentMessage(
                tur=tur,
                rol=Role.SISTEM,
                icerik=SystemContent(olay=olay, ayrinti=self.vault.redact(ayrinti)[:800]),
            ),
        )

    # -- ana akış -----------------------------------------------------------

    def run(self, gorev_metni: str) -> RunOutcome:
        task = sanitize(gorev_metni, self.limits.max_task_chars)

        gorev_id = self.library.new_task_id(task.text[:24])
        workspace = self.library.create(gorev_id)

        configs = {
            rol: factory.resolve_role(rol, self.vault, self.selections)
            for rol in (Role.PLANLAYICI, Role.UYGULAYICI, Role.DENETLEYICI)
        }
        transcript = Transcript(
            gorev_id=gorev_id,
            gorev_metni=task.text,
            saglayici=",".join(sorted({c.saglayici for c in configs.values()})),
        )
        store = TranscriptStore(self.library.root)

        context = RunContext(limits=self.limits, task_text=task.text)
        machine = StateMachine(context)
        budget = BudgetTracker(self.limits)

        try:
            self._drive(machine, transcript, budget, configs, workspace, task.text)
        except (PromptMissing, ProviderError, McpError, InputRejected) as exc:
            self._fail(machine, transcript, f"{type(exc).__name__}: {exc}")
        except IllegalTransition as exc:
            self._fail(machine, transcript, f"geçersiz durum geçişi: {exc}")
        except Exception as exc:  # kurtarılamayan istisna → G13
            self._fail(machine, transcript, f"beklenmeyen hata: {type(exc).__name__}: {exc}")

        rapor = machine.final_report()
        transcript.close(machine.state.value, rapor)
        store.save(transcript)
        return RunOutcome(
            gorev_id=gorev_id,
            durum=machine.state,
            rapor=rapor,
            transcript=transcript,
            workspace=workspace,
        )

    def _fail(self, machine: StateMachine, transcript: Transcript, detay: str) -> None:
        """Hatayı transkripte yazar ve makineyi son duruma taşır."""
        safe = self.vault.redact(detay)[:600]
        self._system(transcript, machine.context.turn, "hata", safe)
        if not machine.is_terminal:
            machine.fire(Event.UNEXPECTED_ERROR, Payload(detail=safe))

    # -- döngünün gövdesi ---------------------------------------------------

    def _drive(
        self,
        machine: StateMachine,
        transcript: Transcript,
        budget: BudgetTracker,
        configs: dict,
        workspace: Path,
        gorev_metni: str,
    ) -> None:
        machine.fire(Event.TASK_RECEIVED)
        self._system(transcript, 1, "gorev_alindi", gorev_metni[:200])

        # Fiyatı bilinmeyen model varsa maliyet rakamı bir ÜST SINIRDIR.
        # Transkript kesin bir rakammış gibi sunmamalı.
        bilinmeyen = [
            c.model for c in configs.values() if not price_for(c.model)[1]
        ]
        if bilinmeyen:
            self._system(
                transcript, 1, "maliyet_ust_sinir",
                "Şu modellerin fiyatı bilinmiyor, maliyet en pahalı bilinen "
                f"tarifeden hesaplandı (üst sınır): {', '.join(sorted(set(bilinmeyen)))}",
            )

        planner = PlannerAgent(
            self._provider(Role.PLANLAYICI, configs[Role.PLANLAYICI]),
            configs[Role.PLANLAYICI],
        )
        implementer = ImplementerAgent(
            self._provider(Role.UYGULAYICI, configs[Role.UYGULAYICI]),
            configs[Role.UYGULAYICI],
        )
        reviewer = ReviewerAgent(
            self._provider(Role.DENETLEYICI, configs[Role.DENETLEYICI]),
            configs[Role.DENETLEYICI],
        )

        plan = self._plan(machine, transcript, budget, planner, gorev_metni)
        if plan is None:
            return  # KAPSAM_DISI veya HATA

        onceki_denetim: ReviewerContent | None = None
        dosyalar: dict[str, str] = {}

        with McpClient(workspace) as mcp:
            while machine.state is State.IMPLEMENTING:
                tur = machine.context.turn

                breach = budget.check(tur)
                if breach is not None:
                    machine.fire(Event.LIMIT_HIT, Payload(limit_name=breach.limit_name))
                    self._system(transcript, tur, "limit_asildi", breach.detail)
                    return

                dosyalar = self._implement(
                    machine, transcript, budget, implementer, mcp, plan, onceki_denetim, tur
                )
                if machine.state is not State.REVIEWING:
                    return

                outcome = TestRunner(self.limits).run(workspace)
                self._system(
                    transcript,
                    tur,
                    "test_kosuldu",
                    f"geçen={outcome.test_sonucu.gecen} kalan={outcome.test_sonucu.kalan} "
                    f"çalıştırıldı={'evet' if outcome.calistirildi else 'hayır'}",
                )

                onceki_denetim = self._review(
                    machine, transcript, budget, reviewer, plan, dosyalar, outcome, tur
                )
                if machine.state is not State.REJECTED:
                    return

                machine.fire(Event.REVISION_REQUESTED)
                if machine.state is State.LIMIT_EXCEEDED:
                    self._system(
                        transcript, tur, "ilerleme_yok",
                        "aynı red gerekçesi üst üste tekrarlandı",
                    )
                    return

    # -- adımlar ------------------------------------------------------------

    def _plan(
        self, machine, transcript, budget, planner: PlannerAgent, gorev_metni: str
    ) -> PlannerContent | None:
        hata = ""
        while machine.state is State.PLANNING:
            try:
                result = planner.run(planner.messages_for(gorev_metni, hata), tur=1)
            except AgentOutputError as exc:
                hata = str(exc)
                self._system(transcript, 1, "plan_sema_hatasi", f"{exc} | ham: {exc.ham}")
                machine.fire(Event.PLAN_SCHEMA_ERROR, Payload(detail=hata))
                continue

            self._emit(transcript, result.message)
            budget.add_usage(
                result.message.token_girdi,
                result.message.token_cikti,
                result.message.maliyet_usd,
            )
            plan: PlannerContent = result.icerik
            machine.fire(Event.PLAN_PRODUCED, Payload(plan=plan))

            if machine.state is State.OUT_OF_SCOPE:
                self._system(
                    transcript, 1, "kapsam_disi",
                    plan.override_reason or plan.uygulanabilirlik.gerekce,
                )
                return None
            return plan
        return None

    def _implement(
        self, machine, transcript, budget, implementer: ImplementerAgent,
        mcp: McpClient, plan, onceki_denetim, tur: int
    ) -> dict[str, str]:
        try:
            generated = implementer.generate(
                implementer.messages_for(plan, onceki_denetim)
            )
        except AgentOutputError as exc:
            self._system(transcript, tur, "uygulayici_sema_hatasi", f"{exc} | ham: {exc.ham}")
            machine.fire(Event.UNEXPECTED_ERROR, Payload(detail=str(exc)))
            return {}

        wire: ImplementerWire = generated.icerik
        mcp.calls.clear()
        yazilan: list[WrittenFile] = []

        for yol, icerik in wire.dosyalar.items():
            result = mcp.write_file(yol, icerik)
            if not result.ok:
                # Yol ihlali MCP sunucusunda yakalandı — kurtarma yok (G5).
                self._system(transcript, tur, "yol_ihlali", f"{yol}: {result.text}")
                machine.fire(Event.PATH_VIOLATION, Payload(detail=f"{yol}: {result.text}"))
                return {}
            yazilan.append(
                WrittenFile(
                    yol=yol,
                    bayt=len(icerik.encode("utf-8")),
                    hash=hashlib.sha256(icerik.encode("utf-8")).hexdigest()[:16],
                )
            )

        content = ImplementerContent(
            yazilan_dosyalar=yazilan,
            arac_cagrilari=list(mcp.calls),
            **{"not": wire.degisiklik_notu or None},
        )
        message = implementer.build_message(content, generated.response, tur)
        self._emit(transcript, message)
        budget.add_usage(message.token_girdi, message.token_cikti, message.maliyet_usd)

        machine.fire(
            Event.FILES_WRITTEN,
            Payload(written_file_count=len(yazilan), all_paths_inside_workspace=True),
        )
        return dict(wire.dosyalar)

    def _review(
        self, machine, transcript, budget, reviewer: ReviewerAgent,
        plan, dosyalar, outcome, tur: int
    ) -> ReviewerContent | None:
        hata = ""
        onceki_gerekce = (
            machine.context.rejection_reasons[-1]
            if machine.context.rejection_reasons
            else ""
        )

        while machine.state is State.REVIEWING:
            try:
                generated = reviewer.generate(
                    reviewer.messages_for(plan, dosyalar, outcome, onceki_gerekce, hata)
                )
            except AgentOutputError as exc:
                hata = str(exc)
                self._system(transcript, tur, "denetim_ayristirilamadi", f"{exc} | ham: {exc.ham}")
                machine.fire(Event.REVIEW_UNPARSABLE, Payload(detail=hata))
                continue

            # §7.4: beyan edilen test sonucu yerine ÖLÇÜLEN değer konur.
            # Mesaj bu yüzden `run()` ile değil, ölçüm uygulandıktan sonra
            # kurulur — transkripte giren kayıt ölçülen gerçeği taşımalı.
            review = with_measured_tests(generated.icerik, outcome)
            message = reviewer.build_message(review, generated.response, tur)
            self._emit(transcript, message)
            budget.add_usage(message.token_girdi, message.token_cikti, message.maliyet_usd)

            if review.override_reason:
                self._system(transcript, tur, "karar_gecersiz_kilindi", review.override_reason)

            temiz = self._secret_scan(transcript, dosyalar, tur)
            machine.fire(
                event_for_review(review),
                Payload(review=review, secret_scan_clean=temiz),
            )
            return review
        return None

    def _secret_scan(self, transcript: Transcript, dosyalar: dict[str, str], tur: int) -> bool:
        """Üretilen kodda sır var mı (T5, KK-06)."""
        findings = secret_scan.scan("\n".join(dosyalar.values()))
        if findings:
            self._system(
                transcript, tur, "sir_bulundu",
                ", ".join(sorted({f"{f.tur} ({f.maske})" for f in findings})),
            )
        return not findings
