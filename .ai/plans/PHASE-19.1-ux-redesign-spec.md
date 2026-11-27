# Phase 19.1 — Learning-experience redesign specification

Status: **R1 READY FOR REVIEW.** Architect decision `APP_19D1_UI_DIRECTION_ACCEPTED_SPEC_EXTENSION_REQUIRED`. The Today / Words / You / Settings architecture is accepted. This revision extends the same specification. It does not redo the UX audit, reopen Phase 18, or authorize implementation.

Specification only. No UI rewrite, no release rebuild, no backend change, no voice-engine change, and no mascot work are authorized by this document. Adaptive learning, sentence practice, and grammar stay in this phase as future engine and schema work. No new mastery formula is accepted in R1.

Implementation note, 2026-11-27: Phase 19.2B later merged the CustomTkinter home and study presentation (PR #31). Phase 19.3 later merged local System.Speech plus WinRT playback, including Normal and Slow (PR #32, `7aedf7a423d2ef244ce37b5d3f348c7f75ed0241`). Neither is in the installed public release v1.5.0. The specification text below is preserved as written, including the statement that rate was not implemented when this spec was accepted. Adaptive Vocabulary is the next product implementation priority and still needs a separate Architect brief. This note does not authorize that work.

Baseline: released v1.5.0 on `main`. Product shell is `FreeHome` in `app/home_app.py`. Study orchestration is `StudySession` (`app/study_session.py`) plus the Tk adapters `quiz_app.py`, `reading_app.py`, and `listening_app.py`. Presentation models that must stay pure: `home_viewmodel.py`, `progress_viewmodel.py`.

Emotional reference: Duolingo’s ease and warmth. The visual language stays original. Scheduling stays the current SRS ladder. The exercise experience becomes progressive.

## 1. UX audit

Inspected from the released v1.5.0 home (account signed in, Cloud Sync Synced, Dutch, unlocked) and from the current screen code. The installed window is about 560×600. Secondary screens open as owned `Toplevel` windows.

### Strengths

- The daily action already exists: one full-width **Start today's study** button.
- The planner is honest. “Vocabulary · 5 items” is the session cap, not the library size. Due, new, and attention come from `DailyStudyPlan` and are not recomputed in the widget.
- Study order is stable: vocabulary, then optional reading, then optional listening. Optional activities can be skipped. A missing voice does not trap a locked session.
- Vocabulary, Progress, Mistake Book, and Add word are one click from home.
- Copy is already bilingual through `config.ui`.
- Cloud Sync status is precise. The panel does not claim Synced without catch-up.
- Unlocked close returns home without marking the session complete. Screen lock stays out of the domain model.

### Pain points by kind

**Structural UX**

- Home is a dashboard of peer panels: identity, account, sync, three SRS counts, activity flags, four equal quick actions, and a lock footnote. The next step is present, but it competes with administration.
- Account and Cloud Sync occupy the top of the daily screen. A signed-in learner sees username, account id, environment name, server host, and a technical sync sentence before the study plan.
- Add word is not a screen. It is a modal inside the vocabulary library. Home’s “Add words” opens that library and then the dialog.
- Study Settings is a small dialog with two checkboxes and an emergency-code button. Language, native language, lock, and voice live elsewhere, or not at all. StudyMaster still shows the older dense control panel (activity checkboxes, language rows, sync-conflict buttons, guest import).
- There is no persistent navigation. Each tool is a separate window with its own Close button. The learner cannot see where they are in the product.
- Home paints the plan before a download finishes, so the first view can show yesterday’s counts. That is an interaction bug in the current shell, not a data bug.

**Visual design**

- Theme is Vista `ttk`: cool gray `#f4f6f8`, navy `#1e4f9c`, white cards, Segoe UI. It is readable and consistent inside one window, and it feels like a settings utility.
- Cards are `LabelFrame` boxes. Primary and secondary buttons differ mainly by padding. There is no soft fill, no icon, and no quiet visual rank between “start” and “open a tool”.
- The vocabulary library is a raw `Listbox`. Progress is six stacked muted lines plus a hand-drawn 10-pixel bar. Mistake Book is another text list. These three tools do not look like one family.
- The OS window title is the executable name. The in-app header says “Language Guard — PRODUCTION” on the real account.

**Copy and tone**

- SRS words face the learner: “due”, “need attention”, “mastery-quality answers”.
- “Reading · off” and “Listening · off” describe configuration, not today’s plan.
- The footer talks about screen lock before the learner has started.
- “Mistake Book” / “Sổ lỗi” frames review as a record of failure.
- Sync copy is accurate and technical: “The server has received the changes and this device has caught up.”
- Correct / almost / wrong feedback is clear, then immediately numeric: streak and accuracy on every question.

**Interaction**

- The quiz row shows Submit, Hint, Write a sentence, Manage vocabulary, Go to reading, and Emergency exit together. Five of those leave the question.
- After a correct answer the next card arrives in about 600 ms. After a wrong answer the correct form stays up for about 2.5 s, then advances on its own. The learner cannot choose when to continue.
- Listening has one Play control. After playback the status says “Played.” There is no replay control, no speed, and no voice choice. The voice is the first installed match for `nl-NL`, `en-US`/`en-GB`, or `es-ES`/`es-MX`.
- Emergency enrollment can appear before home on a fresh launch. That is a security step, not part of the daily companion.

### What feels heavier than the job

The learning job is: see today’s small task, answer a few words, hear a word when listening is on, come back tomorrow. The current home also manages account, environment, sync diagnostics, activity flags, and lock policy. Those belong behind the study plan.

## 2. Information architecture

One calm home. Everything else is a destination opened from home, or a step inside today’s session. Do not invent a second app shell.

### Primary navigation

Visible on Home, in this order:

1. **Today** — the home dashboard itself. Default place.
2. **Study** — today’s session. The primary button. Not a permanent tab.
3. **Words** — vocabulary library, including add.
4. **You** — progress, words to review, and a link onward to settings.

On a 560-pixel window this is a top title plus three text actions under the start button, not a phone tab bar and not four equal rectangles.

### Secondary navigation

Reached from Study Settings, not from the daily header:

- Study Settings (what today includes)
- Account and Cloud Sync
- Voice
- Emergency code

Also secondary, and not on the home surface:

- Word detail
- Reading passage
- Listening item
- Sync conflict and preference conflict
- Guest import
- Sentence practice

### Screen map

```text
Home (Today)
├── Start → Study session
│            ├── Vocabulary questions
│            ├── Reading (only if enabled)
│            └── Listening (only if enabled)
├── Words → Vocabulary library
│            ├── Add word
│            └── Word detail
├── You → Progress
│          └── Words to practice (today’s Mistake Book)
└── Settings
     ├── Study Settings
     ├── Account / Cloud Sync
     ├── Voice
     └── Emergency code
```

Language stays a property of Today, Words, Progress, and Voice. With one study language, do not ask “which language?” on every open. With more than one, a short chooser remains, as `FreeHome._choose_language` does now.

### What moves off Home

| Current home block | New place |
|---|---|
| Environment title and server host | Hidden in production. Non-production builds may keep a single quiet banner. |
| Account card, logout, and the long sync sentence | Settings. Today keeps a compact Cloud Sync status. |
| Reading off / Listening off | Removed from the plan card. Settings own the toggles. If one is included today, the session itself says so. |
| Lock footnote | Study Settings, next to the lock control. |
| Four equal tool buttons | Words, and You. Add word lives on Words and as one secondary home action. |

## 3. Design principles

The accepted direction is warm, soft, and modern, implemented with the current Tkinter theme. One primary learning action. Technical detail stays minimal. A compact Cloud Sync status stays on Today. Its explanation, logout, and conflict actions stay in Settings.

**Visual tone.** Warm paper, not a control panel. Background near `#f6f1ea`. Cards white with a warm hairline, not a heavy group box. Accent is a softened green-teal for the one primary action, close to `#2f7d6d`. Keep the existing semantic green / amber / red only for answer results.

**Emotional tone.** A short daily companion. Celebrate finishing the small session. Do not praise every correct letter. Do not scold a wrong answer.

**Spacing.** One vertical rhythm. Page padding stays at least the current 28 px. Related lines sit 8 px apart. Sections sit 20–24 px apart. Do not fill empty space with extra metrics.

**Typography.** Keep Segoe UI. Three levels only: page title (18 bold), card title (14 bold), body (12). The question in a study card may be 26 bold, as it is now. Muted text is for hints and timestamps, not for the main numbers.

**Cards and buttons.** One primary button per screen, full width on Home and on the study card. Secondary actions are text buttons or quiet outline buttons. Do not put six buttons in one row. `Primary.TButton` remains the single emphasis style. Vista `ttk` will not produce pill illustrations; do not fake them with images in the first waves.

**Color.** Warm neutral surfaces. One accent. Result colors stay `COLOR_OK`, `COLOR_WARN`, and `COLOR_BAD`. Do not encode due / new / attention as a traffic light.

**Iconography.** None in wave 1. A later wave may add a few Segoe MDL2 or small local glyphs for play, replay, and listen. No character art.

**Feedback.** One sentence, then the next step. Correct: “That’s it.” Almost: “Very close. The spelling is …” Wrong: “The word is …” plus the meaning already on the card. No streak, accuracy, or “mastery” line on the question.

**Empty states.** Say what is missing and give the one next action. “No words yet. Add the first word.” “Nothing to review. Today’s new words are enough.” “This PC has no Dutch voice yet. You can skip listening.”

**Success.** End of session only: how many words were practiced, in one line, and a close button back to Today. Do not show a statistics sheet.

**Errors.** Plain language, one action. Sync trouble: “Not saved to your account yet.” with Review on the Account screen. Voice trouble: name the language and offer Skip. Do not show exception text, host names, or environment ids to the learner.

**Microcopy.** Short, spoken, bilingual through `config.ui`. Prefer “today”, “words”, “review”, “listen again”. Today may show the words “Cloud Sync” plus one short state. The long technical sentence stays in Settings. Avoid “entity”, “due”, “attention”, “mastery-quality”, “environment”, and “backend” on Today.

## 4. Screen specifications

### 4.1 Home dashboard

**Purpose.** Tell the learner what to do today and start it.

**Questions it answers.** What language am I studying? What is today’s small task? How do I start? Where are my words?

**Information priority.**

1. Greeting and language.
2. One plan sentence, for example “5 words today.”
3. Start.
4. A single supporting line: reviews first, then new words. Use counts only as that sentence, not as three peer metrics.
5. Words, and You.
6. A compact Cloud Sync status. The long sentence, account actions, and conflict review stay in Settings.

**Layout.** Header (greeting, language, Settings). Plan card. One primary button. Two secondary actions: Words and You. Compact sync status. The current 560×600 minimum still fits. Do not grow the window to make room for the old account card.

**Main action.** Start today’s study. Same command as `FreeHome._start_study`.

**Secondary actions.** Words. Add a word. You (progress). Settings, in the header.

**Improvements.** Remove the production title, the account box, the on/off activity lines, the four-up grid, and the lock footnote. Replace “109 new / 3 due / 3 need attention” with a sentence a learner can act on. Refresh the plan when sync catch-up changes the local library, so the first paint cannot stay stale.

**Constraints.** Keep `build_home_view_model`. Add learner-facing strings there; do not recompute SRS in the widget. Production identity stays available to code. Only non-production builds show an environment banner. The compact status must call the existing sync description and must not invent a Synced state. ScreenGuard, emergency exit, account isolation, SRS, and Cloud Sync behavior stay as they are.

### 4.2 Study session

Specified in section 5. The screen spec summary:

**Purpose.** Finish today’s planned words, then optional reading and listening, with nothing else on screen.

**Questions.** What does this word mean? Where do I type? How far through today’s set am I? How do I hear it again during listening?

**Priority.** Progress (“2 of 5”), question, answer, one submit button, one line of feedback.

**Layout.** Centered column. No toolbar of tools.

**Main action.** Submit, then Continue after feedback.

**Secondary.** Hint. Leave for now. Replay only on a listening step. Emergency exit only while lock mode is on, and visually separate from Submit.

**Improvements.** Remove Manage vocabulary, Write a sentence, and Go to reading from the question. Let the learner continue instead of auto-advancing. Save the numeric session stats for the end.

**Constraints.** `StudySession` still owns activity order and completion. `ScreenGuard` still owns lock. Unlocked Leave does not mark the session complete. Attempts already accepted stay accepted. The first study-card wave keeps today’s typed recall. The later exercise types in sections 6 and 7 stay in this specification until a separate implementation approval.

### 4.3 Vocabulary library

**Purpose.** Find a word, see how it is doing, or add one.

**Questions.** How many words do I have? Which ones need review? How do I add or open one?

**Priority.** Language title and count. Search. Filter (All, To review, New). The list. Add word.

**Layout.** Keep the single window. Replace the bare list, over time, with rows that show the word, the meaning, and one quiet state word: New, Review, or Learning. Search stays above the list. Add word stays at the top right.

**Main action.** Add word.

**Secondary.** Open the selected word. Close, which returns to Home.

**Improvements.** “To review” instead of “Needs attention”. Empty search says “No word matches that.” The double-click detail can stay.

**Constraints.** Filters stay the current `FILTER_*` set. The list still reads `VocabularyLibraryApp` and the store; it does not write SRS. Word detail remains the place for forms, examples, and history.

### 4.4 Add word

**Purpose.** Save one word and its meaning with as little form as possible.

**Questions.** What is the word? What does it mean? Did it save?

**Priority.** Word. Meaning. Save.

**Layout.** A short dialog over the library, as today. Two fields visible. Example and other spellings sit behind “More details”, collapsed. Save is the primary button. Cancel closes without writing.

**Main action.** Save.

**Secondary.** More details. Cancel.

**Improvements.** Home can open this dialog without making the learner scan the whole library first. Success is “Saved.” and the dialog closes. A duplicate uses the current truthful duplicate result, in one sentence.

**Constraints.** `commit_vocab_edit` / store `add` stay the write path. Do not add fields the vocabulary model does not store. Do not auto-import guest files.

### 4.5 Progress

**Purpose.** Show that practice is accumulating, and offer the words that need another look.

**Questions.** Have I practiced? What should I review? How did the last few days go?

**Priority.** One headline: words practiced, and words still new. A seven-day strip. A short list of recent words. One action: Practice these words.

**Layout.** Three stacked cards, not six muted lines plus a separate mastery block. The current canvas bar can become a slightly taller warm bar. Timestamps move to muted secondary text.

**Main action.** Practice these words, which is today’s mistake-book practice. If there is nothing to review, the action is hidden and the headline says today’s new words are enough.

**Secondary.** Change language, only when more than one study language exists. Refresh can go away if the window reloads on open.

**Improvements.** Drop “mastery-quality answers” from the first view. Fold Mistake Book into this screen as “Words to practice” so Home does not need a failure-named destination. The standalone Mistake Book window can remain for one wave as the same content, then be opened from here.

**Constraints.** Render `ProgressViewModel` and `MistakeSummary`. Do not recompute SRS or attempt history in the widget. Recent answers stay the existing rows.

### 4.6 Study Settings, Account, and Sync

**Purpose.** Change how study works, and check that the account is safe, without standing in front of Today.

**Questions.** Is reading or listening part of today? Which language? Is my work saved? How do I sign out? Where is the emergency code? Which voice will I hear?

**Priority.** Study choices first. Account second. Voice third. Emergency last, and clearly separate.

**Layout.** One Settings window with four stacked sections, not four new products. Study section: reading on/off, listening on/off, native language, study language. Account section: signed-in name, the current sync sentence, log out, switch account. Voice section: the plan in section 11. Emergency section: one button into the existing recovery dialog.

**Main action.** Close, after toggles have already saved, which they do today.

**Secondary.** Log out. Switch account. Review a conflict, only when one exists. Emergency code.

**Improvements.** Delete the sentence that says listening has no audio provider. The provider exists and is local. Move language pickers off StudyMaster’s home card. Show conflict and guest-import actions only when there is something to resolve or import.

**Constraints.** Activity toggles keep `set_activity_enabled`, which is preference-synced. Do not add voice, rate, or emergency state to `ACCOUNT_PREF_KEYS` in this phase. Logout and switch keep `account_session`. Conflict screens stay `sync_conflict_app` and `prefs_conflict_app`. Emergency recovery stays `emergency_enroll.recover` and still refuses to reveal a code while lock is active. Do not show the code in a window title.

### 4.7 Wireframes

Lightweight structure for the accepted navigation. These are layout sketches, not a visual asset pass.

Today, about 560 px wide:

```text
Good evening
Dutch                              Settings

┌──────────────────────────────────────────┐
│  5 words today                           │
│  A few reviews, then new words.          │
│                                          │
│  [ Start today's study                 ] │
└──────────────────────────────────────────┘

Words                              You

Cloud Sync · Saved
```

The sync line is one status from the existing catch-up check. Tapping it opens Settings. Logout, the long explanation, and conflicts are not on this screen.

Study session, introduction step:

```text
1 of 5                          Leave

┌──────────────────────────────────────────┐
│  word                                    │
│  meaning                                 │
│  A short example sentence.               │
│                                          │
│  [ Listen ]          [ Listen slowly ]   │
│                                          │
│  [ Continue                            ] │
└──────────────────────────────────────────┘
```

Study session, independent recall:

```text
4 of 5                          Leave

┌──────────────────────────────────────────┐
│  Which word means                        │
│                                          │
│  meaning                                 │
│                                          │
│  [ type the word                     ]   │
│                                          │
│  [ Check                               ] │
└──────────────────────────────────────────┘
```

After a repeated miss, the same frame becomes a missing-letter or guided-typing card. One primary button remains. Hint, when the step allows it, is a text action under the field. Emergency exit appears only while lock mode is on, away from Check.

## 5. Study experience

The session is a stack of small cards. It should feel calm, light, and rewarding at the end.

**Progress.** “2 of 5” for the vocabulary target. A thin bar may mirror that fraction. Do not show today’s lifetime totals, streak, or accuracy until the session ends. Reading and listening, when included, appear as “Next: a short reading” or “Next: a short listen” between steps, not as checkboxes.

**Question.** One prompt: “Which Dutch word means” plus the meaning, large and centered. The example stays hidden until Hint. Do not show the word list, the account, or the sync state.

**Answer.** One centered field. Enter submits. After a verdict, Enter continues. The field is disabled only while the verdict is on screen.

**Audio.** A word introduction may offer Listen at normal speed and Listen slowly. Playback stays off the UI thread and never blocks Continue. Listening keeps the same two speeds. The listening transcript stays hidden until the answer is checked. Word-tap lookup can remain; it is a secondary control.

**Feedback.**

| Result | On the card | Then |
|---|---|---|
| Correct | “That’s it.” in green, with the word | Continue, or Enter |
| Almost | “Very close.” plus the spelling, in amber | Continue |
| Wrong | “The word is …” plus the meaning, in red | Continue |
| Empty | “Type an answer first.” | Stay |

No automatic advance. A wrong answer stays on this card until the learner continues. The next card may be an easier exercise, as section 6 describes. Sentence practice is the separate progression in section 7. It is not a detour forced by one wrong word.

**Close and exit.** A quiet “Leave for now” is always available when the session is unlocked. It closes the session window and returns to Home. It does not mark vocabulary, reading, or listening complete. Answers already submitted stay saved. While lock mode is on, ordinary close still does nothing, and Emergency exit remains the existing guarded path. Do not put that button next to Submit.

**Encouragement.** During the card: at most three words. At the end: “Done for today.” plus the number practiced and the accuracy already calculated by `session_stats`. One button: Back to today. If more activities remain, the end of vocabulary says “Vocabulary done.” and offers the next activity or Skip for optional ones.

**On the card.** Question, answer, submit, hint, progress, feedback, leave.

**Not on the word card.** Account, sync, environment, SRS interval, operation ids, manage-vocabulary, guest import, reading jump, streak, or a mascot. Sentence writing and the grammar explanation live on their own cards.

## 6. Adaptive vocabulary learning

The daily set stays small. Each word moves through a difficulty ladder. The learner sees one exercise at a time. The current SRS ladder still decides when a word is due. Exercise difficulty decides how that word is practiced today.

### Ladder

| Step | Exercise | Support | What the learner does |
|---|---|---|---|
| 1 | Introduction | Recognition | Sees the word, its meaning, and a short example, and can hear it at normal and slow speed |
| 2 | Multiple choice | Recognition | Picks the word from a few meanings, or the meaning from a few words |
| 3 | Missing letter | Assisted recall | Completes the word with one or more letters shown |
| 4 | Guided typing | Assisted recall | Types the word with a first letter, a hint, or a fading prompt |
| 5 | Independent recall | Independent recall | Types the word from the meaning, with no hint |
| 6 | Context | Independent or assisted, by sentence level | Uses the word in the sentence progression in section 7 |

A new word starts at introduction. A word already mastered on the SRS ladder can start at independent recall when it is due. A word whose latest independent attempt was non-mastered starts one step easier than independent recall.

### How difficulty moves

Performance and existing SRS evidence choose the step:

- A successful step may advance one step inside the same session.
- A failure brings more guidance. Repeated failure at the same step offers the next easier step.
- The number of failures that counts as “repeated” is a session policy to tune later. It is not an SRS formula, and R1 does not accept a numeric threshold.
- Introduction has no failure state. The learner continues when they have seen and, if a voice exists, heard the word.
- Within-session requeue stays separate from the SRS due date. An easier card today does not move `due_at`.

### Compatibility with SRS and attempt events

R1 distinguishes the three support levels and does not accept a new mastery formula.

The only mastery rule that exists today is `verdict == exact` and `hint_used == false`. That is `LearningAttempt.correct`. A near answer stays non-mastered. A hint-assisted exact answer stays non-mastered. Progress and the server review ladder both consume that same bit. Mistake Book treats the latest attempt with that bit as the attention decision.

| Support | Current exercises | What today’s event can record |
|---|---|---|
| Recognition | Introduction, multiple choice | Nothing. There is no recognition verdict. |
| Assisted recall | Missing letter, guided typing, today’s Hint | Only the current hint path: exact or near with `hint_used` true, which is non-mastered and still updates SRS as a failed review. |
| Independent recall | Typed answer, no hint | `exact`, `near`, or `wrong`, with `hint_used` false. Only exact is mastered. |

A multiple-choice or guided answer cannot be written as a current progress event without either marking it mastered or resetting the SRS interval. That is why those exercises need a future record of their own before they are stored. Section 10 names that record. It does not define a score, a weight, or a threshold, and R1 does not accept one.

Until that contract exists, only independent recall may create a `LearningAttempt` and a Cloud Sync progress event. Recognition and assisted practice may be shown. They may not change `correct`, the SRS ladder, or Mistake Book attention.

## 7. Progressive sentence practice

Sentence practice is a later card in the session, after the planned words, or a chosen practice from a word. One wrong vocabulary answer does not open it automatically.

| Level | Exercise | Support |
|---|---|---|
| 1 | Word-bank arrangement | Assisted. The learner orders the given words into a sentence. |
| 2 | Fill-in-the-blank | Assisted. The sentence is visible and one target is missing. |
| 3 | Guided writing | Assisted. A grammar template shows the pattern and the learner writes the sentence. |
| 4 | Independent writing | Independent. The learner writes the sentence from a meaning or a prompt, with no bank and no template. |

A sentence can have more than one grammatically valid answer. Matching accepts each validated answer as correct. The accepted set comes from reviewed content when it exists. An AI suggestion can add a candidate only after it is marked valid by the same review rule used for vocabulary enrichment: draft, then review, then apply. The study card must not treat an unreviewed model response as the answer key.

Levels 1–3 never set vocabulary mastery. Level 4 records a sentence result. That result still does not set vocabulary `correct` unless the learner has also produced the target word by independent recall. Sentence skill is a future separate record. It does not increment the SRS streak.

Failure steps down one level and shows the guidance for that level. The same hard prompt is not repeated as the only response to a mistake.

## 8. Grammar companion

The grammar companion is optional, contextual, and expandable. A quiet “Why?” under the feedback opens it in place. Continue stays available while it is open. It never appears on the word-recall card.

A single explanation can contain:

- The grammar rule, in one beginner sentence, then the fuller rule.
- A sentence-structure visualization with the parts in order.
- Color-coded components: subject, verb, object, and the extra part that the exercise is teaching. Colors are stable across languages.
- A beginner explanation in the learner’s native language.
- One or two additional examples.
- The learner’s own mistake when it is spelling, conjugation, word order, or grammar, with the corrected piece highlighted. A vocabulary mismatch stays in the feedback line in section 9. It is not a grammar-library entry.

Foundational rules come from reusable, validated grammar content. AI may explain this learner’s sentence by pointing at that content. AI may not invent a conflicting rule when validated content exists.

### Future Grammar Library

The library is content, organized by study language and CEFR level. It is not learner data and it is not a second Mistake Book. A future browser can filter by language and level, then open the same explanation component. The library waits until sentence practice has a real content source. It is specified here so the explanation component has a place to grow. It is not part of the first home or study-card wave.

## 9. AI feedback

Feedback names one primary error class:

- **Spelling** — the word is right, the letters are not.
- **Vocabulary** — the word does not mean what the prompt asked.
- **Conjugation** — the verb form does not match the pattern.
- **Word order** — the words are right and the order is not.
- **Grammar** — agreement, article, tense, or another structural rule.

The card shows one encouraging sentence and one action. Example shape: “The verb needs the present form. Try the guided sentence.” The class name can sit in quiet text. The card does not show a score penalty, a streak break, or a list of every class that might also apply.

When a validated grammar entry exists, the action opens that entry. When it does not, the action offers the next easier exercise. Production AI credentials stay on the server. The desktop build does not receive an API key.

## 10. Integration and future contracts

These requirements preserve the current safety invariants:

- SRS scheduling remains `interval_days` and `due_at`, with the current ladder. Future reviews stay out of the due count. Session requeue stays separate from due.
- Attempt History stays append-only. An independent answer appends one `LearningAttempt`. Older lines stay unchanged.
- Mistake Book stays derived from the latest independent attempt. Mastered means exact and unaided. A recognition or assisted success does not clear attention.
- Cloud Sync keeps today’s progress event for independent recall. Event ids, verdicts, and the mastered flag keep their current meaning.
- ScreenGuard still owns lock. New cards, grammar popovers, and audio controls use the existing pause rules. Unlocked Leave still does not mark the session complete. Emergency exit stays the quiet lock-mode path.

Voice for these exercises uses section 11’s playback plan: Normal and Slow for every registered study language that has a local voice. English, Dutch, and Spanish remain the first settings groups because their cultures are already preferred. French, German, Italian, and Portuguese use the same Normal / Slow behavior when a same-language voice is installed.

### Future model and schema work

This is the contract to design before any learning wave is implemented. It is not a migration to run now.

- An exercise model needs `kind`, `support_level` (`recognition`, `assisted`, `independent`), the prompt, and the accepted answers. Multiple valid sentences live in that accepted set.
- Independent recall keeps the current attempt fields: `verdict`, `hint_used`, `correct`, `vocab_id`, and the answer snapshots. `correct` remains true only for exact unaided recall.
- Recognition and assisted practice need their own append-only practice record. That record carries the exercise kind, the support level, and the error class. It does not call `Progress.record` and it does not call the SRS review update.
- A future sync revision, if practice records are synced, is additive. Old clients and the current server keep accepting only `exact`, `near`, and `wrong` progress events. An assisted event must not be sent as one of those events, because the server applies the SRS ladder from them. Unknown practice records on an older server are ignored, not rejected in a way that blocks vocabulary sync.
- `algorithm_id` remains the SRS algorithm. Exercise selection gets a separate policy id so a change in difficulty steps cannot be mistaken for a change in the review ladder.
- Grammar content is versioned by language and CEFR level. It is not an account preference and it is not added to `ACCOUNT_PREF_KEYS`.
- Sentence results, when stored, use a separate skill record. They do not increment vocabulary streak or `correct`.

## 11. Voice support plan

Inspected `ListeningAudioProvider`, `resolve_listening_audio_provider`, and `WindowsLocalTTSProvider` on 2026-11-25. No speech script was changed, and no learner text was spoken.

### What exists

The seam is `ListeningAudioProvider.play(text, language_code)`, `is_available()`, and `supports(language_code)`. Production resolution returns `WindowsLocalTTSProvider` when Windows System.Speech can be loaded through a fixed PowerShell script. Otherwise it returns none, and Listening stays skippable. Tests inject `FakeListeningAudioProvider`. There is no second production provider.

Discovery lists enabled voices as name, culture, and two-letter language. Selection is deterministic:

1. The first preferred culture that is installed.
2. Any other installed voice with the same two-letter language, ordered by culture then name.
3. No voice. `supports()` is false and `play()` raises `missing_voice_message`. It does not pick another language.

Preferred cultures already cover all seven study languages:

| Study language | Code | Preferred cultures |
|---|---|---|
| English | en | en-US, then en-GB |
| Dutch | nl | nl-NL |
| Spanish | es | es-ES, then es-MX |
| French | fr | fr-FR, then fr-CA |
| German | de | de-DE |
| Italian | it | it-IT |
| Portuguese | pt | pt-PT, then pt-BR |

On this development PC the discovery returned two enabled voices, both `en-US`: Microsoft David Desktop and Microsoft Zira Desktop. Selection for English is Microsoft David Desktop, because the name sort puts David before Zira. Dutch, Spanish, French, German, Italian, and Portuguese resolved to no voice. That inventory is this PC only. Another PC with a Dutch speech pack would select `nl-NL`. The product rule is the selector, not this inventory.

### Windows limitations

- Speech uses desktop System.Speech voices. A Windows display language can be installed without a text-to-speech voice.
- The speak script calls `SelectVoice` and `Speak`. It does not set `Rate`, so Normal and Slow are not implemented in this specification. Both buttons would sound the same until a later approved change passes a rate as environment data. Phase 19.3 later made that change. This bullet stays as the specification was written.
- Discovery does not return `VoiceInfo.Gender`. A Male / Female control stays absent. The English choice on this PC is alphabetical, not a gender choice.
- Playback is one hidden PowerShell process per utterance, with a 90-second speak timeout and a 20-second discovery timeout. Discovery stays off the Tk thread.
- The backend can be available while every non-English study language is unsupported. `is_available()` and `supports(language)` answer different questions.
- Non-Windows hosts have no production provider.

### Fallback

A missing voice is an unavailable listening step, with Skip, and an introduction card that still shows the word, meaning, and example. The existing message tells the learner to install a Windows voice for that language. The app does not download a voice and does not start a language-pack install.

Foreign-language text is never spoken with an English voice. If `supports(language)` is false, playback does not run. A future provider has to obey the same `supports()` gate. A paid or cloud speech provider is out of scope.

Normal, Slow, replay, and preview are the learner-facing controls. Preview plays a fixed sample for that language through the same `play()` path and disables the button while audio is busy. Replay repeats the current item. Slow waits on the rate change above. Voice name and speed, when they exist, stay local settings and stay out of `ACCOUNT_PREF_KEYS`.

## 12. Implementation roadmap

Visual redesign and the learning engine are separate tracks inside this phase. A visual wave may change Tk layout, copy, and theme tokens. It may not change attempt events, SRS, sync payloads, or the speech script. An engine wave waits for its own approval and for the section 10 contract. No mastery formula beyond today’s exact unaided rule is part of either track yet.

### Visual waves

| Wave | Change | Stays unchanged |
|---|---|---|
| V1 | Warm tokens in `ui_common` | Every screen’s behavior |
| V2 | Today: hierarchy, one start button, Words, You, compact Cloud Sync status, plan refresh after catch-up | Account actions, SRS math |
| V3 | Current study card: manual Continue, extra tools removed, quiet Leave | Exercise types, attempt recording |
| V4 | Words list and the short Add word dialog | Vocabulary schema |
| V5 | You: progress headline and words to practice | Mistake Book derivation |
| V6 | Settings shell: study, account details, emergency | Preference keys, lock rules |
| V7 | Voice screen listing installed voices and the missing-voice state for all seven languages | Speech script, rate, gender |

### Later engine and schema waves

| Wave | Change | Gate |
|---|---|---|
| E1 | Introduction, choice, missing letter, and guided typing that do not write attempts | No SRS write in the prototype |
| E2 | Practice-record contract from section 10 | Separate review before any sync field |
| E3 | Sentence levels and expandable grammar, using validated content | Multiple valid answers reviewed before use |
| E4 | Normal and Slow by passing a rate into the existing Windows provider | No new speech vendor |

**First implementation candidate:** V1, then V2. Today is the accepted home. It already has a pure view model.

**Waits outside these waves**

- Mascot, illustration, and motion.
- A new UI toolkit.
- Changes to ScreenGuard, emergency-code storage, or `StudySession` completion.
- A paid or cloud speech provider.
- A Grammar Library browser before validated content exists.
- Reopening Phase 18.

## 13. Review gate

R1 is the review artifact. Visual wave V1 is the only implementation candidate after acceptance. Engine waves stay gated.

Return tag: `APP_19D1_REDESIGN_SPEC_R1_READY_FOR_REVIEW`.
