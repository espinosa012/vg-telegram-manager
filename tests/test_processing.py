import functools
import logging
from unittest.mock import MagicMock, patch

import pytest

from vgtelegrammanager.models import TelegramMessage


@pytest.fixture
def message():
    return TelegramMessage(telegram_message_id="42", content="hello")


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


@pytest.mark.parametrize("status", [200, 201, 202, 204])
async def test_any_2xx_is_a_successful_forward(connected_manager, message, caplog, status):
    connected_manager.process_messages_endpoint = "https://example.com/hook"

    with patch("requests.post", return_value=MagicMock(status_code=status)) as post, \
            caplog.at_level(logging.INFO, logger="vgtelegrammanager"):
        await connected_manager._dispatch_message("@news", message)

    post.assert_called_once()
    assert "successfully forwarded" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.parametrize("status", [302, 400, 500])
async def test_non_2xx_forward_is_logged_as_error(connected_manager, message, caplog, status):
    connected_manager.process_messages_endpoint = "https://example.com/hook"

    with patch("requests.post", return_value=MagicMock(status_code=status, text="nope")), \
            caplog.at_level(logging.INFO, logger="vgtelegrammanager"):
        await connected_manager._dispatch_message("@news", message)

    assert "Failed to forward message '42'" in caplog.text
