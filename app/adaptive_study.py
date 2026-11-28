"""Wire Adaptive Vocabulary into the unlocked Home / StudyMaster path.

This is development integration only. Frozen installs keep the legacy quiz.
Locked ScreenGuard sessions keep VocabQuizApp. Practice rows stay in
practice_records.db and never write SRS or the sync outbox.

Target reconciliation: DailyStudyPlan.planned_vocab_count is the same N the
legacy lock session uses (min(vocab_total, QUIZ_TARGET_CORRECT)). Adaptive
completion still requires independent exact or near on up to N distinct planned
words. Recognition and assisted success do not count. That is not a reduced
target; it is a stricter unique-word rule for the same planned count.
"""

from __future__ import annotations

import os
import random
import uuid
from dataclasses import dataclass
from typing import Optional, Sequence

import config
from adaptive_vocabulary import (
    AdaptivePreviewRefused,
    AdaptiveSessionBridge,
    AdaptiveVocabularySession,
    select_planned_entries,
)
from practice_store import (
    PracticeStore,
    PracticeStoreError,
    load_history,
    open_account_store,
    open_guest_store,
)
from study_data import StudyBundle, is_signed_in, open_study_data


def adaptive_integration_enabled() -> bool:
    """True only for unlocked development source. Installed builds stay classic."""
    if config.is_frozen():
        return False
    return True


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
    """Account, language, and data root captured when the window opens."""

    user_id: int
    language_code: str
    data_root: str
    signed_in: bool
    binding_id: str

    def still_current(self) -> bool:
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
        return True


def capture_identity(language_code: str = None, *, data_root: str = None) -> AdaptiveStudyIdentity:
    code = str(language_code or config.active_code() or "").strip().lower()
    root = os.path.abspath(str(data_root if data_root is not None else config.data_dir()))
    signed = is_signed_in()
    user_id = int(config.account_user_id() or 0) if signed else 0
    return AdaptiveStudyIdentity(
        user_id=user_id,
        language_code=code,
        data_root=root,
        signed_in=signed,
        binding_id=uuid.uuid4().hex,
    )


def open_practice_store(identity: AdaptiveStudyIdentity) -> PracticeStore:
    """Open the correct practice file for this account or guest language."""
    if not str(identity.data_root or "").strip():
        raise PracticeStoreError("practice store needs an explicit directory")
    if identity.signed_in:
        if identity.user_id <= 0:
            raise PracticeStoreError("signed-in practice store needs an account id")
        return open_account_store(identity.data_root, identity.user_id)
    return open_guest_store(identity.data_root, identity.language_code)


def build_integrated_session(
    bundle: StudyBundle,
    *,
    planned_count: int,
    practice_store: Optional[PracticeStore] = None,
    rng: Optional[random.Random] = None,
    now=None,
) -> AdaptiveVocabularySession:
    """Build one adaptive session from the live StudyBundle and practice history."""
    rng = rng or random.Random()
    planned = select_planned_entries(
        bundle.vocab,
        bundle.progress,
        max(0, int(planned_count)),
        rng,
        now=now,
    )
    history: list = []
    if practice_store is not None:
        try:
            history = load_history(
                practice_store,
                [str(entry.get("id") or "") for entry in planned],
                bundle.language_code,
            )
        except PracticeStoreError:
            history = []
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
        pool = [entry for entry in pool if entry is not None]
    except Exception:
        pool = list(planned)
    return AdaptiveVocabularySession(
        planned,
        language_code=bundle.language_code,
        pool=pool or planned,
        progress_words=progress_words,
        attempts=attempts,
        practice_history=history,
        rng=rng,
        now=now,
    )


def open_integrated_bundle(language_code: str = None, *, data_root: str = None) -> StudyBundle:
    return open_study_data(language_code, data_root=data_root)


def attach_bridge(study_session, controller: AdaptiveVocabularySession, *, locked: bool) -> AdaptiveSessionBridge:
    if locked:
        raise AdaptivePreviewRefused("Locked sessions stay on the legacy quiz.")
    return AdaptiveSessionBridge(study_session, controller, locked=False)


def production_practice_storage_requirements() -> tuple[str, ...]:
    """What a future release would need before writing practice rows in production AppData."""
    return (
        "An Architect-approved release that includes Adaptive Vocabulary in the installed Study button.",
        "An explicit product decision to allow practice_records.db under production AppData.",
        "Retention and account-deletion rules for practice rows.",
        "Additive sync design if practice events ever leave the device.",
        "No change that turns practice rows into SRS progress events.",
    )
