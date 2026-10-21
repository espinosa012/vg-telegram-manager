import functools
import json
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
import requests

from vgtelegrammanager import verify_webhook_signature
from vgtelegrammanager.models import TelegramMessage
from vgtelegrammanager.webhook import SIGNATURE_HEADER, TIMESTAMP_HEADER


@pytest.fixture
def message():
    return TelegramMessage(telegram_message_id="42", content="hello")


@pytest.fixture
def webhook_manager(connected_manager):
    connected_manager.process_messages_endpoint = "https://example.com/hook"
    connected_manager.webhook_backoff_seconds = 0
    return connected_manager


def _post(manager):
    return manager._http_session.post


def _responses(manager, *statuses):
    _post(manager).side_effect = [
        MagicMock(status_code=s, text="nope") if isinstance(s, int) else s for s in statuses
    ]


async def test_failing_partial_handler_does_not_stop_dispatch(connected_manager, message, caplog):
    received = []

    def failing(prefix, msg):
        raise ValueError(f"{prefix} boom")

    connected_manager.add_message_handler(functools.partial(failing, "partial"))
    connected_manager.add_message_handler(received.append)

    with caplog.at_level(logging.ERROR, logger="vgtelegrammanager"):
        await connected_manager._dispatch_message("@news", message)

    assert received == [message]
    assert "partial boom" in caplog.text


async def test_async_callable_object_is_awaited(connected_manager, message):
    class AsyncHandler:
        def __init__(self):
            self.received = []

        async def __call__(self, msg):
            self.received.append(msg)

    handler = AsyncHandler()
    connected_manager.add_message_handler(handler)

    await connected_manager._dispatch_message("@news", message)

    assert handler.received == [message]


async def test_sync_handler_returning_awaitable_is_awaited(connected_manager, message):
    received = []

    async def collect(msg):
        received.append(msg)

    connected_manager.add_message_handler(lambda msg: collect(msg))

    await connected_manager._dispatch_message("@news", message)

    assert received == [message]


async def test_channel_handlers_match_regardless_of_at_and_case(connected_manager, message):
    received = []
    connected_manager.add_message_handler(received.append, "News")

    await connected_manager._dispatch_message("@news", message)

    assert received == [message]


async def test_listener_uses_message_date_as_timestamp(connected_manager):
    received = []
    connected_manager.add_message_handler(received.append)
    connected_manager._add_listener("@news")
    sent_at = datetime(2024, 5, 1, 12, 30, tzinfo=timezone.utc)
    event = MagicMock(chat_id=-1001, chat=MagicMock(username="news"))
    event.message = MagicMock(message="hi", id=5, date=sent_at)

    await connected_manager._listeners["@news"](event)

    assert [(m.telegram_message_id, m.content, m.timestamp) for m in received] == [
        ("5", "hi", sent_at)
    ]


@pytest.mark.parametrize("status", [200, 201, 202, 204])
async def test_any_2xx_is_a_successful_forward(webhook_manager, message, caplog, status):
    _responses(webhook_manager, status)

    with caplog.at_level(logging.INFO, logger="vgtelegrammanager"):
        await webhook_manager._dispatch_message("@news", message)

    _post(webhook_manager).assert_called_once()
    assert "successfully forwarded" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


async def test_forward_posts_json_body(webhook_manager, message):
    _responses(webhook_manager, 200)

    await webhook_manager._dispatch_message("@news", message)

    call = _post(webhook_manager).call_args
    assert call.args == ("https://example.com/hook",)
    assert call.kwargs["headers"]["Content-Type"] == "application/json"
    assert json.loads(call.kwargs["data"])["telegram_message_id"] == "42"
    assert SIGNATURE_HEADER not in call.kwargs["headers"]


@pytest.mark.parametrize("status", [302, 400, 404])
async def test_non_retryable_status_is_not_retried(webhook_manager, message, caplog, status):
    _responses(webhook_manager, status)

    await webhook_manager._dispatch_message("@news", message)

    _post(webhook_manager).assert_called_once()
    assert "Failed to forward message '42' after 1 attempt(s)" in caplog.text


async def test_transient_failures_are_retried_until_success(webhook_manager, message, caplog):
    _responses(webhook_manager, requests.exceptions.Timeout("slow"), 503, 200)

    with caplog.at_level(logging.INFO, logger="vgtelegrammanager"):
        await webhook_manager._dispatch_message("@news", message)

    assert _post(webhook_manager).call_count == 3
    assert "successfully forwarded" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


async def test_retries_stop_after_max_attempts(webhook_manager, message, caplog):
    _responses(webhook_manager, 503, 503, 503, 200)

    await webhook_manager._dispatch_message("@news", message)

    assert _post(webhook_manager).call_count == webhook_manager.webhook_max_attempts == 3
    assert "Failed to forward message '42' after 3 attempt(s)" in caplog.text


async def test_non_transient_request_error_is_not_retried(webhook_manager, message, caplog):
    _responses(webhook_manager, requests.exceptions.InvalidURL("bad url"))

    await webhook_manager._dispatch_message("@news", message)

    _post(webhook_manager).assert_called_once()
    assert "InvalidURL: bad url" in caplog.text


async def test_logged_error_response_is_truncated(webhook_manager, message, caplog):
    _post(webhook_manager).side_effect = [MagicMock(status_code=400, text="x" * 5000)]

    await webhook_manager._dispatch_message("@news", message)

    assert "x" * 500 in caplog.text
    assert "x" * 501 not in caplog.text


async def test_webhook_requests_are_signed_when_secret_is_set(webhook_manager, message):
    webhook_manager.webhook_secret = "top-secret"
    _responses(webhook_manager, 200)

    await webhook_manager._dispatch_message("@news", message)

    kwargs = _post(webhook_manager).call_args.kwargs
    body, headers = kwargs["data"], kwargs["headers"]
    ts, sig = headers[TIMESTAMP_HEADER], headers[SIGNATURE_HEADER]
    assert verify_webhook_signature("top-secret", body, ts, sig)
    assert not verify_webhook_signature("wrong-secret", body, ts, sig)
    assert not verify_webhook_signature("top-secret", body + b" ", ts, sig)


def test_signature_with_stale_or_invalid_timestamp_is_rejected():
    from vgtelegrammanager.webhook import sign_webhook_body

    old = sign_webhook_body("s", b"{}", timestamp=1_000)
    assert not verify_webhook_signature("s", b"{}", old[TIMESTAMP_HEADER], old[SIGNATURE_HEADER])
    assert not verify_webhook_signature("s", b"{}", "not-a-number", old[SIGNATURE_HEADER])


async def test_disconnect_closes_http_session(webhook_manager):
    session = webhook_manager._http_session
    webhook_manager.client.is_connected.return_value = False

    await webhook_manager.disconnect_client()

    session.close.assert_called_once()
    assert webhook_manager._http_session is None
