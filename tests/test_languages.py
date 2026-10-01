"""Canonical study-language registry."""

import languages


def test_seven_supported_codes():
    assert languages.codes() == ["nl", "en", "fr", "de", "es", "it", "pt"]


def test_default_study_code_is_nl():
    assert languages.default_study_code() == "nl"
    assert languages.default_language().code == "nl"


def test_get_language_valid():
    french = languages.get_language("fr")
    assert french is not None
    assert french.code == "fr"
    assert french.name_en == "French"


def test_get_language_unsupported_is_none():
    assert languages.get_language("xx") is None
    assert not languages.is_supported_language("xx")


def test_resolve_language_falls_back_to_default():
    assert languages.resolve_language("xx").code == languages.default_study_code()


def test_get_compat_dict_falls_back():
    profile = languages.get("xx")
    assert profile["name_en"] == languages.default_language().name_en


def test_nl_articles_and_fr_elisions():
    nl = languages.get_language("nl")
    fr = languages.get_language("fr")
    assert "de" in nl.articles and "het" in nl.articles
    assert "l'" in fr.elisions


def test_native_not_mixed_into_study_registry():
    assert "vi" not in languages.codes()


def test_languages_mapping_compat_labels():
    assert languages.LANGUAGES["de"]["label"] == languages.get_language("de").label
