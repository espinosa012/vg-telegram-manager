from unittest.mock import AsyncMock, MagicMock

import pytest

from vgtelegrammanager import TelegramDialogType, VGTelegramManager
from vgtelegrammanager._mixins import AuthMixin, ValidationMixin


@pytest.mark.parametrize(
    "name, owner",
    [("_ensure_client_ready", ValidationMixin), ("is_authenticated", AuthMixin)],
)
def test_real_implementations_are_not_shadowed(name, owner):
    defining_class = next(c for c in VGTelegramManager.__mro__ if name in c.__dict__)
    assert defining_class is owner


def test_ensure_client_ready_raises_when_disconnected(tmp_path):
    mgr = VGTelegramManager(
        api_id=12345,
        api_hash="abcdef1234567890",
        phone_number="+34600000000",
        session_file_path=str(tmp_path / "test.session"),
    )
    with pytest.raises(RuntimeError, match="not connected"):
        mgr._ensure_client_ready()


async def test_disconnected_client_is_rejected_before_any_request(connected_manager):
    connected_manager.client.is_connected.return_value = False
    with pytest.raises(RuntimeError, match="not connected"):
        await connected_manager.get_user_dialogs()
    connected_manager.client.is_user_authorized.assert_not_called()


async def test_is_authenticated_returns_client_state(connected_manager):
    assert await connected_manager.is_authenticated() is True
    connected_manager.client.is_user_authorized.return_value = False
    assert await connected_manager.is_authenticated() is False


async def test_get_user_dialogs_works_when_authenticated(connected_manager):
    class Channel:
        id = 1
        username = "news"
        megagroup = False

    dialog = MagicMock(entity=Channel(), dialog=MagicMock(unread_count=3, pinned=True))
    dialog.name = "News"

    async def iter_dialogs():
        yield dialog

    connected_manager.client.iter_dialogs = iter_dialogs

    dialogs = await connected_manager.get_user_dialogs([TelegramDialogType.CHANNEL])

    assert [(d.id, d.username, d.kind, d.unread_count) for d in dialogs] == [
        (1, "news", "channel", 3)
    ]


async def test_start_listening_requires_authentication(connected_manager):
    connected_manager.client.is_user_authorized.return_value = False
    await connected_manager.add_channel_to_listen("@news")
    with pytest.raises(RuntimeError, match="not authenticated"):
        await connected_manager.start_listening_channels()


async def test_start_listening_runs_when_authenticated(connected_manager):
    connected_manager.client.run_until_disconnected = AsyncMock()
    await connected_manager.add_channel_to_listen("@news")

    await connected_manager.start_listening_channels()

    assert connected_manager.telegram_user_id == "777"
    connected_manager.client.run_until_disconnected.assert_awaited_once()
