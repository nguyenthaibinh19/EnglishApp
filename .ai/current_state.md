# Current state

> First file a new agent should read. Keep this concise and update when phases complete.

**Snapshot date context:** 2026-10-26 — Phase 17C CLOSED (production accepted).
**Project baseline:** Lead-reviewed through Phase 17C
**Accepted commit:** `c0b2d2d375d1b258a5c14fec5f713065875ee0fa`

## Product

**StudyGuard / langstudyguard** is a Windows desktop study-lock app that helps a learner practice vocabulary (and optional reading / listening) before dismissing a locked fullscreen session.

- **Stack:** Python + Tkinter desktop client
- **Account server:** Hetzner VPS; domain `langstudyguard.com`
- **Distribution:** GitHub Releases (`langstudyguard.zip` / `.exe`); unsigned binary (SmartScreen friction known)
- **ScreenGuard / startup lock:** works and must remain untouched unless an explicit phase says otherwise
- **AI:** production requests go through the account server; OpenAI production key must never be embedded in the desktop executable

### Study languages (canonical registry)

`nl`, `en`, `fr`, `de`, `es`, `it`, `pt`

Dutch (`nl`) is the historical default for some compatibility paths — core architecture must not assume Dutch.

### UI / native languages

`vi`, `en` — distinct from study language.

## Current architecture map

```text
VocabularyEntry
      │
      ├──────────────┐
      ↓              ↓
   Progress      AttemptHistory
      ↓              ↓
     SRS         MistakeBook
      │              │
      └──────┬───────┘
             ↓
      DailyStudyPlanner
             ↓
        StudySession
             ↓
      Tkinter application
```

AI path:

```text
quiz / reading / listening / vocab enrich / account_server
        ↓
   ai_teacher facade
        ↓
      AIService
        ↓
     AIProvider
        ↓
 OpenAIProvider   (future: StudyGuardAIProvider, LocalModelProvider)
```

Production vocab enrichment:

```text
Word Detail → AccountServerVocabularyEnrichmentProvider
    → account /api/enrich → AIService → EnrichmentDraft → review → Apply
```

Production Listening content:

```text
listening_source (local target select)
    → AI generate_listening (/api/listening when frozen)
    → validated ListeningItem → cache
    → ListeningSession → WindowsLocalTTSProvider
```

Major UI surfaces: Home Dashboard, Progress Dashboard, Vocabulary Library + Word Detail, Mistake Book, study session (quiz + optional reading + optional listening).

## Persistence (local, per study language)

Typical layout under AppData language folders:

| File | Role | Identity / notes |
|------|------|------------------|
| `vocab.json` | Vocabulary entries | Stable UUID `id`; lexical + optional enrichment |
| `progress.json` | Aggregate learning + SRS | **version 3**, words keyed by vocab UUID; `legacy_index` for compat |
| `attempts.jsonl` | Append-oriented attempt events | Prefer `vocab_id`; `word` is historical snapshot |
| `settings.json` | App/settings | Native language, study languages, activities, etc. |

### Canonical lexical fields

```text
id, word, meaning,
alternatives?, part_of_speech?, note?,
examples?, pronunciation?, forms?
```

Enrichment storage + draft/review + production AI provider:

- `examples`: `[{text, meaning?}, ...]`
- `pronunciation`: `{ipa}` when present (storage only; AI v1 does **not** generate IPA)
- `forms`: subset of `plural` / `past` / `past_participle` / `comparative` / `superlative`
- `EnrichmentDraft` is ephemeral; AI proposes POS/forms/examples; learner must Apply
- Production path: authenticated `/api/enrich` on the account server

Legacy read still supported: `vi`, `alt`, `type`, `nl`, `en`, string `example`. New writes use canonical fields. Account HTTP wire may still send `vi` — that is **not** the local canonical field.

## Current test commands

```text
python -m pytest
python app/smoke_test.py
```

**Test notes (do not treat as a permanent green invariant):** a pre-17C-deploy snapshot once reported ~340 pytest passes. Cursor later reported a pre-existing failure in `tests/test_text_utils.py::test_exact_and_article_stripped` (article-stripping matcher / matching smoke check). Do not claim current full-suite green without fresh evidence.

## Current development position

```text
Completed: Phase 14 — Vocabulary Model v2
Completed: Phase 14.5 — Project Memory Foundation
Completed: Phase 15A — Vocabulary Enrichment Data Model
Completed: Phase 15B — Vocabulary Enrichment Draft & Review Foundation
Completed: Phase 15C — Production AI Vocabulary Enrichment v1
Completed: Phase 16 — Learning Progress Dashboard v1
Completed: Phase 17A — Listening Foundation (+ hardening / product-QA patch)
Completed: Phase 17A.1 — Window Lifecycle Stabilization
Completed: Phase 17B — Windows Local TTS Provider v1 (+ final hardening / async race fix)
Completed: Phase 17C — AI-generated Listening content v1 (production accepted)
Next (directional only): Listening history/SRS (optional later); dictionary/pronunciation enrichment; Reading Lab
```

Listening is optional (settings default **off**). Content is AI-generated from StudyGuard-selected targets (max 2) with validated cache + bundled fallback; question/answer/transcript are study language; meaning is native; word lookup on demand. Audio remains Windows local TTS only.

**Phase 17C production acceptance (2026-10-26, SHA `c0b2d2d`):** live VPS `/api/listening` deployed and verified (authenticated 200 + negative cases); Windows TTS verified; UI hotfix for missing theme color shipped; frozen Windows `.exe` Listening flow operator-QA passed. No Listening attempt/SRS/mastery persistence. No cloud TTS, STT, or pronunciation scoring.

**Known deferred (not reopening 17C):** Dutch `nl-NL` voice may be missing on a given Windows machine (OS install); legacy article-stripping matcher failure is separate technical debt. ScreenGuard still splits `pause_enforcement` from rare `release_display`. Progress Dashboard unchanged. AI enrichment remains advisory (draft → Apply).
