import logging
from unittest.mock import MagicMock

import pytest

from vgtelegrammanager import TelegramDialogType


class Channel:
    def __init__(self, id, username=None):
        self.id = id
        self.username = username


class User:
    def __init__(self, id, username=None):
        self.id = id
        self.username = username


def _dialog(entity, name, peer_id):
    dialog = MagicMock(entity=entity, dialog=MagicMock(unread_count=0, pinned=False), id=peer_id)
    dialog.name = name
    return dialog


@pytest.fixture
def dialogs(connected_manager):
    """Installs a fake iter_dialogs and records how many dialogs were consumed."""
    consumed = []
    items = [
        _dialog(Channel(1, "public_news"), "News", -1001),
        _dialog(Channel(2), "Private Club", -1002),
        _dialog(User(3, "alice"), "Alice", 3),
        _dialog(Channel(4, "other"), "Alice", -1004),
    ]

    async def iter_dialogs():
        for item in items:
            consumed.append(item.name)
            yield item

    connected_manager.client.iter_dialogs = iter_dialogs
    return consumed


@pytest.mark.parametrize(
    "raw, expected",
    [("me", "me"), ("SELF", "me"), ("@x", "@x"), ("-1001234", -1001234), ("777", 777)],
)
async def test_resolution_without_lookup(connected_manager, raw, expected):
    connected_manager.client.iter_dialogs = MagicMock(side_effect=AssertionError("no lookup"))
    assert await connected_manager._resolve_channel_identifier(raw) == expected


async def test_display_name_resolves_to_username(connected_manager, dialogs):
    assert await connected_manager._resolve_channel_identifier("News") == "@public_news"


async def test_display_name_lookup_stops_at_first_match(connected_manager, dialogs):
    await connected_manager._resolve_channel_identifier("News")
    assert dialogs == ["News"]


async def test_private_dialog_resolves_to_marked_peer_id(connected_manager, dialogs):
    assert await connected_manager._resolve_channel_identifier("Private Club") == -1002


async def test_unknown_name_is_treated_as_username(connected_manager, dialogs):
    assert await connected_manager._resolve_channel_identifier("somechannel") == "somechannel"


async def test_unresolvable_while_disconnected_falls_back_with_warning(connected_manager, caplog):
    connected_manager.client.is_connected.return_value = False

    with caplog.at_level(logging.WARNING, logger="vgtelegrammanager"):
        resolved = await connected_manager._resolve_channel_identifier("somechannel")

    assert resolved == "somechannel"
    assert "treating it as a username" in caplog.text


async def test_get_dialog_username_by_name_filters_types(connected_manager, dialogs):
    assert await connected_manager.get_dialog_username_by_name("Alice") == "alice"
    assert (
        await connected_manager.get_dialog_username_by_name("Alice", [TelegramDialogType.CHANNEL])
        == "other"
    )
    with pytest.raises(LookupError):
        await connected_manager.get_dialog_username_by_name("Nobody")


async def test_private_dialog_can_be_listened(connected_manager, dialogs):
    assert await connected_manager.add_channel_to_listen("Private Club") is True
    connected_manager._register_channel_listeners()

    assert connected_manager.get_listening_channels() == [-1002]
    assert connected_manager.client.add_event_handler.call_args.args[1].chats == -1002


async def test_add_channel_accepts_numeric_id(connected_manager):
    assert await connected_manager.add_channel_to_listen(-1009) is True
    assert connected_manager.remove_channel_to_listen(-1009) is True


@pytest.mark.parametrize("bad", ["", "   ", None, True])
async def test_add_channel_rejects_invalid_identifiers(connected_manager, bad):
    with pytest.raises(ValueError):
        await connected_manager.add_channel_to_listen(bad)


async def test_duplicates_are_detected_ignoring_at_and_case(connected_manager):
    assert await connected_manager.add_channel_to_listen("@News") is True
    assert await connected_manager.add_channel_to_listen("@news") is False
    assert connected_manager.remove_channel_to_listen("NEWS") is True
    assert connected_manager.get_listening_channels() == []
