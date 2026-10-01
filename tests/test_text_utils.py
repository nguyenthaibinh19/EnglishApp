"""Answer matching and text helpers — behavior must stay identical."""

import text_utils


def test_exact_and_article_stripped():
    entry = {"nl": "de fiets", "vi": "xe đạp", "alt": ["rijwiel"]}
    assert text_utils.match_answer("de fiets", entry)[0] == "exact"
    assert text_utils.match_answer("fiets", entry)[0] == "exact"
    assert text_utils.match_answer("  De Fiets ", entry)[0] == "exact"
    assert text_utils.match_answer("rijwiel", entry)[0] == "exact"


def test_near_typo_and_wrong():
    entry = {"nl": "de fiets", "vi": "xe đạp"}
    assert text_utils.match_answer("de fietz", entry)[0] == "near"
    assert text_utils.match_answer("het huis", entry)[0] == "wrong"


def test_accent_fold_near():
    accent = {"nl": "één", "vi": "một"}
    assert text_utils.match_answer("een", accent)[0] == "near"


def test_strip_pos_tag():
    tagged = {"nl": "lopen (ww)", "vi": "đi bộ"}
    assert text_utils.match_answer("lopen", tagged)[0] == "exact"


def test_short_word_no_typo_leniency():
    short = {"nl": "kat", "vi": "con mèo"}
    assert text_utils.match_answer("kan", short)[0] == "wrong"


def test_french_article_and_elision():
    french = {"word": "la maison", "vi": "ngôi nhà"}
    assert text_utils.match_answer("maison", french, articles=("la", "le"))[0] == "exact"
    school = {"word": "l'école", "vi": "trường học"}
    assert text_utils.match_answer("ecole", school, elisions=("l'",))[0] in ("exact", "near")


def test_sentence_around():
    passage = "De fiets is rood. Het huis is groot!"
    assert text_utils.sentence_around(passage, passage.index("huis")) == "Het huis is groot!"
    assert text_utils.sentence_around(passage, 3) == "De fiets is rood."
