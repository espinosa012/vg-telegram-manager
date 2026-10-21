
import pytest

from vgtelegrammanager import VGTelegramManager
from vgtelegrammanager.models import TelegramMessage


@pytest.fixture
def manager(tmp_path):
    session_file = str(tmp_path / "test.session")
    mgr = VGTelegramManager(
        api_id=12345,
        api_hash="abcdef1234567890",
        phone_number="+34600000000",
        session_file_path=session_file,
    )
    return mgr


async def test_resolve_channel_me(manager):
    assert await manager._resolve_channel_identifier("me") == "me"
    assert await manager._resolve_channel_identifier("self") == "me"
    assert await manager._resolve_channel_identifier("  ME  ") == "me"


async def test_resolve_channel_username(manager):
    assert await manager._resolve_channel_identifier("@some_channel") == "@some_channel"


async def test_add_and_remove_channel(manager):
    added = await manager.add_channel_to_listen("@news")
    assert added is True
    assert "@news" in manager.get_listening_channels()

    # Re-adding same channel returns False
    readded = await manager.add_channel_to_listen("@news")
    assert readded is False

    removed = manager.remove_channel_to_listen("@news")
    assert removed is True
    assert "@news" not in manager.get_listening_channels()


async def test_message_dispatch_to_callbacks(manager):
    received_global = []
    received_channel = []

    def global_cb(msg: TelegramMessage):
        received_global.append(msg)

    async def channel_cb(msg: TelegramMessage):
        received_channel.append(msg)

    manager.add_message_handler(global_cb)
    await manager.add_channel_to_listen("me", callback=channel_cb)

    test_msg = TelegramMessage(
        telegram_message_id="101",
        from_telegram_chat_name="me",
        content="Test note",
    )

    await manager._dispatch_message("me", test_msg)

    assert len(received_global) == 1
    assert received_global[0].content == "Test note"
    assert len(received_channel) == 1
    assert received_channel[0].content == "Test note"
