"""Stable vocabulary identity (Phase 13) + conservative per-language migration.

ID format: UUID4 string (opaque, spelling-independent).
Migration runs when VocabStore loads a language folder; idempotent.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from text_utils import entry_word, normalize


def _entry_has_meaning(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    if str(item.get("meaning") or "").strip():
        return True
    return bool(str(item.get("vi") or "").strip())

PROGRESS_IDENTITY_VERSION = 3
IDENTITY_MARKER = "vocab_id"


def new_vocab_id() -> str:
    return str(uuid.uuid4())


def is_vocab_id(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        uuid.UUID(text)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def entry_id(entry: Optional[dict]) -> str:
    if not isinstance(entry, dict):
        return ""
    value = str(entry.get("id") or "").strip()
    return value if is_vocab_id(value) else ""


def atomic_write_json(path: str, data: Any) -> None:
    """Write JSON via temp file + os.replace. Raises on failure (caller must not mark migrated)."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_write_text(path: str, text: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def assign_missing_ids(entries: Sequence[dict]) -> Tuple[List[dict], bool]:
    """Return new entry list with IDs; changed=True if any ID was generated."""
    result: List[dict] = []
    changed = False
    for item in entries or ():
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        if not entry_id(entry):
            entry["id"] = new_vocab_id()
            changed = True
        result.append(entry)
    return result, changed


def _word_to_ids(entries: Sequence[dict]) -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {}
    for entry in entries or ():
        vid = entry_id(entry)
        key = normalize(entry_word(entry))
        if not vid or not key:
            continue
        mapping.setdefault(key, []).append(vid)
    return mapping


def migrate_progress_words(
    progress_data: dict,
    vocab_entries: Sequence[dict],
) -> Tuple[dict, bool]:
    """Re-key Progress.words from normalized word → vocab_id where unambiguous.

    Ambiguous legacy key (multiple vocab rows share normalize): map to the *first*
    vocab ID in file order only; do not copy to every duplicate.
    Unmatched legacy keys are kept as orphans (not deleted).
    Already-ID keys that match a current vocab ID are kept as-is.

    Builds ``legacy_index`` {normalized_word → vocab_id} for compatibility reads.
    """
    data = dict(progress_data or {})
    words_in = dict(data.get("words") or {})
    word_to_ids = _word_to_ids(vocab_entries)
    legacy_index: Dict[str, str] = {}

    words_out: Dict[str, dict] = {}
    changed = False

    for key, stats in words_in.items():
        if not isinstance(stats, dict):
            continue
        key_s = str(key)
        if is_vocab_id(key_s):
            words_out[key_s] = dict(stats)
            continue
        norm = normalize(key_s)
        ids = word_to_ids.get(norm) or []
        if not ids:
            # Orphan history (deleted vocab, etc.) — keep under legacy key.
            words_out[key_s] = dict(stats)
            continue
        target = ids[0]  # first file-order match for ambiguous duplicates
        if target in words_out:
            # Target already filled (e.g. prior ID key); keep orphan legacy copy.
            words_out[key_s] = dict(stats)
            continue
        words_out[target] = dict(stats)
        if norm:
            legacy_index[norm] = target
        changed = True

    # Index current vocab spellings → ids for compatibility lookups after rename.
    for entry in vocab_entries or ():
        vid = entry_id(entry)
        norm = normalize(entry_word(entry))
        if vid and norm and norm not in legacy_index:
            legacy_index[norm] = vid

    days_in = dict(data.get("days") or {})
    days_out: Dict[str, dict] = {}
    for day_key, day in days_in.items():
        if not isinstance(day, dict):
            days_out[day_key] = day
            continue
        day_copy = dict(day)
        for bucket in ("asked", "correct", "wrong"):
            items = day.get(bucket)
            if not isinstance(items, list):
                continue
            mapped: List[str] = []
            for item in items:
                text = str(item)
                if is_vocab_id(text):
                    mapped.append(text)
                    continue
                ids = word_to_ids.get(normalize(text)) or []
                if len(ids) == 1:
                    mapped.append(ids[0])
                    if ids[0] != text:
                        changed = True
                elif len(ids) > 1:
                    mapped.append(ids[0])
                    changed = True
                else:
                    mapped.append(text)
            # de-dupe preserving order
            seen = set()
            unique = []
            for item in mapped:
                if item in seen:
                    continue
                seen.add(item)
                unique.append(item)
            day_copy[bucket] = unique
        days_out[day_key] = day_copy

    identity = data.get("identity")
    version = int(data.get("version") or 0)
    need_marker = identity != IDENTITY_MARKER or version < PROGRESS_IDENTITY_VERSION
    if need_marker or changed or words_out.keys() != words_in.keys():
        changed = True
    if dict(data.get("legacy_index") or {}) != legacy_index:
        changed = True

    data["words"] = words_out
    data["days"] = days_out
    data["legacy_index"] = legacy_index
    data["version"] = max(version, PROGRESS_IDENTITY_VERSION)
    data["identity"] = IDENTITY_MARKER
    return data, changed


def migrate_attempts_lines(
    lines: Sequence[str],
    vocab_entries: Sequence[dict],
) -> Tuple[List[str], bool]:
    """Backfill vocab_id on attempt JSON lines when normalized word maps uniquely.

    Ambiguous or unmatched attempts are preserved without fabricating an ID.
    Order and all other fields stay intact.
    """
    word_to_ids = _word_to_ids(vocab_entries)
    out: List[str] = []
    changed = False
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            out.append(line.rstrip("\n") + "\n")
            continue
        if not isinstance(raw, dict):
            out.append(json.dumps(raw, ensure_ascii=False) + "\n")
            continue
        existing = str(raw.get("vocab_id") or "").strip()
        if is_vocab_id(existing):
            out.append(json.dumps(raw, ensure_ascii=False) + "\n")
            continue
        key = normalize(str(raw.get("word") or ""))
        ids = word_to_ids.get(key) or []
        if len(ids) == 1:
            raw["vocab_id"] = ids[0]
            changed = True
        # ambiguous (len>1) or none: leave unresolved
        out.append(json.dumps(raw, ensure_ascii=False) + "\n")
    return out, changed


def ensure_language_identity(
    vocab_path: str,
    progress_path: Optional[str] = None,
    attempts_path: Optional[str] = None,
    *,
    vocab_entries: Optional[List[dict]] = None,
) -> List[dict]:
    """Migrate one language folder. Returns vocab entries (with IDs). Idempotent.

    On any write failure, originals remain; raises OSError after logging context.
    """
    directory = os.path.dirname(vocab_path) if vocab_path else ""
    if progress_path is None and directory:
        progress_path = os.path.join(directory, "progress.json")
    if attempts_path is None and directory:
        attempts_path = os.path.join(directory, "attempts.jsonl")

    if vocab_entries is None:
        vocab_entries = _load_vocab_list(vocab_path)
    entries, vocab_changed = assign_missing_ids(vocab_entries)
    if vocab_changed:
        atomic_write_json(vocab_path, entries)

    # Only touch progress.json when it already exists — never invent an empty file.
    if progress_path and os.path.exists(progress_path):
        progress_data = _load_progress(progress_path)
        already = (
            int(progress_data.get("version") or 0) >= PROGRESS_IDENTITY_VERSION
            and progress_data.get("identity") == IDENTITY_MARKER
        )
        migrated, prog_changed = migrate_progress_words(progress_data, entries)
        if prog_changed or not already:
            atomic_write_json(progress_path, migrated)

    if attempts_path and os.path.exists(attempts_path):
        try:
            with open(attempts_path, "r", encoding="utf-8") as f:
                raw_lines = f.readlines()
        except OSError as e:
            print("Không đọc được attempts.jsonl (migration):", e)
            raise
        new_lines, att_changed = migrate_attempts_lines(raw_lines, entries)
        if att_changed:
            atomic_write_text(attempts_path, "".join(new_lines))

    return entries


def _load_vocab_list(path: str) -> List[dict]:
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print("Không đọc được vocab.json (migration):", e)
        return []
    if not isinstance(data, list):
        return []
    result = []
    for item in data:
        if isinstance(item, dict) and entry_word(item) and _entry_has_meaning(item):
            result.append(dict(item))
    return result


def _load_progress(path: str) -> dict:
    default = {"version": 2, "words": {}, "days": {}}
    if not path or not os.path.exists(path):
        return dict(default)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(default)
    if not isinstance(data, dict):
        return dict(default)
    data.setdefault("version", 2)
    data.setdefault("words", {})
    data.setdefault("days", {})
    return data
