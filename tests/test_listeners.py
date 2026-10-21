from vgtelegrammanager.models import TelegramMessage


def _registered_chats(manager):
    return [call.args[1].chats for call in manager.client.add_event_handler.call_args_list]


async def test_registering_twice_does_not_duplicate_handlers(connected_manager):
    await connected_manager.add_channel_to_listen("@news")
    await connected_manager.add_channel_to_listen("me")

    connected_manager._register_channel_listeners()
    connected_manager._register_channel_listeners()

    assert _registered_chats(connected_manager) == ["@news", "me"]


async def test_channel_added_while_listening_is_registered_immediately(connected_manager):
    await connected_manager.add_channel_to_listen("@news")
    connected_manager._register_channel_listeners()

    await connected_manager.add_channel_to_listen("@sports")

    assert _registered_chats(connected_manager) == ["@news", "@sports"]


async def test_channel_added_before_listening_is_not_registered_yet(connected_manager):
    await connected_manager.add_channel_to_listen("@news")
    connected_manager.client.add_event_handler.assert_not_called()


async def test_remove_channel_detaches_listener_and_callbacks(connected_manager):
    received = []
    await connected_manager.add_channel_to_listen("@news", callback=received.append)
    connected_manager._register_channel_listeners()
    handler = connected_manager._listeners["@news"]

    assert connected_manager.remove_channel_to_listen("news") is True

    connected_manager.client.remove_event_handler.assert_called_once_with(handler)
    assert "@news" not in connected_manager._listeners
    assert "@news" not in connected_manager._channel_callbacks

    await connected_manager._dispatch_message(
        "@news", TelegramMessage(telegram_message_id="1", content="x")
    )
    assert received == []


async def test_disconnect_stops_immediate_registration(connected_manager):
    connected_manager._register_channel_listeners()
    connected_manager.client.is_connected.return_value = False

    await connected_manager.disconnect_client()
    await connected_manager.add_channel_to_listen("@news")

    connected_manager.client.add_event_handler.assert_not_called()
