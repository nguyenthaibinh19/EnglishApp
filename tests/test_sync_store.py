"""Phase 18A — Account Cloud Sync foundation (vocabulary entities only)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

import sync_store
from sync_store import (
    SyncConflictError,
    SyncSchemaError,
    SyncValidationError,
    connect,
    delete_vocabulary,
    get_vocabulary,
    init_schema,
    list_vocabulary_changes,
    put_vocabulary,
    schema_version,
)


VOCAB_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VOCAB_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _db(tmp_path: Path) -> sqlite3.Connection:
    path = tmp_path / "study_sync.db"
    return connect(str(path))


def _payload(vocab_id: str = VOCAB_A, word: str = "huis", meaning: str = "house", **extra):
    data = {"id": vocab_id, "word": word, "meaning": meaning}
    data.update(extra)
    return data


def test_create_new_user_vocabulary_record(tmp_path):
    conn = _db(tmp_path)
    record = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="op-create-1",
    )
    assert record.revision == 1
    assert record.deleted is False
    assert record.payload["word"] == "huis"
    assert record.payload["meaning"] == "house"
    assert record.payload["id"] == VOCAB_A
    assert "vi" not in record.payload
    loaded = get_vocabulary(
        conn, user_id=1, language_code="nl", vocab_id=VOCAB_A
    )
    assert loaded is not None
    assert loaded.revision == 1
    assert loaded.change_cursor == record.change_cursor


def test_update_with_matching_revision(tmp_path):
    conn = _db(tmp_path)
    first = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="op-1",
    )
    second = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(meaning="ngôi nhà"),
        expected_revision=first.revision,
        operation_id="op-2",
    )
    assert second.revision == 2
    assert second.payload["meaning"] == "ngôi nhà"
    assert second.payload["id"] == VOCAB_A
    assert second.change_cursor > first.change_cursor


def test_concurrent_update_with_stale_revision(tmp_path):
    conn = _db(tmp_path)
    put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="op-1",
    )
    put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(meaning="house v2"),
        expected_revision=1,
        operation_id="op-2",
    )
    with pytest.raises(SyncConflictError) as raised:
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(meaning="stale writer"),
            expected_revision=1,
            operation_id="op-stale",
        )
    assert raised.value.current is not None
    assert raised.value.current.revision == 2
    assert raised.value.current.payload["meaning"] == "house v2"
    # No mutation from the stale write.
    current = get_vocabulary(conn, user_id=1, language_code="nl", vocab_id=VOCAB_A)
    assert current.payload["meaning"] == "house v2"
    assert current.revision == 2


def test_two_users_same_vocabulary_uuid_isolated(tmp_path):
    conn = _db(tmp_path)
    a = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(meaning="user1"),
        expected_revision=0,
        operation_id="u1-create",
    )
    b = put_vocabulary(
        conn,
        user_id=2,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(meaning="user2"),
        expected_revision=0,
        operation_id="u2-create",
    )
    assert a.payload["meaning"] == "user1"
    assert b.payload["meaning"] == "user2"
    assert get_vocabulary(conn, user_id=1, language_code="nl", vocab_id=VOCAB_A).payload[
        "meaning"
    ] == "user1"
    assert get_vocabulary(conn, user_id=2, language_code="nl", vocab_id=VOCAB_A).payload[
        "meaning"
    ] == "user2"


def test_different_study_languages_isolated(tmp_path):
    conn = _db(tmp_path)
    put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(word="huis", meaning="house"),
        expected_revision=0,
        operation_id="nl-1",
    )
    put_vocabulary(
        conn,
        user_id=1,
        language_code="en",
        vocab_id=VOCAB_A,
        payload=_payload(word="house", meaning="ngôi nhà"),
        expected_revision=0,
        operation_id="en-1",
    )
    nl = get_vocabulary(conn, user_id=1, language_code="nl", vocab_id=VOCAB_A)
    en = get_vocabulary(conn, user_id=1, language_code="en", vocab_id=VOCAB_A)
    assert nl.payload["word"] == "huis"
    assert en.payload["word"] == "house"


def test_idempotent_retry_same_operation_id(tmp_path):
    conn = _db(tmp_path)
    payload = _payload()
    first = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=payload,
        expected_revision=0,
        operation_id="same-op",
    )
    retry = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=payload,  # identical mutation → idempotent
        expected_revision=0,
        operation_id="same-op",
    )
    assert retry.revision == first.revision
    assert retry.change_cursor == first.change_cursor
    assert retry.payload["meaning"] == "house"
    changes = list_vocabulary_changes(conn, user_id=1)
    assert len(changes) == 1


def test_delete_tombstone_rejects_resurrection(tmp_path):
    conn = _db(tmp_path)
    created = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="create",
    )
    deleted = delete_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        expected_revision=created.revision,
        operation_id="delete",
    )
    assert deleted.deleted is True
    assert deleted.revision == 2
    loaded = get_vocabulary(conn, user_id=1, language_code="nl", vocab_id=VOCAB_A)
    assert loaded.deleted is True

    with pytest.raises(SyncConflictError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(meaning="resurrect"),
            expected_revision=0,
            operation_id="resurrect-create",
        )
    with pytest.raises(SyncConflictError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(meaning="resurrect"),
            expected_revision=deleted.revision,
            operation_id="resurrect-update",
        )
    assert get_vocabulary(conn, user_id=1, language_code="nl", vocab_id=VOCAB_A).deleted


def test_stale_delete_rejected(tmp_path):
    conn = _db(tmp_path)
    put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="create",
    )
    put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(meaning="v2"),
        expected_revision=1,
        operation_id="update",
    )
    with pytest.raises(SyncConflictError):
        delete_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            expected_revision=1,
            operation_id="stale-delete",
        )


def test_cursor_pagination(tmp_path):
    conn = _db(tmp_path)
    cursors = []
    for index in range(5):
        vid = f"{index:08x}-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        record = put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=vid,
            payload=_payload(vocab_id=vid, word=f"w{index}", meaning=f"m{index}"),
            expected_revision=0,
            operation_id=f"op-{index}",
        )
        cursors.append(record.change_cursor)

    page1 = list_vocabulary_changes(conn, user_id=1, after_cursor=0, limit=2)
    assert [item.cursor for item in page1] == cursors[:2]
    page2 = list_vocabulary_changes(
        conn, user_id=1, after_cursor=page1[-1].cursor, limit=2
    )
    assert [item.cursor for item in page2] == cursors[2:4]
    page3 = list_vocabulary_changes(
        conn, user_id=1, after_cursor=page2[-1].cursor, limit=10
    )
    assert [item.cursor for item in page3] == cursors[4:]

    # Language filter
    put_vocabulary(
        conn,
        user_id=1,
        language_code="de",
        vocab_id=VOCAB_B,
        payload=_payload(vocab_id=VOCAB_B, word="Haus", meaning="house"),
        expected_revision=0,
        operation_id="de-1",
    )
    de_only = list_vocabulary_changes(conn, user_id=1, language_code="de", limit=50)
    assert len(de_only) == 1
    assert de_only[0].language_code == "de"


def test_invalid_uuid_language_payload_rejected(tmp_path):
    conn = _db(tmp_path)
    with pytest.raises(SyncValidationError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id="not-a-uuid",
            payload=_payload(vocab_id="not-a-uuid"),
            expected_revision=0,
            operation_id="bad-id",
        )
    with pytest.raises(SyncValidationError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="xx",
            vocab_id=VOCAB_A,
            payload=_payload(),
            expected_revision=0,
            operation_id="bad-lang",
        )
    with pytest.raises(SyncValidationError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload={"id": VOCAB_A, "word": "huis"},  # missing meaning
            expected_revision=0,
            operation_id="bad-payload",
        )
    with pytest.raises(SyncValidationError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(vocab_id=VOCAB_B),  # id mismatch
            expected_revision=0,
            operation_id="id-mismatch",
        )
    with pytest.raises(SyncValidationError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(api_key="sk-secret"),
            expected_revision=0,
            operation_id="secret",
        )


def test_transaction_rollback_on_error(tmp_path):
    conn = _db(tmp_path)
    put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="seed",
    )
    assert len(list_vocabulary_changes(conn, user_id=1)) == 1

    # Abort entity upsert inside the same transaction as the change insert.
    conn.execute(
        """
        CREATE TRIGGER fail_entities_on_boom
        BEFORE INSERT ON vocabulary_entities
        WHEN NEW.operation_id = 'boom'
        BEGIN
            SELECT RAISE(ABORT, 'simulated failure');
        END
        """
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(meaning="should-not-persist"),
            expected_revision=1,
            operation_id="boom",
        )

    current = get_vocabulary(conn, user_id=1, language_code="nl", vocab_id=VOCAB_A)
    assert current.payload["meaning"] == "house"
    assert current.revision == 1
    assert len(list_vocabulary_changes(conn, user_id=1)) == 1

    conn.execute("DROP TRIGGER fail_entities_on_boom")
    conn.commit()
    # Failed operation_id must not be reserved after rollback.
    retry = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(meaning="after-rollback"),
        expected_revision=1,
        operation_id="boom",
    )
    assert retry.payload["meaning"] == "after-rollback"
    assert retry.revision == 2


def test_schema_init_repeated_without_data_loss(tmp_path):
    path = tmp_path / "study_sync.db"
    conn = connect(str(path))
    put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="keep-me",
    )
    assert schema_version(conn) == sync_store.SCHEMA_VERSION
    init_schema(conn)
    init_schema(conn)
    loaded = get_vocabulary(conn, user_id=1, language_code="nl", vocab_id=VOCAB_A)
    assert loaded is not None
    assert loaded.payload["word"] == "huis"
    assert schema_version(conn) == sync_store.SCHEMA_VERSION


def test_no_writes_to_production_appdata_or_accounts_db(tmp_path, monkeypatch):
    """Sync tests must only touch tmp_path — never AppData or accounts.db."""
    import config

    app_accounts = Path(__file__).resolve().parents[1] / "app" / "accounts.db"
    accounts_mtime = app_accounts.stat().st_mtime if app_accounts.exists() else None

    # Poison data_dir so accidental AppData writes would land in a monitored folder.
    poison = tmp_path / "poison-appdata"
    poison.mkdir()
    monkeypatch.setattr(config, "data_dir", lambda: str(poison))

    conn = _db(tmp_path / "isolated")
    put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="safe",
    )
    conn.close()

    # No files created under poisoned AppData.
    assert list(poison.iterdir()) == []
    # Default package path study_sync.db must not appear from this test.
    package_sync = Path(__file__).resolve().parents[1] / "app" / sync_store.DB_FILE
    # If it somehow existed before, we don't delete it; only assert we didn't
    # rely on creating it via connect(db_path()) without tmp.
    if accounts_mtime is not None:
        assert app_accounts.stat().st_mtime == accounts_mtime


def test_duplicate_create_conflicts(tmp_path):
    conn = _db(tmp_path)
    put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="first",
    )
    with pytest.raises(SyncConflictError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(meaning="other"),
            expected_revision=0,
            operation_id="second-create",
        )


def test_delete_idempotent_retry(tmp_path):
    conn = _db(tmp_path)
    created = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="c",
    )
    first = delete_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        expected_revision=created.revision,
        operation_id="d",
    )
    again = delete_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        expected_revision=created.revision,
        operation_id="d",
    )
    assert again.revision == first.revision
    assert again.deleted is True
    assert len(list_vocabulary_changes(conn, user_id=1)) == 2


def test_legacy_vi_payload_normalized_to_meaning(tmp_path):
    conn = _db(tmp_path)
    record = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload={"id": VOCAB_A, "word": "fiets", "vi": "xe đạp"},
        expected_revision=0,
        operation_id="legacy",
    )
    assert record.payload["meaning"] == "xe đạp"
    assert "vi" not in record.payload


def test_operation_id_reuse_with_different_payload_conflicts(tmp_path):
    conn = _db(tmp_path)
    first = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(meaning="house"),
        expected_revision=0,
        operation_id="shared-op",
    )
    with pytest.raises(SyncConflictError) as raised:
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(meaning="different meaning"),
            expected_revision=0,
            operation_id="shared-op",
        )
    assert "different payload" in str(raised.value).lower()
    assert raised.value.current.revision == first.revision
    # Entity unchanged; no second change row.
    assert get_vocabulary(conn, user_id=1, language_code="nl", vocab_id=VOCAB_A).payload[
        "meaning"
    ] == "house"
    assert len(list_vocabulary_changes(conn, user_id=1)) == 1


def test_operation_id_reuse_for_different_entity_conflicts(tmp_path):
    conn = _db(tmp_path)
    put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="one-op",
    )
    with pytest.raises(SyncConflictError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_B,
            payload=_payload(vocab_id=VOCAB_B, word="fiets", meaning="bike"),
            expected_revision=0,
            operation_id="one-op",
        )
    assert get_vocabulary(conn, user_id=1, language_code="nl", vocab_id=VOCAB_B) is None


def test_sequential_connections_revision_check_inside_transaction(tmp_path):
    """Two connections: second stale update must conflict after the first commits."""
    path = tmp_path / "study_sync.db"
    bootstrap = connect(str(path))
    put_vocabulary(
        bootstrap,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="seed",
    )
    bootstrap.close()

    writer_a = connect(str(path))
    writer_b = connect(str(path))
    won = put_vocabulary(
        writer_a,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(meaning="from-a"),
        expected_revision=1,
        operation_id="a-wins",
    )
    assert won.revision == 2
    with pytest.raises(SyncConflictError) as raised:
        put_vocabulary(
            writer_b,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(meaning="from-b"),
            expected_revision=1,
            operation_id="b-stale",
        )
    assert raised.value.current.revision == 2
    assert get_vocabulary(writer_b, user_id=1, language_code="nl", vocab_id=VOCAB_A).payload[
        "meaning"
    ] == "from-a"


def test_change_cursor_preserves_full_history_including_updates_and_delete(tmp_path):
    conn = _db(tmp_path)
    c1 = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(meaning="v1"),
        expected_revision=0,
        operation_id="h1",
    )
    c2 = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(meaning="v2"),
        expected_revision=1,
        operation_id="h2",
    )
    c3 = delete_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        expected_revision=2,
        operation_id="h3",
    )
    history = list_vocabulary_changes(conn, user_id=1, after_cursor=0, limit=50)
    assert [row.cursor for row in history] == [c1.change_cursor, c2.change_cursor, c3.change_cursor]
    assert [row.revision for row in history] == [1, 2, 3]
    assert [row.deleted for row in history] == [False, False, True]
    assert history[0].payload["meaning"] == "v1"
    assert history[1].payload["meaning"] == "v2"
    # Pagination mid-history still returns later tombstone.
    after_first = list_vocabulary_changes(
        conn, user_id=1, after_cursor=c1.change_cursor, limit=50
    )
    assert [row.operation_id for row in after_first] == ["h2", "h3"]


def test_enrichment_fields_round_trip_and_secret_rejection(tmp_path):
    conn = _db(tmp_path)
    rich = _payload(
        part_of_speech="noun",
        examples=[{"text": "Het huis is groot.", "meaning": "The house is big."}],
        pronunciation={"ipa": "/ɦœys/"},
        forms={"plural": "huizen"},
        note="common",
    )
    record = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=rich,
        expected_revision=0,
        operation_id="enrich-ok",
    )
    assert record.payload["part_of_speech"] == "noun"
    assert record.payload["examples"][0]["text"] == "Het huis is groot."
    assert record.payload["pronunciation"]["ipa"] == "/ɦœys/"
    assert record.payload["forms"]["plural"] == "huizen"
    assert record.payload["note"] == "common"

    with pytest.raises(SyncValidationError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(pronunciation={"ipa": "/x/", "api_key": "sk-nested"}),
            expected_revision=1,
            operation_id="enrich-secret",
        )
    with pytest.raises(SyncValidationError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(
                examples=[{"text": "ok", "meaning": "ok", "api_key": "sk-in-example"}]
            ),
            expected_revision=1,
            operation_id="example-secret",
        )
    # Failed validation must not advance revision or append changes.
    assert get_vocabulary(conn, user_id=1, language_code="nl", vocab_id=VOCAB_A).revision == 1
    assert len(list_vocabulary_changes(conn, user_id=1)) == 1


def test_unsupported_payload_fields_rejected_not_silently_dropped(tmp_path):
    conn = _db(tmp_path)
    with pytest.raises(SyncValidationError) as raised:
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(cefr="A1", synonyms=["home"]),
            expected_revision=0,
            operation_id="unsupported-top",
        )
    assert "Unsupported vocabulary payload fields" in str(raised.value)

    with pytest.raises(SyncValidationError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(examples=[{"text": "x", "meaning": "y", "source": "ai"}]),
            expected_revision=0,
            operation_id="unsupported-example",
        )
    with pytest.raises(SyncValidationError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(forms={"plural": "huizen", "gender": "n"}),
            expected_revision=0,
            operation_id="unsupported-forms",
        )
    assert get_vocabulary(conn, user_id=1, language_code="nl", vocab_id=VOCAB_A) is None
    assert list_vocabulary_changes(conn, user_id=1) == []


def test_operation_id_reuse_with_different_expected_revision_conflicts(tmp_path):
    conn = _db(tmp_path)
    first = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="rev-bound",
    )
    assert first.expected_revision == 0
    with pytest.raises(SyncConflictError) as raised:
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(),
            expected_revision=1,  # same op id, different expected_revision
            operation_id="rev-bound",
        )
    assert "expected_revision" in str(raised.value).lower()
    assert len(list_vocabulary_changes(conn, user_id=1)) == 1


def test_strict_integer_arguments_reject_bool_and_float(tmp_path):
    conn = _db(tmp_path)
    with pytest.raises(SyncValidationError):
        put_vocabulary(
            conn,
            user_id=True,  # noqa: bool is subclass of int
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(),
            expected_revision=0,
            operation_id="bool-user",
        )
    with pytest.raises(SyncValidationError):
        put_vocabulary(
            conn,
            user_id=1,
            language_code="nl",
            vocab_id=VOCAB_A,
            payload=_payload(),
            expected_revision=0.0,  # float
            operation_id="float-rev",
        )
    with pytest.raises(SyncValidationError):
        list_vocabulary_changes(conn, user_id=1, after_cursor=0.5, limit=10)
    with pytest.raises(SyncValidationError):
        list_vocabulary_changes(conn, user_id=1, after_cursor=0, limit=True)


# ---------------------------------------------------------------------------
# Schema migration (v1 → v2) and future-version rejection
# ---------------------------------------------------------------------------


def _create_v1_database(path: Path) -> None:
    """Hand-build a Phase 18A schema v1 DB (no expected_revision column)."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(
            """
            CREATE TABLE sync_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE vocabulary_entities (
                user_id INTEGER NOT NULL,
                language_code TEXT NOT NULL,
                vocab_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT,
                change_cursor INTEGER NOT NULL,
                operation_id TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, language_code, vocab_id)
            );
            CREATE TABLE vocabulary_changes (
                change_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                language_code TEXT NOT NULL,
                vocab_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                deleted INTEGER NOT NULL,
                payload_json TEXT,
                operation_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (user_id, operation_id)
            );
            INSERT INTO sync_meta (key, value) VALUES ('schema_version', '1');
            """
        )
        conn.commit()
    finally:
        conn.close()


def _insert_v1_change(
    path: Path,
    *,
    user_id: int,
    language_code: str,
    vocab_id: str,
    revision: int,
    deleted: int,
    payload: dict,
    operation_id: str,
) -> int:
    import json

    conn = sqlite3.connect(str(path))
    try:
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        cur = conn.execute(
            """
            INSERT INTO vocabulary_changes (
                user_id, language_code, vocab_id, revision, deleted,
                payload_json, operation_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                user_id,
                language_code,
                vocab_id,
                revision,
                deleted,
                payload_json,
                operation_id,
            ),
        )
        change_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO vocabulary_entities (
                user_id, language_code, vocab_id, revision, deleted,
                payload_json, change_cursor, operation_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user_id, language_code, vocab_id) DO UPDATE SET
                revision = excluded.revision,
                deleted = excluded.deleted,
                payload_json = excluded.payload_json,
                change_cursor = excluded.change_cursor,
                operation_id = excluded.operation_id,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                language_code,
                vocab_id,
                revision,
                deleted,
                payload_json,
                change_id,
                operation_id,
            ),
        )
        conn.commit()
        return change_id
    finally:
        conn.close()


def test_fresh_v2_db_initialization(tmp_path):
    path = tmp_path / "fresh.db"
    conn = connect(str(path))
    assert schema_version(conn) == 2
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(vocabulary_changes)").fetchall()
    }
    assert "expected_revision" in cols
    put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="fresh-create",
    )
    record = get_vocabulary(conn, user_id=1, language_code="nl", vocab_id=VOCAB_A)
    assert record.expected_revision == 0
    assert record.revision == 1


def test_v1_to_v2_backfills_create_update_delete_history(tmp_path):
    path = tmp_path / "v1.db"
    _create_v1_database(path)
    create_payload = _payload(meaning="v1")
    update_payload = _payload(meaning="v2")
    _insert_v1_change(
        path,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        revision=1,
        deleted=0,
        payload=create_payload,
        operation_id="op-create",
    )
    _insert_v1_change(
        path,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        revision=2,
        deleted=0,
        payload=update_payload,
        operation_id="op-update",
    )
    _insert_v1_change(
        path,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        revision=3,
        deleted=1,
        payload=update_payload,
        operation_id="op-delete",
    )

    raw = sqlite3.connect(str(path))
    assert raw.execute(
        "SELECT value FROM sync_meta WHERE key='schema_version'"
    ).fetchone()[0] == "1"
    assert "expected_revision" not in {
        row[1] for row in raw.execute("PRAGMA table_info(vocabulary_changes)")
    }
    raw.close()

    conn = connect(str(path))
    assert schema_version(conn) == 2
    changes = list_vocabulary_changes(conn, user_id=1, limit=50)
    assert [c.revision for c in changes] == [1, 2, 3]
    assert [c.expected_revision for c in changes] == [0, 1, 2]
    assert [c.deleted for c in changes] == [False, False, True]
    entity = get_vocabulary(conn, user_id=1, language_code="nl", vocab_id=VOCAB_A)
    assert entity.deleted is True
    assert entity.revision == 3
    assert entity.expected_revision == 2


def test_operation_retry_after_v1_to_v2_migration(tmp_path):
    path = tmp_path / "v1-retry.db"
    _create_v1_database(path)
    payload = _payload(meaning="house")
    _insert_v1_change(
        path,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        revision=1,
        deleted=0,
        payload=payload,
        operation_id="op-create",
    )
    _insert_v1_change(
        path,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        revision=2,
        deleted=0,
        payload=_payload(meaning="updated"),
        operation_id="op-update",
    )

    conn = connect(str(path))
    assert schema_version(conn) == 2
    # Replay original update operation with reconstructed expected_revision=1.
    retry = put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(meaning="updated"),
        expected_revision=1,
        operation_id="op-update",
    )
    assert retry.revision == 2
    assert retry.expected_revision == 1
    assert len(list_vocabulary_changes(conn, user_id=1)) == 2


def test_repeated_migration_is_idempotent(tmp_path):
    path = tmp_path / "v1-repeat.db"
    _create_v1_database(path)
    _insert_v1_change(
        path,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        revision=2,
        deleted=0,
        payload=_payload(),
        operation_id="op-u",
    )
    conn = connect(str(path))
    first = list_vocabulary_changes(conn, user_id=1)[0]
    assert first.expected_revision == 1
    init_schema(conn)
    init_schema(conn)
    assert schema_version(conn) == 2
    again = list_vocabulary_changes(conn, user_id=1)[0]
    assert again.expected_revision == 1
    assert again.revision == first.revision
    assert again.operation_id == first.operation_id


def _as_tuples(rows) -> list:
    return [tuple(row) for row in rows]


def _db_integrity_snapshot(connection: sqlite3.Connection) -> dict:
    """Capture objects / pragma / meta / user rows for future-schema regressions."""
    master = _as_tuples(
        connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
    )
    pragma_sv = connection.execute("PRAGMA schema_version").fetchone()[0]
    meta = _as_tuples(
        connection.execute(
            "SELECT key, value FROM sync_meta ORDER BY key"
        ).fetchall()
    )
    entities = _as_tuples(
        connection.execute(
            "SELECT user_id, language_code, vocab_id, revision, deleted, "
            "payload_json, change_cursor, operation_id, expected_revision "
            "FROM vocabulary_entities ORDER BY user_id, language_code, vocab_id"
        ).fetchall()
    )
    changes = _as_tuples(
        connection.execute(
            "SELECT change_id, user_id, language_code, vocab_id, revision, deleted, "
            "payload_json, operation_id, expected_revision "
            "FROM vocabulary_changes ORDER BY change_id"
        ).fetchall()
    )
    indexes = {
        row[1]
        for row in connection.execute(
            "SELECT type, name FROM sqlite_master WHERE type = 'index'"
        ).fetchall()
    }
    return {
        "master": master,
        "pragma_schema_version": pragma_sv,
        "meta": meta,
        "entities": entities,
        "changes": changes,
        "indexes": indexes,
    }


def _prepare_future_v3_db(path: Path, *, drop_vocab_indexes: bool = False) -> dict:
    """Build a supported v2 DB, label it schema_version=3, return baseline snapshot."""
    conn = connect(str(path))
    put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="keep",
    )
    if drop_vocab_indexes:
        conn.execute("DROP INDEX IF EXISTS idx_vocab_changes_user_cursor")
        conn.execute("DROP INDEX IF EXISTS idx_vocab_changes_user_lang_cursor")
    conn.execute(
        "UPDATE sync_meta SET value = '3' WHERE key = 'schema_version'"
    )
    conn.commit()
    snapshot = _db_integrity_snapshot(conn)
    conn.close()
    return snapshot


def test_future_schema_v3_connect_rejects_without_mutation(tmp_path):
    path = tmp_path / "future-connect.db"
    before = _prepare_future_v3_db(path)

    with pytest.raises(SyncSchemaError) as raised:
        connect(str(path))
    assert "newer than supported" in str(raised.value).lower()

    probe = sqlite3.connect(str(path))
    try:
        after = _db_integrity_snapshot(probe)
    finally:
        probe.close()
    assert after == before
    assert after["meta"] == [("schema_version", "3")]


def test_future_schema_v3_init_schema_tuple_connection_rejects_without_mutation(
    tmp_path,
):
    """Direct init_schema on default tuple rows must not mutate a future DB."""
    path = tmp_path / "future-tuple.db"
    before = _prepare_future_v3_db(path)

    raw = sqlite3.connect(str(path))  # default row_factory → tuples
    assert raw.row_factory is None
    try:
        with pytest.raises(SyncSchemaError) as raised:
            init_schema(raw)
        assert "newer than supported" in str(raised.value).lower()
        after = _db_integrity_snapshot(raw)
    finally:
        raw.close()
    assert after == before
    assert after["meta"] == [("schema_version", "3")]


def test_future_schema_v3_missing_indexes_are_not_created(tmp_path):
    path = tmp_path / "future-no-idx.db"
    before = _prepare_future_v3_db(path, drop_vocab_indexes=True)
    assert "idx_vocab_changes_user_cursor" not in before["indexes"]
    assert "idx_vocab_changes_user_lang_cursor" not in before["indexes"]

    with pytest.raises(SyncSchemaError):
        connect(str(path))

    raw = sqlite3.connect(str(path))
    try:
        with pytest.raises(SyncSchemaError):
            init_schema(raw)
        after = _db_integrity_snapshot(raw)
    finally:
        raw.close()

    assert after == before
    assert "idx_vocab_changes_user_cursor" not in after["indexes"]
    assert "idx_vocab_changes_user_lang_cursor" not in after["indexes"]


@pytest.mark.parametrize(
    "meta_setup",
    [
        "missing_key",
        "empty",
        "non_int",
        "negative",
    ],
)
def test_malformed_schema_metadata_rejected_without_mutation(tmp_path, meta_setup):
    path = tmp_path / f"malformed-{meta_setup}.db"
    conn = connect(str(path))
    put_vocabulary(
        conn,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        payload=_payload(),
        expected_revision=0,
        operation_id="keep",
    )
    if meta_setup == "missing_key":
        conn.execute("DELETE FROM sync_meta WHERE key = 'schema_version'")
    elif meta_setup == "empty":
        conn.execute(
            "UPDATE sync_meta SET value = '' WHERE key = 'schema_version'"
        )
    elif meta_setup == "non_int":
        conn.execute(
            "UPDATE sync_meta SET value = 'not-a-version' WHERE key = 'schema_version'"
        )
    else:
        conn.execute(
            "UPDATE sync_meta SET value = '-1' WHERE key = 'schema_version'"
        )
    conn.commit()
    before = _db_integrity_snapshot(conn)
    conn.close()

    with pytest.raises(SyncSchemaError):
        connect(str(path))

    raw = sqlite3.connect(str(path))
    try:
        with pytest.raises(SyncSchemaError):
            init_schema(raw)
        after = _db_integrity_snapshot(raw)
    finally:
        raw.close()
    assert after == before


def test_failed_migration_does_not_upgrade_schema_version(tmp_path):
    path = tmp_path / "v1-fail.db"
    _create_v1_database(path)
    _insert_v1_change(
        path,
        user_id=1,
        language_code="nl",
        vocab_id=VOCAB_A,
        revision=2,
        deleted=0,
        payload=_payload(),
        operation_id="op-u",
    )

    # Open raw connection, install abort trigger, then run migration.
    raw = sqlite3.connect(str(path))
    raw.execute(
        """
        CREATE TRIGGER fail_v2_backfill
        BEFORE UPDATE OF expected_revision ON vocabulary_changes
        BEGIN
            SELECT RAISE(ABORT, 'simulated migration failure');
        END
        """
    )
    # expected_revision column must exist for UPDATE OF to bind — add it as v1→v2 would,
    # but leave schema_version at 1 so init_schema still attempts backfill.
    raw.execute(
        "ALTER TABLE vocabulary_changes ADD COLUMN expected_revision INTEGER NOT NULL DEFAULT 0"
    )
    raw.execute(
        "ALTER TABLE vocabulary_entities ADD COLUMN expected_revision INTEGER NOT NULL DEFAULT 0"
    )
    raw.commit()

    with pytest.raises(sqlite3.IntegrityError):
        init_schema(raw)
    version = raw.execute(
        "SELECT value FROM sync_meta WHERE key='schema_version'"
    ).fetchone()[0]
    assert version == "1"
    # DEFAULT 0 remains — not falsely marked as migrated v2.
    row = raw.execute(
        "SELECT expected_revision, revision FROM vocabulary_changes WHERE operation_id='op-u'"
    ).fetchone()
    assert row[0] == 0
    assert row[1] == 2
    raw.close()
