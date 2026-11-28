"""Wire Adaptive Vocabulary into the unlocked Home / StudyMaster path.

Development integration only. Frozen installs keep the legacy quiz. Locked
ScreenGuard sessions keep VocabQuizApp. Practice rows stay in
practice_records.db and never write SRS or the sync outbox.

Activation requires LG_ADAPTIVE_STUDY=1 and a validated isolated LG_DATA_DIR.
Source runs without that opt-in stay on the classic Study route.

Target reconciliation: DailyStudyPlan.planned_vocab_count is the same N the
legacy lock session uses. Adaptive selection uses due/new candidates only (no
future-review fill). If fewer unique valid vocabulary ids are eligible than N,
Adaptive Study refuses and the required activity stays unresolved — use Legacy
Quiz. Recognition and assisted success never count toward completion.
"""

from __future__ import annotations

import os
import random
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

import config
from adaptive_vocabulary import (
    AdaptivePreviewRefused,
    AdaptiveSessionBridge,
    AdaptiveVocabularySession,
)
from practice_store import (
    PracticeStore,
    PracticeStoreError,
    load_history,
    open_account_store,
    open_guest_store,
    refuse_practice_data_root,
)
from study_data import StudyBundle, is_signed_in, open_study_data
from vocab_identity import entry_id


def _env_flag(name: str) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    return raw in ("1", "true", "yes", "y", "on")


def adaptive_opt_in_enabled() -> bool:
    """Explicit development opt-in. Source alone is not enough."""
    return _env_flag("LG_ADAPTIVE_STUDY")


def adaptive_data_root_allowed(data_root: str = None) -> tuple[bool, str]:
    """Require an explicit isolated LG_DATA_DIR that practice storage accepts."""
    explicit = (os.environ.get("LG_DATA_DIR") or "").strip()
    root = str(data_root if data_root is not None else explicit).strip()
    if not root:
        return False, "Adaptive Study needs LG_DATA_DIR set to an isolated data root."
    if not explicit:
        return False, "Adaptive Study needs LG_DATA_DIR set to an isolated data root."
    try:
        resolved = os.path.abspath(config.data_dir())
    except Exception as error:
        return False, str(error)
    if os.path.normcase(os.path.abspath(root)) != os.path.normcase(resolved):
        # Opt-in root must be the active data directory for this process.
        return False, "Adaptive Study data root must match the active LG_DATA_DIR."
    problem = refuse_practice_data_root(resolved)
    if problem:
        return False, problem
    try:
        from app_environment import assert_data_root_allowed

        assert_data_root_allowed(resolved)
    except Exception as error:
        return False, str(error)
    return True, resolved


def adaptive_integration_enabled() -> bool:
    """True only with explicit opt-in, isolated data root, and non-frozen runtime."""
    if config.is_frozen():
        return False
    if not adaptive_opt_in_enabled():
        return False
    ok, _detail = adaptive_data_root_allowed()
    return ok


def adaptive_unlocked_allowed(guard) -> bool:
    """Adaptive Vocabulary never opens under an active ScreenGuard lock."""
    if not adaptive_integration_enabled():
        return False
    if guard is None:
        return True
    locks = getattr(guard, "locks_the_user", None)
    if callable(locks) and locks():
        return False
    return True


@dataclass(frozen=True)
class AdaptiveStudyIdentity:
    """Account, language, data root, and session generation captured at open."""

    user_id: int
    language_code: str
    data_root: str
    signed_in: bool
    binding_id: str
    account_generation: int = 0

    def still_current(self, *, account_generation: int = None) -> bool:
        root = os.path.abspath(config.data_dir())
        if os.path.normcase(root) != os.path.normcase(self.data_root):
            return False
        code = str(config.active_code() or "").strip().lower()
        if code != self.language_code:
            return False
        signed = is_signed_in()
        if signed != self.signed_in:
            return False
        if signed and int(config.account_user_id() or 0) != int(self.user_id):
            return False
        if (not signed) and int(self.user_id) != 0:
            return False
        if account_generation is not None and int(account_generation) != int(
            self.account_generation
        ):
            return False
        return True


def capture_identity(
    language_code: str = None,
    *,
    data_root: str = None,
    account_generation: int = 0,
) -> AdaptiveStudyIdentity:
    code = str(language_code or config.active_code() or "").strip().lower()
    if data_root is None:
        raw_root = config.data_dir()
    else:
        raw_root = str(data_root).strip()
    root = os.path.abspath(raw_root) if raw_root else ""
    signed = is_signed_in()
    user_id = int(config.account_user_id() or 0) if signed else 0
    return AdaptiveStudyIdentity(
        user_id=user_id,
        language_code=code,
        data_root=root,
        signed_in=signed,
        binding_id=uuid.uuid4().hex,
        account_generation=int(account_generation or 0),
    )


@dataclass(frozen=True)
class PracticeAvailability:
    """ok = writable store; unavailable = failed open/history; disabled = intentionally off."""

    status: str
    store: Optional[PracticeStore] = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok" and self.store is not None

    @property
    def unavailable(self) -> bool:
        return self.status == "unavailable"


def open_practice_store(identity: AdaptiveStudyIdentity) -> PracticeStore:
    """Open the correct practice file for this account or guest language."""
    if not str(identity.data_root or "").strip():
        raise PracticeStoreError("practice store needs an explicit directory")
    if identity.signed_in:
        if identity.user_id <= 0:
            raise PracticeStoreError("signed-in practice store needs an account id")
        return open_account_store(identity.data_root, identity.user_id)
    return open_guest_store(identity.data_root, identity.language_code)


def open_sentence_skill_store(identity: AdaptiveStudyIdentity):
    """Open the separate sentence-skill store for this captured identity."""
    from sentence_skill_store import (
        SentenceSkillStoreError,
        open_account_sentence_skill_store,
        open_guest_sentence_skill_store,
    )

    if not str(identity.data_root or "").strip():
        raise SentenceSkillStoreError("sentence skill store needs an explicit directory")
    if identity.signed_in:
        if identity.user_id <= 0:
            raise SentenceSkillStoreError("signed-in sentence skill store needs an account id")
        return open_account_sentence_skill_store(identity.data_root, identity.user_id)
    return open_guest_sentence_skill_store(identity.data_root, identity.language_code)


def open_practice_availability(identity: AdaptiveStudyIdentity) -> PracticeAvailability:
    try:
        store = open_practice_store(identity)
    except PracticeStoreError as error:
        return PracticeAvailability(status="unavailable", detail=str(error or "practice store unavailable"))
    return PracticeAvailability(status="ok", store=store)


def select_due_new_entries(
    store,
    progress,
    limit: int,
    rng: random.Random,
    now: Optional[datetime] = None,
) -> list:
    """Due and new words only. No future-review fallback. Dedupes by stable vocab id."""
    from scheduler import _stats_for_entry
    from srs import ensure_utc, is_due, utc_now

    total = store.count() if store is not None else 0
    if total <= 0 or int(limit) <= 0:
        return []
    moment = ensure_utc(now or utc_now())
    due_indices = []
    for index in range(total):
        entry = store.get(index)
        if entry is None:
            continue
        vid = entry_id(entry)
        if not vid:
            continue
        stats = _stats_for_entry(progress, entry) if progress is not None else None
        if is_due(stats, moment):
            due_indices.append(index)
    ordered = list(due_indices)
    rng.shuffle(ordered)
    chosen = []
    seen = set()
    for index in ordered:
        if len(chosen) >= int(limit):
            break
        entry = store.get(index)
        if entry is None:
            continue
        vid = entry_id(entry)
        if not vid or vid in seen:
            continue
        seen.add(vid)
        chosen.append(entry)
    return chosen


@dataclass(frozen=True)
class IntegratedSessionBuild:
    """Result of building an adaptive session against the required planned count."""

    required_count: int
    selected_count: int
    session: Optional[AdaptiveVocabularySession] = None
    practice: PracticeAvailability = PracticeAvailability(status="disabled")
    refusal_reason: str = ""

    @property
    def ok(self) -> bool:
        return (
            self.session is not None
            and self.required_count > 0
            and self.selected_count == self.required_count
            and not self.refusal_reason
        )


def build_integrated_session(
    bundle: StudyBundle,
    *,
    planned_count: int,
    practice_store: Optional[PracticeStore] = None,
    practice: PracticeAvailability = None,
    rng: Optional[random.Random] = None,
    now=None,
) -> IntegratedSessionBuild:
    """Build one adaptive session only when eligible unique words equal planned_count."""
    rng = rng or random.Random()
    required = max(0, int(planned_count))
    availability = practice
    if availability is None:
        if practice_store is not None:
            availability = PracticeAvailability(status="ok", store=practice_store)
        else:
            availability = PracticeAvailability(status="disabled")

    planned = select_due_new_entries(
        bundle.vocab,
        bundle.progress,
        required,
        rng,
        now=now,
    )
    selected = len(planned)
    if required <= 0:
        return IntegratedSessionBuild(
            required_count=required,
            selected_count=0,
            practice=availability,
            refusal_reason="no_planned_target",
        )
    if selected != required:
        return IntegratedSessionBuild(
            required_count=required,
            selected_count=selected,
            practice=availability,
            refusal_reason="insufficient_eligible_words",
        )

    history: list = []
    history_error = ""
    store = availability.store if availability is not None else None
    if store is not None and availability.ok:
        try:
            history = load_history(
                store,
                [entry_id(entry) for entry in planned],
                bundle.language_code,
            )
        except PracticeStoreError as error:
            history = []
            history_error = str(error or "practice history unavailable")
            availability = PracticeAvailability(
                status="unavailable",
                store=store,
                detail=history_error,
            )
    progress_words = {}
    try:
        progress_words = dict(bundle.progress.data.get("words") or {})
    except Exception:
        progress_words = {}
    attempts = ()
    try:
        attempts = bundle.attempts.load_attempts()
    except Exception:
        attempts = ()
    pool = []
    try:
        pool = [bundle.vocab.get(index) for index in range(bundle.vocab.count())]
        pool = [entry for entry in pool if entry is not None and entry_id(entry)]
    except Exception:
        pool = list(planned)
    session = AdaptiveVocabularySession(
        planned,
        language_code=bundle.language_code,
        pool=pool or planned,
        progress_words=progress_words,
        attempts=attempts,
        practice_history=history,
        rng=rng,
        now=now,
    )
    # Session construction also drops invalid/duplicate ids; re-check equality.
    if int(session.counters.planned or 0) != required:
        return IntegratedSessionBuild(
            required_count=required,
            selected_count=int(session.counters.planned or 0),
            practice=availability,
            refusal_reason="insufficient_eligible_words",
        )
    return IntegratedSessionBuild(
        required_count=required,
        selected_count=required,
        session=session,
        practice=availability,
    )


def open_integrated_bundle(language_code: str = None, *, data_root: str = None) -> StudyBundle:
    return open_study_data(language_code, data_root=data_root)


def attach_bridge(study_session, controller: AdaptiveVocabularySession, *, locked: bool) -> AdaptiveSessionBridge:
    if locked:
        raise AdaptivePreviewRefused("Locked sessions stay on the legacy quiz.")
    return AdaptiveSessionBridge(study_session, controller, locked=False)


def incomplete_target_message(required: int, selected: int) -> tuple[str, str]:
    return (
        config.ui("Adaptive Study chưa đủ từ", "Adaptive Study needs more words"),
        config.ui(
            f"Hôm nay cần {required} từ độc lập, nhưng chỉ có {selected} từ đến hạn/mới "
            f"đủ điều kiện. Adaptive Study không giảm mục tiêu. "
            f"Dùng Legacy Quiz (Từ vựng) hoặc thêm từ / đợi đến hạn.",
            f"Today requires {required} independent words, but only {selected} due/new "
            f"eligible words are available. Adaptive Study does not reduce that target. "
            f"Use Legacy Quiz (Vocabulary) or add words / wait until more are due.",
        ),
    )


def practice_unavailable_message() -> str:
    return config.ui(
        "Không dùng được lịch sử luyện Adaptive. Câu trả lời tự nhớ vẫn được ghi.",
        "Adaptive practice history is unavailable. Independent answers are still recorded.",
    )


def production_practice_storage_requirements() -> tuple[str, ...]:
    """What a future release would need before writing practice rows in production AppData."""
    return (
        "An Architect-approved release that includes Adaptive Vocabulary in the installed Study button.",
        "An explicit product decision to allow practice_records.db under production AppData.",
        "Retention and account-deletion rules for practice rows.",
        "Additive sync design if practice events ever leave the device.",
        "No change that turns practice rows into SRS progress events.",
        "LG_ADAPTIVE_STUDY opt-in must not be the production activation mechanism.",
    )
