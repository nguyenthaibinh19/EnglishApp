"""Curated Dutch A1 sentence pack for Phase 19.5A / R1.

Review status: curated_author. This pack was authored for the LanguageGuard
demo and checklist-reviewed for internal consistency. It has not received
independent expert linguistic certification. Do not claim expert validation.
"""

from __future__ import annotations

from sentence_content import (
    CONTENT_FORMAT_VERSION,
    KIND_FILL_BLANK,
    KIND_GUIDED_WRITING,
    KIND_INDEPENDENT_WRITING,
    KIND_WORD_BANK,
    REVIEW_CURATED_AUTHOR,
    REVIEW_PENDING_EXPERT,
    ROLE_ARTICLE,
    ROLE_OBJECT,
    ROLE_SUBJECT,
    ROLE_VERB,
    SUPPORT_ASSISTED,
    SUPPORT_INDEPENDENT,
    GrammarRule,
    SentenceComponent,
    SentenceExercise,
    SentencePack,
)

FAMILY_LEZEN = "nl-a1-family-lezen-boek"

RULE_SVO = GrammarRule(
    rule_id="nl-a1-svo-main",
    language_code="nl",
    cefr="A1",
    title_en="Dutch main-clause word order",
    title_vi="Trật tự câu chính tiếng Hà Lan",
    beginner_en="In a simple sentence, put the subject first, then the verb, then the object.",
    beginner_vi="Trong câu đơn, đặt chủ ngữ trước, rồi động từ, rồi tân ngữ.",
    full_en=(
        "A basic Dutch main clause follows Subject–Verb–Object (SVO). "
        "Example: Zij leest een boek. The finite verb stays in second position "
        "in this beginner pattern."
    ),
    full_vi=(
        "Câu chính cơ bản tiếng Hà Lan theo Chủ ngữ–Động từ–Tân ngữ (SVO). "
        "Ví dụ: Zij leest een boek. Động từ chia ngôi đứng ở vị trí thứ hai "
        "trong mẫu sơ cấp này."
    ),
    examples=("Zij leest een boek.", "Ik drink water."),
    provenance="Author-curated from standard A1 SVO teaching pattern; LanguageGuard 19.5A.",
    review_status=REVIEW_PENDING_EXPERT,
    topics=("svo", "word-order", "word_order"),
)

RULE_PRESENT = GrammarRule(
    rule_id="nl-a1-present-conjugation",
    language_code="nl",
    cefr="A1",
    title_en="Present-tense verb with hij/zij/het",
    title_vi="Động từ hiện tại với hij/zij/het",
    beginner_en="With hij, zij, or het, most verbs add -t in the present (zij leest).",
    beginner_vi="Với hij, zij hoặc het, hầu hết động từ thêm -t ở hiện tại (zij leest).",
    full_en=(
        "Dutch present singular: ik + stem, jij/u + stem+t (often), "
        "hij/zij/het + stem+t. Stem lees → zij leest. Do not use the "
        "infinitive lezen as the finite form here."
    ),
    full_vi=(
        "Hiện tại số ít: ik + gốc, jij/u + gốc+t (thường gặp), "
        "hij/zij/het + gốc+t. Gốc lees → zij leest. Không dùng nguyên mẫu "
        "lezen làm dạng chia ngôi ở đây."
    ),
    examples=("Zij leest een boek.", "Hij leest een boek."),
    provenance="Author-curated A1 present conjugation note; LanguageGuard 19.5A.",
    review_status=REVIEW_PENDING_EXPERT,
    topics=("present-conjugation", "conjugation"),
)

RULE_ARTICLE = GrammarRule(
    rule_id="nl-a1-articles",
    language_code="nl",
    cefr="A1",
    title_en="Basic Dutch articles",
    title_vi="Mạo từ cơ bản tiếng Hà Lan",
    beginner_en="Use de or het with a noun you already know. Een means a/an.",
    beginner_vi="Dùng de hoặc het với danh từ đã biết. Een nghĩa là một.",
    full_en=(
        "Common nouns take de or het. Beginners learn the article with the noun "
        "(het boek, de fiets). Een is the indefinite article."
    ),
    full_vi=(
        "Danh từ thường đi với de hoặc het. Người mới học ghi nhớ mạo từ cùng "
        "danh từ (het boek, de fiets). Een là mạo từ không xác định."
    ),
    examples=("een boek", "het boek", "een fiets"),
    provenance="Author-curated A1 article note; LanguageGuard 19.5A.",
    review_status=REVIEW_PENDING_EXPERT,
    topics=("articles", "article"),
)

_CHECKLIST = (
    "Each exercise has a stable id, family_id where applicable, and content_version=1.",
    "Accepted answers are explicitly listed; no vocabulary-example auto-import.",
    "Multiple valid answers are listed where intended (punctuation / Zij/Ze variants).",
    "Grammar rule ids resolve inside this pack.",
    "Beginner + fuller explanations exist in English and Vietnamese.",
    "Provenance and review_status recorded; pending_expert_validation means no external linguist sign-off.",
    "At least one family covers all four sentence levels for Dutch A1.",
    "No production learner data or live AI output was used as an answer key.",
)

# Complete four-level family: same learning objective (SVO + present + article).
EX_WB = SentenceExercise(
    exercise_id="nl-a1-wb-leest-boek",
    family_id=FAMILY_LEZEN,
    language_code="nl",
    cefr="A1",
    kind=KIND_WORD_BANK,
    support_level=SUPPORT_ASSISTED,
    prompt="Arrange the words: She reads a book.",
    translation_en="She reads a book.",
    translation_vi="Cô ấy đọc một cuốn sách.",
    accepted_answers=(
        "Zij leest een boek.",
        "Zij leest een boek",
        "Ze leest een boek.",
        "Ze leest een boek",
    ),
    target_lemma="lezen",
    word_bank=("Zij", "leest", "een", "boek", "."),
    grammar_rule_ids=("nl-a1-svo-main", "nl-a1-articles"),
    components=(
        SentenceComponent(ROLE_SUBJECT, "Zij"),
        SentenceComponent(ROLE_VERB, "leest"),
        SentenceComponent(ROLE_ARTICLE, "een"),
        SentenceComponent(ROLE_OBJECT, "boek"),
    ),
    provenance="Author-curated SVO arrangement; LanguageGuard 19.5A R1.",
    review_status=REVIEW_CURATED_AUTHOR,
    learning_objective="Arrange a simple SVO sentence with an indefinite article.",
    notes="Period token optional in accepted set. Zij/Ze both reviewed.",
)

EX_FB = SentenceExercise(
    exercise_id="nl-a1-fb-zij-leest",
    family_id=FAMILY_LEZEN,
    language_code="nl",
    cefr="A1",
    kind=KIND_FILL_BLANK,
    support_level=SUPPORT_ASSISTED,
    prompt="Complete: She reads a book.",
    translation_en="She reads a book.",
    translation_vi="Cô ấy đọc một cuốn sách.",
    accepted_answers=(
        "Zij leest een boek.",
        "Zij leest een boek",
        "Ze leest een boek.",
        "Ze leest een boek",
        "leest",
    ),
    target_lemma="lezen",
    blank_sentence="Zij ___ een boek.",
    grammar_rule_ids=("nl-a1-present-conjugation", "nl-a1-svo-main"),
    components=(
        SentenceComponent(ROLE_SUBJECT, "Zij"),
        SentenceComponent(ROLE_VERB, "leest"),
        SentenceComponent(ROLE_ARTICLE, "een"),
        SentenceComponent(ROLE_OBJECT, "boek"),
    ),
    provenance="Author-curated conjugation blank; LanguageGuard 19.5A R1.",
    review_status=REVIEW_CURATED_AUTHOR,
    learning_objective="Use the present finite form leest with zij.",
    notes="Accept full sentence or the missing finite verb alone.",
)

EX_GW = SentenceExercise(
    exercise_id="nl-a1-gw-leest-boek",
    family_id=FAMILY_LEZEN,
    language_code="nl",
    cefr="A1",
    kind=KIND_GUIDED_WRITING,
    support_level=SUPPORT_ASSISTED,
    prompt="Write: She reads a book.",
    translation_en="She reads a book.",
    translation_vi="Cô ấy đọc một cuốn sách.",
    accepted_answers=(
        "Zij leest een boek.",
        "Zij leest een boek",
        "Ze leest een boek.",
        "Ze leest een boek",
    ),
    target_lemma="lezen",
    grammar_template="Subject + Verb + Article + Object",
    grammar_rule_ids=("nl-a1-svo-main", "nl-a1-articles", "nl-a1-present-conjugation"),
    components=(
        SentenceComponent(ROLE_SUBJECT, "Zij"),
        SentenceComponent(ROLE_VERB, "leest"),
        SentenceComponent(ROLE_ARTICLE, "een"),
        SentenceComponent(ROLE_OBJECT, "boek"),
    ),
    provenance="Author-curated guided SVO + article; LanguageGuard 19.5A R1.",
    review_status=REVIEW_CURATED_AUTHOR,
    learning_objective="Write the full SVO sentence with een + noun.",
    notes="Zij/Ze both accepted as reviewed variants.",
)

EX_IW = SentenceExercise(
    exercise_id="nl-a1-iw-leest-boek",
    family_id=FAMILY_LEZEN,
    language_code="nl",
    cefr="A1",
    kind=KIND_INDEPENDENT_WRITING,
    support_level=SUPPORT_INDEPENDENT,
    prompt="Write a Dutch sentence: She reads a book.",
    translation_en="She reads a book.",
    translation_vi="Cô ấy đọc một cuốn sách.",
    accepted_answers=(
        "Zij leest een boek.",
        "Zij leest een boek",
        "Ze leest een boek.",
        "Ze leest een boek",
        "Zij leest een boek!",
        "Ze leest een boek!",
    ),
    target_lemma="lezen",
    grammar_rule_ids=("nl-a1-svo-main", "nl-a1-articles", "nl-a1-present-conjugation"),
    components=(
        SentenceComponent(ROLE_SUBJECT, "Zij"),
        SentenceComponent(ROLE_VERB, "leest"),
        SentenceComponent(ROLE_ARTICLE, "een"),
        SentenceComponent(ROLE_OBJECT, "boek"),
    ),
    provenance="Author-curated independent writing; LanguageGuard 19.5A R1.",
    review_status=REVIEW_CURATED_AUTHOR,
    learning_objective="Produce the family sentence independently.",
    notes="Answers outside this set may use the AI adapter as provisional only.",
)

NL_A1_PACK = SentencePack(
    pack_id="nl-a1-sentence-v1",
    language_code="nl",
    cefr="A1",
    title="Dutch A1 sentence practice",
    exercises=(EX_WB, EX_FB, EX_GW, EX_IW),
    rules=(RULE_SVO, RULE_PRESENT, RULE_ARTICLE),
    content_version=CONTENT_FORMAT_VERSION,
    review_checklist=_CHECKLIST,
    provenance=(
        "LanguageGuard Phase 19.5A curated pack. Author checklist review only. "
        "Pending independent expert linguistic validation."
    ),
)
