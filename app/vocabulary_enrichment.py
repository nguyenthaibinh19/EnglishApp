"""Vocabulary enrichment draft / review / apply (Phase 15B).

Architecture:

    VocabularyEntry
          ↓
    EnrichmentService
          ↓
    VocabularyEnrichmentProvider
          ↓
    EnrichmentDraft   (ephemeral — never auto-persisted)
          ↓
    review / select / edit
          ↓
    apply_enrichment(...)
          ↓
    VocabularyEntry  (via VocabStore.update)

External enrichment must never silently overwrite canonical vocabulary data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from vocabulary_model import (
    FORM_FIELDS,
    GrammaticalForms,
    PronunciationInfo,
    VocabularyExample,
    entry_examples,
    entry_forms,
    entry_part_of_speech,
    entry_pronunciation,
    normalize_examples,
    normalize_forms,
    normalize_part_of_speech,
    normalize_pronunciation,
)

# Lightweight draft provenance — not persisted on VocabularyEntry.
ENRICHMENT_SOURCES = frozenset(
    {"dictionary", "language_rule", "ai", "manual", "test"}
)


class EnrichmentError(RuntimeError):
    """Provider/network/AI failure surfaced to UI; never mutates vocabulary."""


@dataclass(frozen=True)
class EnrichmentRequest:
    """Domain-only request for an enrichment provider."""

    vocab_id: str
    word: str
    meaning: str
    study_language: str
    native_language: str = ""
    part_of_speech: str = ""


@dataclass(frozen=True)
class EnrichmentDraft:
    """Uncommitted enrichment suggestions. Missing fields = no suggestion."""

    part_of_speech: Optional[str] = None
    forms: Optional[GrammaticalForms] = None
    pronunciation: Optional[PronunciationInfo] = None
    examples: Optional[Tuple[VocabularyExample, ...]] = None
    source: str = "manual"

    def has_suggestions(self) -> bool:
        if self.part_of_speech:
            return True
        if self.pronunciation and self.pronunciation.ipa:
            return True
        if self.forms and self.forms.to_storage_dict():
            return True
        if self.examples:
            return True
        return False


@dataclass(frozen=True)
class EnrichmentApplySelection:
    """Explicit learner choices for what to commit from a draft."""

    apply_part_of_speech: bool = False
    apply_pronunciation: bool = False
    form_keys: Tuple[str, ...] = ()
    example_indices: Tuple[int, ...] = ()
    # Optional in-review edits (override draft values when applying).
    edited_part_of_speech: Optional[str] = None
    edited_ipa: Optional[str] = None
    edited_forms: Optional[Dict[str, str]] = None
    edited_examples: Optional[Dict[int, VocabularyExample]] = None


@dataclass(frozen=True)
class FieldReviewItem:
    """One comparable enrichment area for the review UI."""

    key: str
    label: str
    current: str
    suggested: str
    selected: bool = True
    editable: bool = True
    # For forms: the form field name; for examples: draft index as str.
    target: str = ""


@dataclass(frozen=True)
class EnrichmentReviewState:
    """Pure view-model: current vs suggested, selection flags."""

    source: str
    part_of_speech: Optional[FieldReviewItem] = None
    pronunciation: Optional[FieldReviewItem] = None
    forms: Tuple[FieldReviewItem, ...] = ()
    examples: Tuple[FieldReviewItem, ...] = ()

    def visible_items(self) -> List[FieldReviewItem]:
        items: List[FieldReviewItem] = []
        if self.part_of_speech is not None:
            items.append(self.part_of_speech)
        if self.pronunciation is not None:
            items.append(self.pronunciation)
        items.extend(self.forms)
        items.extend(self.examples)
        return items

    def with_selection(self, key: str, selected: bool) -> "EnrichmentReviewState":
        def _item(item: Optional[FieldReviewItem]) -> Optional[FieldReviewItem]:
            if item is None or item.key != key:
                return item
            return replace(item, selected=selected)

        return EnrichmentReviewState(
            source=self.source,
            part_of_speech=_item(self.part_of_speech),
            pronunciation=_item(self.pronunciation),
            forms=tuple(_item(item) or item for item in self.forms),
            examples=tuple(_item(item) or item for item in self.examples),
        )

    def with_suggested(self, key: str, suggested: str) -> "EnrichmentReviewState":
        def _item(item: Optional[FieldReviewItem]) -> Optional[FieldReviewItem]:
            if item is None or item.key != key:
                return item
            return replace(item, suggested=suggested)

        return EnrichmentReviewState(
            source=self.source,
            part_of_speech=_item(self.part_of_speech),
            pronunciation=_item(self.pronunciation),
            forms=tuple(_item(item) or item for item in self.forms),
            examples=tuple(_item(item) or item for item in self.examples),
        )

    def to_selection(self) -> EnrichmentApplySelection:
        apply_pos = bool(self.part_of_speech and self.part_of_speech.selected)
        apply_ipa = bool(self.pronunciation and self.pronunciation.selected)
        form_keys = tuple(
            item.target for item in self.forms if item.selected and item.target
        )
        example_indices = tuple(
            int(item.target)
            for item in self.examples
            if item.selected and str(item.target).isdigit()
        )
        edited_pos = (
            self.part_of_speech.suggested.strip()
            if self.part_of_speech is not None
            else None
        )
        edited_ipa = (
            self.pronunciation.suggested.strip()
            if self.pronunciation is not None
            else None
        )
        edited_forms = {
            item.target: item.suggested.strip()
            for item in self.forms
            if item.target
        }
        edited_examples: Dict[int, VocabularyExample] = {}
        for item in self.examples:
            if not str(item.target).isdigit():
                continue
            idx = int(item.target)
            text = item.suggested.strip()
            if text:
                edited_examples[idx] = VocabularyExample(text=text)
        return EnrichmentApplySelection(
            apply_part_of_speech=apply_pos,
            apply_pronunciation=apply_ipa,
            form_keys=form_keys,
            example_indices=example_indices,
            edited_part_of_speech=edited_pos,
            edited_ipa=edited_ipa,
            edited_forms=edited_forms or None,
            edited_examples=edited_examples or None,
        )


class VocabularyEnrichmentProvider(ABC):
    """Boundary for enrichment sources (dictionary / rules / AI later)."""

    @abstractmethod
    def enrich(self, request: EnrichmentRequest) -> EnrichmentDraft:
        raise NotImplementedError


class FakeEnrichmentProvider(VocabularyEnrichmentProvider):
    """Deterministic provider for tests / optional local verification only."""

    def __init__(self, draft: Optional[EnrichmentDraft] = None):
        self._draft = draft
        self.calls: List[EnrichmentRequest] = []

    def enrich(self, request: EnrichmentRequest) -> EnrichmentDraft:
        self.calls.append(request)
        if self._draft is not None:
            return self._draft
        return EnrichmentDraft(
            part_of_speech="noun",
            forms=GrammaticalForms(plural=f"{request.word}s"),
            pronunciation=PronunciationInfo(ipa="test"),
            examples=(
                VocabularyExample(
                    text=f"Example with {request.word}.",
                    meaning=request.meaning,
                ),
            ),
            source="test",
        )


def draft_from_ai_result(result: Any, *, source: str = "ai") -> EnrichmentDraft:
    """Map validated AI enrichment result → ephemeral EnrichmentDraft (no IPA)."""
    from ai.base import VocabularyEnrichmentAIResult, sanitize_enrichment_ai_payload

    if isinstance(result, VocabularyEnrichmentAIResult):
        payload = result.as_dict()
    elif isinstance(result, dict):
        payload = sanitize_enrichment_ai_payload(result).as_dict()
    else:
        raise EnrichmentError("Invalid enrichment AI result.")

    pos = payload.get("part_of_speech") or None
    forms_data = payload.get("forms")
    forms = normalize_forms(forms_data) if forms_data else None
    if forms and not forms.to_storage_dict():
        forms = None
    examples_data = payload.get("examples")
    examples = tuple(normalize_examples(examples_data)) if examples_data else None
    return normalize_draft(
        EnrichmentDraft(
            part_of_speech=pos,
            forms=forms,
            pronunciation=None,
            examples=examples or None,
            source=source,
        )
    )


class AccountServerVocabularyEnrichmentProvider(VocabularyEnrichmentProvider):
    """Production enrichment: desktop → account server → AIService → OpenAI.

    Never embeds or receives the production OpenAI API key.
    Dev machines with a local `.env` key use AIService → OpenAIProvider directly
    when ``uses_account_server()`` is false (same pattern as grade/reading).
    """

    def enrich(self, request: EnrichmentRequest) -> EnrichmentDraft:
        import config
        from ai.base import AIError, sanitize_enrichment_ai_payload
        from ai.service import get_service
        import languages

        try:
            if config.uses_account_server():
                import account_client

                data = account_client.enrich_vocabulary(
                    request.word,
                    request.meaning,
                    part_of_speech=request.part_of_speech or "",
                    language_code=request.study_language,
                    native_language=request.native_language,
                )
                result = sanitize_enrichment_ai_payload(data)
            else:
                lang = languages.resolve_language(request.study_language)
                native_label = (
                    "English"
                    if str(request.native_language or "").lower() == "en"
                    else "Tiếng Việt"
                )
                result = get_service().enrich_vocabulary(
                    request.word,
                    request.meaning,
                    part_of_speech=request.part_of_speech or "",
                    profile=lang.as_profile(include_code=True),
                    native_label=native_label,
                    use_account_proxy=False,
                )
        except AIError as error:
            raise EnrichmentError(str(error)) from error
        except Exception as error:  # noqa: BLE001 - surface as EnrichmentError
            # account_client.AccountError is covered here when not subclassed above.
            raise EnrichmentError(str(error)) from error
        return draft_from_ai_result(result, source="ai")


def resolve_production_enrichment_provider() -> Optional[VocabularyEnrichmentProvider]:
    """Return production AI enrichment provider when AI is configured; else None."""
    import config

    if not config.ai_is_configured():
        return None
    return AccountServerVocabularyEnrichmentProvider()


def normalize_draft(draft: EnrichmentDraft) -> EnrichmentDraft:
    """Validate/normalize draft structures; drop empty suggestions."""
    source = str(draft.source or "manual").strip() or "manual"
    if source not in ENRICHMENT_SOURCES:
        source = "manual"

    pos = None
    if draft.part_of_speech is not None:
        cleaned = normalize_part_of_speech(draft.part_of_speech)
        pos = cleaned or None

    forms = None
    if draft.forms is not None:
        normalized = normalize_forms(draft.forms.as_dict() if hasattr(draft.forms, "as_dict") else draft.forms)
        if normalized.to_storage_dict():
            forms = normalized

    pronunciation = None
    if draft.pronunciation is not None:
        info = normalize_pronunciation(
            draft.pronunciation.to_storage_dict()
            if hasattr(draft.pronunciation, "to_storage_dict")
            else draft.pronunciation
        )
        if info.ipa:
            pronunciation = info

    examples = None
    if draft.examples is not None:
        normalized_examples = tuple(normalize_examples(list(draft.examples)))
        examples = normalized_examples or None

    return EnrichmentDraft(
        part_of_speech=pos,
        forms=forms,
        pronunciation=pronunciation,
        examples=examples,
        source=source,
    )


def _example_key(example: VocabularyExample) -> Tuple[str, str]:
    return (example.text.casefold(), (example.meaning or "").casefold())


def apply_enrichment(
    entry: dict,
    draft: EnrichmentDraft,
    selection: EnrichmentApplySelection,
) -> Dict[str, Any]:
    """Merge selected draft values into update kwargs for VocabStore.

    Missing draft fields never clear canonical data.
    Clearing existing data via enrichment is not supported in Phase 15B.
    """
    draft = normalize_draft(draft)
    updates: Dict[str, Any] = {}

    if selection.apply_part_of_speech:
        pos = selection.edited_part_of_speech
        if pos is None:
            pos = draft.part_of_speech
        if pos:
            updates["part_of_speech"] = normalize_part_of_speech(pos)

    if selection.apply_pronunciation:
        ipa = selection.edited_ipa
        if ipa is None and draft.pronunciation is not None:
            ipa = draft.pronunciation.ipa
        ipa = str(ipa or "").strip()
        if ipa:
            updates["pronunciation"] = {"ipa": ipa}

    form_keys = tuple(
        key for key in selection.form_keys if key in FORM_FIELDS
    )
    if form_keys:
        merged = entry_forms(entry).as_dict()
        draft_forms = draft.forms.as_dict() if draft.forms else {}
        edits = selection.edited_forms or {}
        for key in form_keys:
            value = str(edits.get(key) or draft_forms.get(key) or "").strip()
            if value:
                merged[key] = value
        if merged:
            updates["forms"] = merged

    if selection.example_indices:
        existing = list(entry_examples(entry))
        draft_examples = list(draft.examples or ())
        seen = {_example_key(item) for item in existing}
        edits = selection.edited_examples or {}
        for index in selection.example_indices:
            if index in edits:
                candidate = edits[index]
            elif 0 <= index < len(draft_examples):
                candidate = draft_examples[index]
            else:
                continue
            if not candidate or not str(candidate.text or "").strip():
                continue
            normalized = VocabularyExample(
                text=str(candidate.text).strip(),
                meaning=str(getattr(candidate, "meaning", "") or "").strip(),
            )
            key = _example_key(normalized)
            if key in seen:
                continue
            existing.append(normalized)
            seen.add(key)
        updates["examples"] = [item.to_storage_dict() for item in existing]

    return updates


def build_review_state(
    entry: dict,
    draft: EnrichmentDraft,
    *,
    form_labels: Optional[Dict[str, str]] = None,
) -> EnrichmentReviewState:
    """Build current-vs-suggested review items for present draft suggestions only."""
    draft = normalize_draft(draft)
    labels = form_labels or {
        "plural": "Plural",
        "past": "Past",
        "past_participle": "Past participle",
        "comparative": "Comparative",
        "superlative": "Superlative",
    }

    pos_item = None
    if draft.part_of_speech:
        pos_item = FieldReviewItem(
            key="part_of_speech",
            label="Part of speech",
            current=entry_part_of_speech(entry) or "—",
            suggested=draft.part_of_speech,
            selected=True,
            target="part_of_speech",
        )

    ipa_item = None
    if draft.pronunciation and draft.pronunciation.ipa:
        current_ipa = entry_pronunciation(entry).ipa
        ipa_item = FieldReviewItem(
            key="pronunciation",
            label="Pronunciation (IPA)",
            current=f"/{current_ipa}/" if current_ipa else "—",
            suggested=draft.pronunciation.ipa,
            selected=True,
            target="ipa",
        )

    form_items: List[FieldReviewItem] = []
    draft_forms = draft.forms.as_dict() if draft.forms else {}
    existing_forms = entry_forms(entry).as_dict()
    for name in FORM_FIELDS:
        if name not in draft_forms:
            continue
        form_items.append(
            FieldReviewItem(
                key=f"form:{name}",
                label=labels.get(name, name),
                current=existing_forms.get(name) or "—",
                suggested=draft_forms[name],
                selected=True,
                target=name,
            )
        )

    example_items: List[FieldReviewItem] = []
    for index, example in enumerate(draft.examples or ()):
        suggested = example.text
        if example.meaning:
            suggested = f"{example.text} — {example.meaning}"
        example_items.append(
            FieldReviewItem(
                key=f"example:{index}",
                label=f"Example {index + 1}",
                current="(append)",
                suggested=suggested,
                selected=True,
                target=str(index),
            )
        )

    return EnrichmentReviewState(
        source=draft.source,
        part_of_speech=pos_item,
        pronunciation=ipa_item,
        forms=tuple(form_items),
        examples=tuple(example_items),
    )


class VocabularyEnrichmentService:
    """Request drafts, build review state, apply selected values.

    Does not own Tkinter. Does not write files itself — callers persist via
    VocabStore.update.
    """

    def __init__(self, provider: VocabularyEnrichmentProvider):
        self.provider = provider

    def request_draft(self, request: EnrichmentRequest) -> EnrichmentDraft:
        return normalize_draft(self.provider.enrich(request))

    def build_review(
        self,
        entry: dict,
        draft: EnrichmentDraft,
        *,
        form_labels: Optional[Dict[str, str]] = None,
    ) -> EnrichmentReviewState:
        return build_review_state(entry, draft, form_labels=form_labels)

    def apply(
        self,
        entry: dict,
        draft: EnrichmentDraft,
        selection: EnrichmentApplySelection,
    ) -> Dict[str, Any]:
        return apply_enrichment(entry, draft, selection)

    def apply_to_store(
        self,
        store: Any,
        index: int,
        draft: EnrichmentDraft,
        selection: EnrichmentApplySelection,
    ) -> bool:
        """Apply selected enrichment through VocabStore.update. Preserves vocab_id."""
        entry = store.get(index)
        if not entry:
            return False
        updates = apply_enrichment(entry, draft, selection)
        if not updates:
            return True
        word = str(entry.get("word") or "").strip()
        meaning = str(entry.get("meaning") or "").strip()
        return bool(store.update(index, word, meaning, **updates))
