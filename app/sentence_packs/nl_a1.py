"""Curated Dutch A1 sentence pack for Phase 19.5A.

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
        "Example: Ik drink water. The finite verb stays in second position "
        "in this beginner pattern."
    ),
    full_vi=(
        "Câu chính cơ bản tiếng Hà Lan theo Chủ ngữ–Động từ–Tân ngữ (SVO). "
        "Ví dụ: Ik drink water. Động từ chia ngôi đứng ở vị trí thứ hai "
        "trong mẫu sơ cấp này."
    ),
    examples=("Ik drink water.", "Zij leest een boek."),
    provenance="Author-curated from standard A1 SVO teaching pattern; LanguageGuard 19.5A.",
    review_status=REVIEW_PENDING_EXPERT,
)

RULE_PRESENT = GrammarRule(
    rule_id="nl-a1-present-conjugation",
    language_code="nl",
    cefr="A1",
    title_en="Present-tense verb with hij/zij/het",
    title_vi="Động từ hiện tại với hij/zij/het",
    beginner_en="With hij, zij, or het, most verbs add -t in the present (hij drinkt).",
    beginner_vi="Với hij, zij hoặc het, hầu hết động từ thêm -t ở hiện tại (hij drinkt).",
    full_en=(
        "Dutch present singular: ik + stem, jij/u + stem+t (often), "
        "hij/zij/het + stem+t. Stem drink → hij drinkt. Do not use the "
        "infinitive drinken as the finite form here."
    ),
    full_vi=(
        "Hiện tại số ít: ik + gốc, jij/u + gốc+t (thường gặp), "
        "hij/zij/het + gốc+t. Gốc drink → hij drinkt. Không dùng nguyên mẫu "
        "drinken làm dạng chia ngôi ở đây."
    ),
    examples=("Ik drink water.", "Hij drinkt water."),
    provenance="Author-curated A1 present conjugation note; LanguageGuard 19.5A.",
    review_status=REVIEW_PENDING_EXPERT,
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
    examples=("het boek", "een fiets", "de fiets"),
    provenance="Author-curated A1 article note; LanguageGuard 19.5A.",
    review_status=REVIEW_PENDING_EXPERT,
)

_CHECKLIST = (
    "Each exercise has a stable id and content_version=1.",
    "Accepted answers are explicitly listed; no vocabulary-example auto-import.",
    "Multiple valid answers are listed where intended (punctuation / word-order variants).",
    "Grammar rule ids resolve inside this pack.",
    "Beginner + fuller explanations exist in English and Vietnamese.",
    "Provenance and review_status recorded; pending_expert_validation means no external linguist sign-off.",
    "All four sentence levels are present for Dutch A1.",
    "No production learner data or live AI output was used as an answer key.",
)

EX_WORD_BANK = SentenceExercise(
    exercise_id="nl-a1-wb-drink-water",
    language_code="nl",
    cefr="A1",
    kind=KIND_WORD_BANK,
    support_level=SUPPORT_ASSISTED,
    prompt="Arrange the words: I drink water.",
    translation_en="I drink water.",
    translation_vi="Tôi uống nước.",
    accepted_answers=(
        "Ik drink water.",
        "Ik drink water",
    ),
    target_lemma="drinken",
    word_bank=("Ik", "drink", "water", "."),
    grammar_rule_ids=("nl-a1-svo-main",),
    components=(
        SentenceComponent(ROLE_SUBJECT, "Ik"),
        SentenceComponent(ROLE_VERB, "drink"),
        SentenceComponent(ROLE_OBJECT, "water"),
    ),
    provenance="Author-curated SVO arrangement; LanguageGuard 19.5A.",
    review_status=REVIEW_CURATED_AUTHOR,
    notes="Period token optional in accepted set.",
)

EX_FILL_BLANK = SentenceExercise(
    exercise_id="nl-a1-fb-hij-drinkt",
    language_code="nl",
    cefr="A1",
    kind=KIND_FILL_BLANK,
    support_level=SUPPORT_ASSISTED,
    prompt="Complete: He drinks water.",
    translation_en="He drinks water.",
    translation_vi="Anh ấy uống nước.",
    accepted_answers=(
        "Hij drinkt water.",
        "Hij drinkt water",
        "drinkt",
    ),
    target_lemma="drinken",
    blank_sentence="Hij ___ water.",
    grammar_rule_ids=("nl-a1-present-conjugation", "nl-a1-svo-main"),
    components=(
        SentenceComponent(ROLE_SUBJECT, "Hij"),
        SentenceComponent(ROLE_VERB, "drinkt"),
        SentenceComponent(ROLE_OBJECT, "water"),
    ),
    provenance="Author-curated conjugation blank; LanguageGuard 19.5A.",
    review_status=REVIEW_CURATED_AUTHOR,
    notes="Accept full sentence or the missing finite verb alone.",
)

EX_GUIDED = SentenceExercise(
    exercise_id="nl-a1-gw-leest-boek",
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
    provenance="Author-curated guided SVO + article; LanguageGuard 19.5A.",
    review_status=REVIEW_CURATED_AUTHOR,
    notes="Zij/Ze both accepted as reviewed variants.",
)

EX_INDEPENDENT = SentenceExercise(
    exercise_id="nl-a1-iw-koop-fiets",
    language_code="nl",
    cefr="A1",
    kind=KIND_INDEPENDENT_WRITING,
    support_level=SUPPORT_INDEPENDENT,
    prompt="Write a Dutch sentence: I buy a bicycle.",
    translation_en="I buy a bicycle.",
    translation_vi="Tôi mua một chiếc xe đạp.",
    accepted_answers=(
        "Ik koop een fiets.",
        "Ik koop een fiets",
        "Ik koop een fiets!",
    ),
    target_lemma="kopen",
    grammar_rule_ids=("nl-a1-svo-main", "nl-a1-articles"),
    components=(
        SentenceComponent(ROLE_SUBJECT, "Ik"),
        SentenceComponent(ROLE_VERB, "koop"),
        SentenceComponent(ROLE_ARTICLE, "een"),
        SentenceComponent(ROLE_OBJECT, "fiets"),
    ),
    provenance="Author-curated independent writing; LanguageGuard 19.5A.",
    review_status=REVIEW_CURATED_AUTHOR,
    notes="Answers outside this set may use the AI adapter as provisional only.",
)

# Extra bank item for a clear wrong-order demo (same ladder family).
EX_WORD_BANK_BOOK = SentenceExercise(
    exercise_id="nl-a1-wb-leest-boek",
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
    provenance="Author-curated second arrangement; LanguageGuard 19.5A.",
    review_status=REVIEW_CURATED_AUTHOR,
)

NL_A1_PACK = SentencePack(
    pack_id="nl-a1-sentence-v1",
    language_code="nl",
    cefr="A1",
    title="Dutch A1 sentence practice",
    exercises=(
        EX_WORD_BANK,
        EX_WORD_BANK_BOOK,
        EX_FILL_BLANK,
        EX_GUIDED,
        EX_INDEPENDENT,
    ),
    rules=(RULE_SVO, RULE_PRESENT, RULE_ARTICLE),
    content_version=CONTENT_FORMAT_VERSION,
    review_checklist=_CHECKLIST,
    provenance=(
        "LanguageGuard Phase 19.5A curated pack. Author checklist review only. "
        "Pending independent expert linguistic validation."
    ),
)
