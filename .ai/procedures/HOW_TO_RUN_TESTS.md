# How to run tests

## Commands

From the repository (with project `app/` on `PYTHONPATH` as the existing scripts expect — typically run as today):

```text
python -m pytest
python app/smoke_test.py
```

Developer convenience: `start_dutch_guard.bat` runs the app, not the test suite.

## Expectations

Both suites should pass before a normal code phase is considered complete.

## Rules

- Tests must **not** modify real user AppData (`%APPDATA%\langstudyguard\` etc.).
- Prefer `tmp_path`, fakes, and in-memory providers.
- No real OpenAI / production VPS / live dictionary network calls in unit tests.
- `app/smoke_test.py` is retained alongside pytest; it is not a substitute for focused unit tests.
- Exact pytest count is a **snapshot**, not an invariant — see [current_state.md](../current_state.md).

## Related

- [invariants.md](../invariants.md) — test isolation
- [lessons.md](../lessons.md)
