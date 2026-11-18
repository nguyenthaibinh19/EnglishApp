# C-APP-AI-001 — App consumer conformance (test-only)

Status: **FINAL CONFORMANCE CORRECTION READY FOR PR REVIEW** — contract **C-APP-AI-001 v0.2.0 ACCEPTED**; App consumer helpers remain test-only.
Branch: `app/c-app-ai-001-consumer-conformance`. Phase 18B.9 remains the active App roadmap priority.
No `LocalAIProvider`, no production routing change, no merge/deploy authorized by this note.

Contract version: `0.2.0` ACCEPTED. Wire owner: private `langstudyguard-ai` proposal (not copied here). App owns consumer validators.

## Four-capability matrix

| Capability | Wire endpoint | App validator used | Positive fixture | Result |
|---|---|---|---|---|
| Grade | `POST /api/v1/grade` | `validate_grade_wire_payload` (test-recommended; stronger than current OpenAI coerce) | `grade_ok.json` | PASS |
| Reading | `POST /api/v1/reading` | `reading_schema.normalize_test` | `reading_ok.json` | PASS |
| Listening | `POST /api/v1/listening` | `listening_content.normalize_listening_item` | `listening_ok.json` | PASS |
| Enrich | `POST /api/v1/enrich` | `ai.base.sanitize_enrichment_ai_payload` | `enrich_ok.json` | PASS |

## Identified wire / consumer mismatches

1. **Grade score fail-closed gap:** current `OpenAIProvider.grade_answer` accepts out-of-range scores via `float(... or 0.0)`. Contract / future local consumer should reject non-finite or out-of-`[0,1]` scores (`AIError`).
2. **FakeProvider reading shape:** returns `groups: []` without usable `question_groups`; fails `normalize_test`. Local fixtures must emit App-shaped `question_groups`.
3. **Account-proxy precedence:** when `uses_account_server()` is true and `profile is None`, injected providers are bypassed. Local mode needs `use_account_proxy=False` and/or an explicit local-mode gate before provider calls.
4. **Reading unsupported groups:** unknown `type` values are skipped; if all groups invalid, App raises `ValueError` (fail-closed). Compatible with contract expectation that producer emit only supported types.

## Routing finding (smallest safe future change)

Do **not** change default account-server routing. For a future Owner-approved local mode only:

1. Add an explicit local-mode config/flag.
2. When local mode is active, call the injected provider with `use_account_proxy=False` (or equivalent early branch) so account-proxy precedence cannot hijack the call.
3. Map all local HTTP failures to `AIError` via the documented mapping; never fall back to cloud.

## Timeout finding

Observed cold grade ≈ **18.83s**. Recommended future `LOCAL_AI_INFERENCE_TIMEOUT` default: **45.0s** (minimum accepted config **25.0s**). Keep existing `OPENAI_TIMEOUT` (default 90s) for cloud/account paths.

## `LocalAIError` / HTTP → `AIError` mapping

| Status / condition | App mapping |
|---|---|
| 503 / unavailable / no models | `AIError("Local AI runtime is unavailable.")` |
| 502 / invalid schema / inference failure | `AIError("Local AI returned an invalid or incomplete result.")` |
| 401 | authorization failed |
| 403 Origin/Host | loopback security policy rejection |
| 413 | payload too large |
| 415 | media type must be application/json |
| 422 | request failed validation |
| 400 | malformed request |
| 404 | endpoint not found |
| unknown / malicious code | generic `Local AI request failed.` (never echo status/code/body) |

Messages stay sanitized; no tokens, Host, Origin, raw bodies, or untrusted error codes.

## Recommended minimal AI-M4 implementation boundary

Authorized later, not by this task:

1. Add `LocalAIProvider(AIProvider)` in `app/ai/` using loopback HTTP only.
2. Validate responses with App normalizers + grade fail-closed helper.
3. Wire timeout via `LOCAL_AI_INFERENCE_TIMEOUT` (≥25s, default 45s).
4. Explicit local-mode routing that bypasses account proxy without changing the default route.
5. No ScreenGuard / Cloud Sync / DB / offbox changes; no private AI source copied into App.

## Authorization / STOP

Await formal `C-APP-AI-001` acceptance and a separate implementation brief before coding `LocalAIProvider` or merging this branch.
