# How to add a study language

See [ADR-002](../decisions/ADR-002-canonical-study-languages.md).

## Steps

1. Add the language to the canonical **`StudyLanguage` registry** (codes, labels, articles, elisions, samples as needed).
2. Keep **study language** distinct from **UI/native** language (`vi` / `en`).
3. Review article/elision metadata used by answer matching (`text_utils` + language profile).
4. Provide starter vocabulary under bundled starters if new users should get seed words.
5. Confirm per-language data paths (`vocab.json` / `progress.json` / `attempts.jsonl`) isolate correctly.
6. Add/adjust tests for registry + matching behavior; avoid hard-coded language branches in core.
7. Run pytest + smoke test.
8. Update `.ai/current_state.md` language list if the supported set changes.

## Do not

- Assume Dutch defaults outside explicit compatibility.
- Treat UI language as a study language.
- Scatter `if code == "xx"` through quiz/progress modules when registry metadata should carry the difference.
