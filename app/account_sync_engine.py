"""Background account sync worker (runs off the Tkinter UI thread)."""

from __future__ import annotations

import random
import threading
import time
from typing import Callable, Optional

from account_local_store import (
    OUTBOX_KIND_PROGRESS,
    OUTBOX_KIND_VOCAB_DELETE,
    OUTBOX_KIND_VOCAB_PUT,
    AccountLocalConflict,
    AccountLocalStore,
    SyncStatusSnapshot,
)
from account_sync_client import (
    AccountSyncClient,
    SyncClientError,
    SyncConflictClientError,
    SyncOfflineError,
)

StatusCallback = Callable[[SyncStatusSnapshot], None]


class AccountSyncEngine:
    """Push/pull vocabulary and progress for one signed-in account."""

    def __init__(
        self,
        store: AccountLocalStore,
        client: AccountSyncClient,
        *,
        poll_seconds: float = 60.0,
        on_status: Optional[StatusCallback] = None,
    ):
        self.store = store
        self.client = client
        self.poll_seconds = max(5.0, float(poll_seconds))
        self.on_status = on_status
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._backoff = 1.0
        self._last_status: Optional[SyncStatusSnapshot] = None

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name=f"account-sync-{self.store.user_id}",
                daemon=True,
            )
            self._thread.start()
        self.notify()

    def stop(self, *, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        self.store.close()

    def notify(self) -> None:
        """Wake the worker after a local mutation or reconnect."""
        self._wake.set()

    def status(self) -> SyncStatusSnapshot:
        return self.store.status()

    def sync_once(self) -> SyncStatusSnapshot:
        """Run one full push/pull cycle (tests and local demo)."""
        try:
            # Vocabulary: pull first so identical remote tips can clear lost acks,
            # and divergent remote edits become explicit conflicts before any push.
            self._pull_vocabulary()
            self._push_vocabulary()
            self._push_progress()
            self._pull_progress()
            self._sync_preferences()
            self.store.set_offline(False)
            self._backoff = 1.0
        except SyncOfflineError:
            self.store.set_offline(True)
            self._backoff = min(self._backoff * 2.0, 60.0)
        except SyncConflictClientError as error:
            self.store.mark_conflict("http", str(error))
        except AccountLocalConflict as error:
            self.store.mark_conflict("local", str(error))
        except SyncClientError as error:
            # Keep pending; do not treat validation/auth as offline forever.
            if error.status in {401, 403}:
                self.store.mark_conflict("auth", str(error))
            elif error.status is None or error.status >= 500:
                self.store.set_offline(True)
        snapshot = self.store.status()
        self._last_status = snapshot
        if self.on_status is not None:
            self.on_status(snapshot)
        return snapshot

    def _run(self) -> None:
        while not self._stop.is_set():
            self.sync_once()
            wait = self.poll_seconds
            if self.store.status().offline:
                wait = min(self.poll_seconds, self._backoff + random.uniform(0, 0.5))
            self._wake.wait(timeout=wait)
            self._wake.clear()

    def _push_vocabulary(self) -> None:
        # Snapshot then handle rows superseded while the HTTP call ran.
        for item in list(self.store.pending_outbox(OUTBOX_KIND_VOCAB_PUT)):
            if not self.store.is_outbox_pending(item["operation_id"]):
                continue
            record = self.client.put_vocabulary(item["payload"])
            if self.store.is_outbox_pending(item["operation_id"]):
                self.store.acknowledge_vocab_outbox(item["operation_id"], record)
            else:
                # In-flight race: user saved Y while X was uploading. Consume X's
                # acceptance without discarding Y or inventing a false conflict.
                self.store.note_accepted_vocab_upload(
                    item["operation_id"], item["payload"], record
                )
        for item in list(self.store.pending_outbox(OUTBOX_KIND_VOCAB_DELETE)):
            if not self.store.is_outbox_pending(item["operation_id"]):
                continue
            record = self.client.delete_vocabulary(item["payload"])
            if self.store.is_outbox_pending(item["operation_id"]):
                self.store.acknowledge_vocab_outbox(item["operation_id"], record)
            else:
                self.store.note_accepted_vocab_upload(
                    item["operation_id"], item["payload"], record
                )

    def _pull_vocabulary(self) -> None:
        while True:
            cursors = self.store.cursors()
            page = self.client.vocabulary_changes(after_cursor=cursors["vocab_cursor"])
            changes = page.get("changes") or []
            next_cursor = int(page.get("next_cursor") or cursors["vocab_cursor"])
            has_more = bool(page.get("has_more"))
            self.store.apply_vocab_changes_page(
                changes, next_cursor=next_cursor, has_more=has_more
            )
            if not has_more:
                break

    def _push_progress(self) -> None:
        for item in self.store.pending_outbox(OUTBOX_KIND_PROGRESS):
            event = item["payload"]
            body = self.client.accept_progress(event)
            self.store.acknowledge_progress_upload(item["event_id"] or item["operation_id"], body)

    def _pull_progress(self) -> None:
        while True:
            cursors = self.store.cursors()
            page = self.client.progress_changes(after_cursor=cursors["progress_cursor"])
            changes = page.get("changes") or []
            next_cursor = int(page.get("next_cursor") or cursors["progress_cursor"])
            has_more = bool(page.get("has_more"))
            self.store.apply_progress_changes_page(
                changes, next_cursor=next_cursor, has_more=has_more
            )
            if not has_more:
                break

    def _sync_preferences(self) -> None:
        from account_prefs import sync_preferences_once

        sync_preferences_once(self.store, self.client)


# Process-wide engine registry for the running Windows app.
_active_engine: Optional[AccountSyncEngine] = None
_active_lock = threading.Lock()


def active_engine() -> Optional[AccountSyncEngine]:
    with _active_lock:
        return _active_engine


def start_for_session(
    *,
    user_id: int,
    token: str,
    base_url: str,
    data_root: Optional[str] = None,
    on_status: Optional[StatusCallback] = None,
    poll_seconds: float = 60.0,
) -> AccountSyncEngine:
    """Replace any previous engine (logout / account switch)."""
    import app_environment

    app_environment.assert_network_writes_allowed(base_url)
    global _active_engine
    with _active_lock:
        if _active_engine is not None:
            _active_engine.stop()
            _active_engine = None
        store = AccountLocalStore(user_id, data_root=data_root)
        client = AccountSyncClient(base_url, token)
        engine = AccountSyncEngine(
            store, client, poll_seconds=poll_seconds, on_status=on_status
        )
        engine.start()
        _active_engine = engine
        return engine


def stop_active() -> None:
    global _active_engine
    with _active_lock:
        if _active_engine is not None:
            _active_engine.stop()
            _active_engine = None


def notify_local_change() -> None:
    engine = active_engine()
    if engine is not None:
        engine.notify()


def current_status_label() -> str:
    engine = active_engine()
    if engine is None:
        return ""
    return engine.status().status
