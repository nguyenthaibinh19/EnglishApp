"""Answer matching and text helpers — behavior must stay identical."""

import config
import languages
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


def _use_global_language(monkeypatch, code):
    profile = languages.get_language(code).as_profile(include_code=True)

    def active():
        return code

    def current():
        return profile

    monkeypatch.setattr(config, "active_code", active)
    monkeypatch.setattr(config, "current_language", current)


def test_legacy_dutch_article_ignores_other_global_language(monkeypatch):
    entry = {"nl": "de fiets", "vi": "xe đạp", "alt": ["rijwiel"]}
    for code in ("en", "fr", "de"):
        _use_global_language(monkeypatch, code)
        assert text_utils.match_answer("fiets", entry)[0] == "exact"
        assert text_utils.match_answer("de fiets", entry)[0] == "exact"
        assert text_utils.match_answer("rijwiel", entry)[0] == "exact"


def test_legacy_english_article_ignores_dutch_settings(monkeypatch):
    _use_global_language(monkeypatch, "nl")
    entry = {"en": "the house", "vi": "ngôi nhà"}
    assert text_utils.match_answer("house", entry)[0] == "exact"
    assert text_utils.match_answer("the house", entry)[0] == "exact"
    assert text_utils.match_answer("fiets", {"en": "the house"})[0] == "wrong"


def test_explicit_language_code_beats_legacy_key_and_global_settings(monkeypatch):
    _use_global_language(monkeypatch, "en")
    dutch = {"nl": "de fiets"}
    assert text_utils.match_answer("fiets", dutch, language_code="de")[0] == "wrong"
    assert text_utils.match_answer("de fiets", dutch, language_code="de")[0] == "exact"
    german = {"word": "das Haus", "vi": "ngôi nhà"}
    assert text_utils.match_answer("Haus", german, language_code="de")[0] == "exact"
    assert text_utils.match_answer("Haus", german, language_code="en")[0] == "wrong"
    assert text_utils.match_answer("das Haus", german, language_code="en")[0] == "exact"


def test_french_language_code_covers_articles_and_elisions(monkeypatch):
    _use_global_language(monkeypatch, "en")
    house = {"word": "la maison", "vi": "ngôi nhà"}
    assert text_utils.match_answer("maison", house, language_code="fr")[0] == "exact"
    school = {"word": "l'école", "vi": "trường học"}
    assert text_utils.match_answer("école", school, language_code="fr")[0] == "exact"
    assert text_utils.match_answer("ecole", school, language_code="fr")[0] == "near"


def test_explicit_articles_and_elisions_still_win(monkeypatch):
    _use_global_language(monkeypatch, "de")
    french = {"word": "la maison"}
    assert text_utils.match_answer("maison", french, articles=("la", "le"), language_code="de")[0] == "exact"
    school = {"word": "l'école"}
    assert text_utils.match_answer("ecole", school, elisions=("l'",), language_code="de")[0] in ("exact", "near")


def test_missing_article_and_unrelated_first_token(monkeypatch):
    _use_global_language(monkeypatch, "fr")
    bare = {"nl": "fiets", "vi": "xe đạp"}
    assert text_utils.match_answer("fiets", bare)[0] == "exact"
    assert text_utils.match_answer("de fiets", bare)[0] == "wrong"
    english_view = {"word": "het huis"}
    assert text_utils.match_answer("huis", english_view, language_code="en")[0] == "wrong"
    assert text_utils.match_answer("het huis", english_view, language_code="en")[0] == "exact"


def test_accent_near_and_short_typo_follow_entry_language(monkeypatch):
    _use_global_language(monkeypatch, "en")
    assert text_utils.match_answer("een", {"nl": "één"})[0] == "near"
    assert text_utils.match_answer("fietz", {"nl": "de fiets"})[0] == "near"
    assert text_utils.match_answer("kan", {"nl": "kat"})[0] == "wrong"
    assert text_utils.match_answer("Haus", {"word": "das Haus"}, language_code="de")[0] == "exact"


def test_sentence_around():
    passage = "De fiets is rood. Het huis is groot!"
    assert text_utils.sentence_around(passage, passage.index("huis")) == "Het huis is groot!"
    assert text_utils.sentence_around(passage, 3) == "De fiets is rood."
