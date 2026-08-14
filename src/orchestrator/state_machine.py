"""Durum makinesi — PROJECT.md §4.

Saf: LLM çağrısı, disk erişimi, saat okuması yoktur. Tek işi bir olayı alıp
koruma koşullarını değerlendirmek ve hedef durumu döndürmektir. Yan etkiler
(dosya yazma, ağ) çağıran katmana aittir; böylece 13 geçişin tamamı
saniyeler içinde ve deterministik olarak sınanabilir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Callable

from src.orchestrator.limits import LIMITS, Limits
from src.transcript.models import (
    Decision,
    FeasibilityVerdict,
    PlannerContent,
    ReviewerContent,
)


# Türkçe küçük harf kuralı: noktalı I küçükken noktasız, noktasız I ise 'ı'
# olur. Kalan harfleri (Ş, Ğ, Ü, Ö, Ç) standart lower() doğru çevirir.
_TR_LOWER = str.maketrans({"İ": "i", "I": "ı"})


class State(str, Enum):
    PLANNING = "PLANLANIYOR"
    IMPLEMENTING = "UYGULANIYOR"
    REVIEWING = "DENETLENIYOR"
    REJECTED = "REDDEDILDI"
    ACCEPTED = "KABUL_EDILDI"
    OUT_OF_SCOPE = "KAPSAM_DISI"
    LIMIT_EXCEEDED = "LIMIT_ASILDI"
    ERROR = "HATA"


TERMINAL_STATES = frozenset(
    {State.ACCEPTED, State.OUT_OF_SCOPE, State.LIMIT_EXCEEDED, State.ERROR}
)


class Event(str, Enum):
    TASK_RECEIVED = "gorev_alindi"
    PLAN_PRODUCED = "plan_uretildi"
    PLAN_SCHEMA_ERROR = "plan_sema_hatasi"
    FILES_WRITTEN = "dosyalar_yazildi"
    PATH_VIOLATION = "yol_ihlali"
    REVIEW_ACCEPTED = "denetim_kabul"
    REVIEW_REJECTED = "denetim_red"
    REVIEW_UNPARSABLE = "denetim_ayristirilamadi"
    REVISION_REQUESTED = "revizyon_istendi"
    LIMIT_HIT = "limit_asildi"
    UNEXPECTED_ERROR = "beklenmeyen_hata"


class IllegalTransition(RuntimeError):
    """Tanımsız (durum, olay) çifti. Sessizce yutulmaz: bir kodlama hatasıdır."""


@dataclass(frozen=True)
class Payload:
    """Olayla birlikte gelen, koruma koşullarının okuduğu veri."""

    plan: PlannerContent | None = None
    written_file_count: int = 0
    all_paths_inside_workspace: bool = True
    review: ReviewerContent | None = None
    secret_scan_clean: bool = True
    limit_name: str = ""
    detail: str = ""


@dataclass
class RunContext:
    """Bir görevin çalışma boyunca biriken sayaçları."""

    limits: Limits = field(default_factory=lambda: LIMITS)
    task_text: str = ""
    turn: int = 0
    plan_schema_errors: int = 0
    review_parse_errors: int = 0
    rejection_reasons: list[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: Decimal = Decimal("0")
    last_limit_hit: str = ""
    last_error: str = ""
    refusal_reason: str = ""
    refused_game: str = ""

    # -- ilerleme tespiti ---------------------------------------------------

    @staticmethod
    def normalize_reason(reason: str) -> str:
        """Karşılaştırma için gerekçeyi sadeleştirir.

        Küçük harfe indirir ve boşlukları tekilleştirir. Kasıtlı olarak daha
        ileri gitmez: eş anlamlı ama farklı yazılmış iki gerekçe "ilerleme"
        sayılır. Yanlış pozitif (erken durdurma) yanlış negatiften (sonsuz
        döngü) daha zararlıdır; asıl tavan yine de MAX_TUR'dur.

        Türkçe I/İ kuralı önce uygulanır: Python'un `lower()` metodu 'İ'yi
        'i' + birleşik nokta (U+0307) olarak açar, bu yüzden "EKSİK".lower()
        ile "eksik" EŞİT DEĞİLDİR. Gerekçeler Türkçe olduğundan bu, aynı
        gerekçenin farklı yazımını "yeni gerekçe" sayarak ilerleme-yok
        korumasını sessizce devre dışı bırakırdı.
        """
        return re.sub(r"\s+", " ", reason.translate(_TR_LOWER).lower().strip())

    @property
    def no_progress(self) -> bool:
        """Son N red gerekçesi birbirinin aynıysa ilerleme yok demektir."""
        threshold = self.limits.no_progress_threshold
        if len(self.rejection_reasons) < threshold:
            return False
        recent = [self.normalize_reason(r) for r in self.rejection_reasons[-threshold:]]
        return len(set(recent)) == 1


@dataclass(frozen=True)
class TransitionResult:
    source: State
    event: Event
    target: State
    rule: str
    note: str = ""


Guard = Callable[[RunContext, Payload], bool]
Effect = Callable[[RunContext, Payload], None]


@dataclass(frozen=True)
class Transition:
    rule: str
    source: State | None  # None = yalnızca başlangıçtan (henüz durum yok)
    event: Event
    target: State
    guard: Guard = lambda ctx, p: True
    effect: Effect | None = None
    note: str = ""
    any_source: bool = False  # True = herhangi bir son-olmayan durumdan


# --------------------------------------------------------------------------
# Koruma koşulları — §4.2'deki tabloyla birebir
# --------------------------------------------------------------------------


def _task_valid(ctx: RunContext, p: Payload) -> bool:
    text = ctx.task_text.strip()
    return bool(text) and len(text) <= ctx.limits.max_task_chars


def _plan_usable(ctx: RunContext, p: Payload) -> bool:
    return (
        p.plan is not None
        and p.plan.effective_verdict is FeasibilityVerdict.UYGUN
        and len(p.plan.kabul_kriterleri) >= 1
    )


def _plan_refused(ctx: RunContext, p: Payload) -> bool:
    return (
        p.plan is not None
        and p.plan.effective_verdict is FeasibilityVerdict.UYGUN_DEGIL
    )


def _schema_retries_left(ctx: RunContext, p: Payload) -> bool:
    return ctx.plan_schema_errors + 1 < 2


def _files_ok(ctx: RunContext, p: Payload) -> bool:
    return p.written_file_count >= 1 and p.all_paths_inside_workspace


def _accepted_and_clean(ctx: RunContext, p: Payload) -> bool:
    return (
        p.review is not None
        and p.review.effective_decision is Decision.KABUL
        and p.secret_scan_clean
    )


def _accepted_but_secret_found(ctx: RunContext, p: Payload) -> bool:
    return (
        p.review is not None
        and p.review.effective_decision is Decision.KABUL
        and not p.secret_scan_clean
    )


def _turns_left(ctx: RunContext, p: Payload) -> bool:
    return ctx.turn < ctx.limits.max_turns


def _parse_retries_left(ctx: RunContext, p: Payload) -> bool:
    return ctx.review_parse_errors + 1 < 2


def _progressing(ctx: RunContext, p: Payload) -> bool:
    return not ctx.no_progress


def _stalled(ctx: RunContext, p: Payload) -> bool:
    return ctx.no_progress


# --------------------------------------------------------------------------
# Etkiler
# --------------------------------------------------------------------------


def _start_first_turn(ctx: RunContext, p: Payload) -> None:
    ctx.turn = 1


def _count_schema_error(ctx: RunContext, p: Payload) -> None:
    ctx.plan_schema_errors += 1


def _count_parse_error(ctx: RunContext, p: Payload) -> None:
    ctx.review_parse_errors += 1


def _record_rejection(ctx: RunContext, p: Payload) -> None:
    if p.review is None:
        ctx.rejection_reasons.append(p.detail)
        return
    # Karar geçersiz kılındıysa kaydedilecek gerekçe denetleyicinin kabul
    # metni değil, geçersiz kılma nedenidir.
    ctx.rejection_reasons.append(p.review.override_reason or p.review.gerekce)


def _record_secret_rejection(ctx: RunContext, p: Payload) -> None:
    ctx.rejection_reasons.append("sır taraması bulgu verdi")


def _next_turn(ctx: RunContext, p: Payload) -> None:
    ctx.turn += 1


def _record_refusal(ctx: RunContext, p: Payload) -> None:
    if p.plan is None:
        return
    ctx.refusal_reason = p.plan.override_reason or p.plan.uygulanabilirlik.gerekce
    ctx.refused_game = p.plan.oyun


def _record_limit(ctx: RunContext, p: Payload) -> None:
    ctx.last_limit_hit = p.limit_name or p.detail


def _record_error(ctx: RunContext, p: Payload) -> None:
    ctx.last_error = p.detail


def _record_path_violation(ctx: RunContext, p: Payload) -> None:
    ctx.last_error = p.detail or "workspace dışına yazma girişimi"


# --------------------------------------------------------------------------
# Geçiş tablosu
#
# Sıra anlamlıdır: aynı (durum, olay) için ilk koruma koşulu geçen kazanır.
# Bu yüzden dar koşullar geniş olanlardan önce yazılmıştır.
# --------------------------------------------------------------------------

TRANSITIONS: tuple[Transition, ...] = (
    Transition("G1", None, Event.TASK_RECEIVED, State.PLANNING,
               _task_valid, _start_first_turn,
               "görev metni boş değil ve sınır içinde"),

    Transition("G2", State.PLANNING, Event.PLAN_PRODUCED, State.IMPLEMENTING,
               _plan_usable, None,
               "uygulanabilir bulundu, en az bir kabul kriteri var"),

    # Gerekçeli ret bir hata değildir. Kendi son durumu vardır ki
    # "sistem çöktü" ile "sistem değerlendirdi ve yapmadı" karışmasın.
    Transition("G2k", State.PLANNING, Event.PLAN_PRODUCED, State.OUT_OF_SCOPE,
               _plan_refused, _record_refusal,
               "uygulanabilirlik ölçütünü geçemedi — gerekçeli ret"),

    # G3'ün "2. kez" ifadesi bir yeniden deneme hakkı olduğunu ima eder ama
    # tabloda ilk denemenin geçişi yazılı değildi; G3r bu boşluğu kapatır.
    Transition("G3r", State.PLANNING, Event.PLAN_SCHEMA_ERROR, State.PLANNING,
               _schema_retries_left, _count_schema_error,
               "ilk şema hatası — planlayıcı yeniden denenir"),
    Transition("G3", State.PLANNING, Event.PLAN_SCHEMA_ERROR, State.ERROR,
               effect=_count_schema_error,
               note="ikinci şema hatası — yeniden deneme hakkı tükendi"),

    Transition("G4", State.IMPLEMENTING, Event.FILES_WRITTEN, State.REVIEWING,
               _files_ok, None,
               "en az bir dosya yazıldı, tüm yollar workspace içinde"),

    Transition("G5", State.IMPLEMENTING, Event.PATH_VIOLATION, State.ERROR,
               effect=_record_path_violation,
               note="sandbox politikası ihlali — kurtarma yok"),

    Transition("G6", State.REVIEWING, Event.REVIEW_ACCEPTED, State.ACCEPTED,
               _accepted_and_clean, None,
               "testler geçti ve sır taraması temiz"),

    # KK-06: KABUL geldiği hâlde sır bulunduysa kabul geçersizdir ve bu bir
    # hata değil, bir RED turudur. §4.2 tablosunda bu dal yazılı değildi.
    Transition("G6s", State.REVIEWING, Event.REVIEW_ACCEPTED, State.REJECTED,
               _accepted_but_secret_found, _record_secret_rejection,
               "KABUL geldi ama sır taraması bulgu verdi — kabul geçersiz"),

    Transition("G7", State.REVIEWING, Event.REVIEW_REJECTED, State.REJECTED,
               _turns_left, _record_rejection,
               "red alındı, tur hakkı var"),
    Transition("G8", State.REVIEWING, Event.REVIEW_REJECTED, State.LIMIT_EXCEEDED,
               effect=_record_rejection,
               note="red alındı, tur tavanı doldu"),

    Transition("G9r", State.REVIEWING, Event.REVIEW_UNPARSABLE, State.REVIEWING,
               _parse_retries_left, _count_parse_error,
               "ilk ayrıştırma hatası — denetleyici yeniden denenir"),
    Transition("G9", State.REVIEWING, Event.REVIEW_UNPARSABLE, State.ERROR,
               effect=_count_parse_error,
               note="yapısal JSON dönmedi — karar KABUL sayılmaz"),

    Transition("G10", State.REJECTED, Event.REVISION_REQUESTED, State.IMPLEMENTING,
               _progressing, _next_turn,
               "red gerekçesi yeni — revizyon turu başlar"),
    Transition("G11", State.REJECTED, Event.REVISION_REQUESTED, State.LIMIT_EXCEEDED,
               _stalled, None,
               "aynı gerekçe üst üste tekrarladı — ilerleme yok"),

    Transition("G12", None, Event.LIMIT_HIT, State.LIMIT_EXCEEDED,
               effect=_record_limit, any_source=True,
               note="token/süre/maliyet tavanı doldu"),
    Transition("G13", None, Event.UNEXPECTED_ERROR, State.ERROR,
               effect=_record_error, any_source=True,
               note="kurtarılamayan istisna"),
)


def event_for_review(review: ReviewerContent) -> Event:
    """Denetleyici içeriğinden olayı türetir.

    Çağıranın `karar` alanına doğrudan bakması yasaktır. §7.4 iş kuralı
    (KABUL + başarısız test = RED) burada, tek noktada uygulanır; aksi
    hâlde kuralı uygulamayı unutan bir çağrı yeri T4'ü yeniden açar.
    """
    if review.effective_decision is Decision.KABUL:
        return Event.REVIEW_ACCEPTED
    return Event.REVIEW_REJECTED


class StateMachine:
    def __init__(self, context: RunContext | None = None) -> None:
        self.context = context if context is not None else RunContext()
        self.state: State | None = None
        self.history: list[TransitionResult] = []

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def fire(self, event: Event, payload: Payload | None = None) -> TransitionResult:
        payload = payload or Payload()

        if self.is_terminal:
            raise IllegalTransition(
                f"{self.state.value} bir son durumdur; '{event.value}' işlenemez"
            )

        for transition in TRANSITIONS:
            if transition.event is not event:
                continue
            if not transition.any_source and transition.source is not self.state:
                continue
            if not transition.guard(self.context, payload):
                continue

            if transition.effect is not None:
                transition.effect(self.context, payload)

            result = TransitionResult(
                source=self.state if self.state is not None else State.PLANNING,
                event=event,
                target=transition.target,
                rule=transition.rule,
                note=transition.note,
            )
            self.state = transition.target
            self.history.append(result)
            return result

        current = self.state.value if self.state else "(başlangıç)"
        raise IllegalTransition(
            f"'{current}' durumunda '{event.value}' olayı için geçiş tanımlı değil "
            f"veya hiçbir koruma koşulu sağlanmadı"
        )

    # -- raporlama ----------------------------------------------------------

    def final_report(self) -> dict[str, object]:
        """§4.2: hiçbir son durum sessizce sonlanmaz.

        Hangi kuralla, hangi turda durulduğu ve gerekçesi yazılır.
        """
        if not self.is_terminal:
            raise RuntimeError("son duruma ulaşılmadan rapor üretilemez")

        last = self.history[-1]
        ctx = self.context
        report: dict[str, object] = {
            "son_durum": self.state.value,
            "uygulanan_kural": last.rule,
            "gerekce": last.note,
            "tur": ctx.turn,
            "tur_tavani": ctx.limits.max_turns,
            "toplam_gecis": len(self.history),
        }
        if self.state is State.LIMIT_EXCEEDED:
            report["dolan_limit"] = ctx.last_limit_hit or (
                "ilerleme yok" if ctx.no_progress else "tur tavanı"
            )
            report["son_red_gerekcesi"] = (
                ctx.rejection_reasons[-1] if ctx.rejection_reasons else ""
            )
        if self.state is State.ERROR:
            report["hata"] = ctx.last_error
        if self.state is State.OUT_OF_SCOPE:
            report["oyun"] = ctx.refused_game
            report["ret_gerekcesi"] = ctx.refusal_reason
        return report
