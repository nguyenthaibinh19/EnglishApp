"""Telegram and Brevo senders for the health monitor.

PROVIDER_ACCEPTED means the provider API returned success. It does not prove
that a person received or read the message. Secrets are redacted from logs.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

PROVIDER_ACCEPTED = "PROVIDER_ACCEPTED"
PROVIDER_REJECTED = "PROVIDER_REJECTED"
NOT_SENT = "NOT_SENT"
REDACTED = "[redacted]"

MAX_ATTEMPTS = 3
BUDGET_SECONDS = 10.0


@dataclass(frozen=True)
class ChannelResult:
    """One channel attempt. ``log`` is already redacted."""

    channel: str
    result: str
    http_status: Optional[int]
    attempts: int
    log: str


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: str = ""
    retry_after: float = 0.0


Post = Callable[[str], HttpResponse]


def redact(text: str, secrets: list[str]) -> str:
    """Remove known secrets from ``text``."""
    cleaned = text or ""
    for secret in secrets:
        if secret:
            cleaned = cleaned.replace(secret, REDACTED)
    return cleaned


def deliver(
    channel: str,
    post: Optional[Post],
    text: str,
    *,
    secrets: list[str],
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    budget: float = BUDGET_SECONDS,
) -> ChannelResult:
    """Send with a bounded retry. A missing sender is NOT_SENT and is not acceptance."""
    if post is None:
        return ChannelResult(channel, NOT_SENT, None, 0, f"channel={channel} result={NOT_SENT} attempt=0")
    started = monotonic()
    attempt = 0
    status: Optional[int] = None
    while attempt < MAX_ATTEMPTS:
        remaining = budget - (monotonic() - started)
        if attempt and remaining <= 0:
            break
        attempt += 1
        try:
            response = post(text)
        except Exception as error:
            status = None
            detail = redact(str(error), secrets)
            if attempt >= MAX_ATTEMPTS or budget - (monotonic() - started) <= 0:
                return ChannelResult(
                    channel,
                    PROVIDER_REJECTED,
                    None,
                    attempt,
                    f"channel={channel} result={PROVIDER_REJECTED} http=none attempt={attempt} error={detail}",
                )
            sleep(min(2 ** (attempt - 1), max(0.0, remaining)))
            continue
        status = response.status
        if 200 <= response.status < 300:
            return ChannelResult(
                channel,
                PROVIDER_ACCEPTED,
                response.status,
                attempt,
                f"channel={channel} result={PROVIDER_ACCEPTED} http={response.status} attempt={attempt}",
            )
        if response.status == 429 and attempt < MAX_ATTEMPTS:
            remaining = budget - (monotonic() - started)
            delay = min(max(0.0, response.retry_after), max(0.0, remaining))
            if delay <= 0:
                break
            sleep(delay)
            continue
        if 400 <= response.status < 500:
            return ChannelResult(
                channel,
                PROVIDER_REJECTED,
                response.status,
                attempt,
                f"channel={channel} result={PROVIDER_REJECTED} http={response.status} attempt={attempt}",
            )
        if attempt >= MAX_ATTEMPTS:
            break
        remaining = budget - (monotonic() - started)
        sleep(min(float(2 ** (attempt - 1)), max(0.0, remaining)))
    return ChannelResult(
        channel,
        PROVIDER_REJECTED,
        status,
        attempt,
        f"channel={channel} result={PROVIDER_REJECTED} http={status} attempt={attempt}",
    )


def telegram_post(token: str, chat_id: str, opener=None) -> Post:
    """Build a Telegram sender. The request URL is not returned to logs."""

    def post(text: str) -> HttpResponse:
        payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
        request = urllib.request.Request(
            "https://api.telegram.org/bot" + token + "/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return _open(request, opener)

    return post


def brevo_post(api_key: str, sender: str, recipient: str, subject: str, opener=None) -> Post:
    """Build a Brevo transactional sender."""

    def post(text: str) -> HttpResponse:
        payload = json.dumps(
            {
                "sender": {"email": sender},
                "to": [{"email": recipient}],
                "subject": subject,
                "textContent": text,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=payload,
            headers={"Content-Type": "application/json", "api-key": api_key},
            method="POST",
        )
        return _open(request, opener)

    return post


def _open(request: urllib.request.Request, opener) -> HttpResponse:
    call = opener or urllib.request.urlopen
    try:
        with call(request, timeout=5) as response:
            body = response.read().decode("utf-8", "replace")
            return HttpResponse(getattr(response, "status", 200), body, 0.0)
    except urllib.error.HTTPError as error:
        retry_after = 0.0
        try:
            retry_after = float(error.headers.get("Retry-After") or 0)
        except (TypeError, ValueError, AttributeError):
            retry_after = 0.0
        body = error.read().decode("utf-8", "replace")
        return HttpResponse(error.code, body, retry_after)
