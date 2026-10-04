# Invariants

Rules that must not be broken casually. Tests encode many of these; this file states them for agents and humans.

## Stable vocabulary identity

```text
vocab_id is immutable.
```

- Editing `word` / `meaning` / alternatives must **never** regenerate the ID.
- Rename must preserve Progress, SRS, Attempts, Mistake Book linkage, and Word Detail history.
- See [ADR-009](decisions/ADR-009-stable-vocabulary-identity.md).

## Vocabulary lexical schema

Canonical **local** fields:

```text
meaning
alternatives
part_of_speech   (optional)
examples         (optional; structured)
pronunciation    (optional; ipa only for now)
forms            (optional; small controlled set)
```

Not as primary persisted names:

```text
vi
alt
type
example   (legacy string — migrate to examples[])
```

Legacy fields may remain supported for **reading/migration** only. New writes use canonical fields. Enrichment fields do not affect answer matching. See [ADR-010](decisions/ADR-010-vocabulary-model-v2.md), [ADR-011](decisions/ADR-011-vocabulary-enrichment-model.md).

## Enrichment never silently overwrites

```text
External enrichment must NEVER silently overwrite canonical vocabulary data.
```

- Suggestions arrive as ephemeral `EnrichmentDraft`.
- Learners review and explicitly apply selected fields.
- Missing draft fields must not clear existing canonical values.
- See [ADR-012](decisions/ADR-012-enrichment-review-before-apply.md).

## Progress / SRS

- Progress state follows vocabulary ID (progress.json v3).
- SRS **future** items must not be reported as **due** in Daily Study / Home.
- Legacy missing `due_at` remains due (current Phase 8 behavior).
- Long-term due ≠ within-session requeue.

## Mastery semantics

Current mastery-compatible success (`LearningAttempt.correct` / Progress `correct` increments):

```text
verdict == exact
AND
hint_used == False
```

Near answers and hint-assisted exact answers are **non-mastered**. Do not casually redefine `LearningAttempt.correct`.

## Mistake Book

- Latest **mastered** attempt → item does **not** currently need attention.
- Latest **non-mastered** attempt → item needs attention.
- Not a permanent dump of every historical error.

## AI security

- Production AI credentials stay server-side.
- Never embed the server OpenAI API key into the frozen desktop executable, settings, logs, or test fixtures.
- AI vocabulary enrichment is advisory only (draft → review → Apply); see [ADR-013](decisions/ADR-013-ai-vocabulary-enrichment.md).

## Reading optionality

- Reading remains optional when enabled in settings.
- Reading / AI / network failure must not permanently block lock-session completion after **required** vocabulary work is complete.

## Listening optionality / audio safety

- Listening is optional when enabled; settings default **disabled** until a production audio provider exists.
- Missing / failed audio provider → Listening **unavailable**; must not permanently block lock-session completion after required vocabulary work.
- Listening answer feedback must not redefine vocabulary mastery / SRS. See [ADR-015](decisions/ADR-015-listening-activity.md).

## StudySession vs ScreenGuard

- StudySession decides **logical** completion.
- ScreenGuard / Tkinter owns **lock enforcement**.
- Do not move lock/security behavior into the session-domain model.

## Persistence safety

- Schema migration must preserve existing user learning data.
- Destructive migration is unacceptable without an explicit migration design.
- When rewriting user persistence: prefer atomic temp-write + flush/fsync + `os.replace`.
- Migrations must be **idempotent**.

## Test isolation

- Tests must not modify real user AppData.
- Tests must not contact production services (OpenAI, VPS, live dictionaries) unless an explicit, isolated fixture says otherwise — prefer fakes / `tmp_path`.

## Language architecture

- Study language and UI/native language are **distinct**.
- Core architecture must not assume Dutch except explicit backward-compatibility / default behavior.
