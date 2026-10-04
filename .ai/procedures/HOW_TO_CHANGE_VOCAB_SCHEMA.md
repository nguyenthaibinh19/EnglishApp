# How to change the vocabulary schema

Use this checklist before changing `vocab.json` fields or `VocabularyEntry`.

See [ADR-009](../decisions/ADR-009-stable-vocabulary-identity.md), [ADR-010](../decisions/ADR-010-vocabulary-model-v2.md), [invariants.md](../invariants.md).

## Checklist

1. **Preserve `vocab_id`** — never regenerate IDs for existing entries.
2. **Audit all lexical consumers** (VocabStore, quiz, library, mistake book, reading add, account wire helpers, starters).
3. **Define canonical field semantics** (name, optionality, types).
4. **Define legacy compatibility** (what still loads; canonical wins when both exist).
5. **Migration must be idempotent** (second load does not rewrite unnecessarily or invent new IDs).
6. **Atomic writes** for rewritten user files (temp → flush/fsync → `os.replace`).
7. **Preserve Progress / SRS / Attempts identity** links across rename and field renames.
8. **Test legacy → current** with representative old shapes (`vi`, `alt`, `nl`/`en`, missing optional fields).
9. **Test second load / migration** (idempotency).
10. Run `python -m pytest`.
11. Run `python app/smoke_test.py`.
12. **Never** validate destructive migration against real AppData.

## Reminders

- HTTP wire may still use `vi` even when local canonical field is `meaning`.
- Article/gender fields are deferred unless a dedicated design says otherwise.
- Update `.ai/` memory if contracts/invariants change.
