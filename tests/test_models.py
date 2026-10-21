from datetime import datetime, timezone
from vgtelegrammanager.models import TelegramDialog, TelegramDialogType, TelegramMessage


def test_telegram_dialog_model():
    dialog = TelegramDialog(
        id=12345,
        name="Test Channel",
        username="testchannel",
        dialog_type=TelegramDialogType.CHANNEL,
        kind="channel",
    )
    assert dialog.id == 12345
    assert dialog.name == "Test Channel"
    assert dialog.username == "testchannel"
    assert dialog.dialog_type == TelegramDialogType.CHANNEL
    assert dialog.kind == "channel"
    assert dialog.unread_count == 0


def test_telegram_message_model():
    now = datetime.now(timezone.utc)
    msg = TelegramMessage(
        telegram_message_id="999",
        telegram_user_id="111",
        from_telegram_chat_id="-10012345678",
        from_telegram_chat_name="my_chat",
        content="Hello world",
        timestamp=now,
    )
    assert msg.telegram_message_id == "999"
    assert msg.content == "Hello world"
    data = msg.model_dump(mode="json")
    assert data["telegram_message_id"] == "999"
    assert data["content"] == "Hello world"
