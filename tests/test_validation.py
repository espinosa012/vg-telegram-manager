import pytest
from vgtelegrammanager import VGTelegramManager


def test_init_validation_success():
    client = VGTelegramManager(
        api_id=12345,
        api_hash="abcdef1234567890",
        phone_number="+34600000000",
        session_file_path="sessions/test.session",
    )
    assert client.app_api_id == 12345
    assert client.process_messages_endpoint is None


def test_init_validation_with_endpoint():
    client = VGTelegramManager(
        api_id=12345,
        api_hash="abcdef1234567890",
        phone_number="+34600000000",
        session_file_path="sessions/test.session",
        process_messages_endpoint="https://example.com/webhook",
    )
    assert client.process_messages_endpoint == "https://example.com/webhook"


def test_init_validation_invalid_api_id():
    with pytest.raises(ValueError, match="API ID must be a positive integer"):
        VGTelegramManager(
            api_id=-1,
            api_hash="abcdef",
            phone_number="+34600000000",
            session_file_path="sessions/test.session",
        )


def test_init_validation_invalid_endpoint():
    with pytest.raises(ValueError, match="must be a valid HTTP or HTTPS URL"):
        VGTelegramManager(
            api_id=12345,
            api_hash="abcdef",
            phone_number="+34600000000",
            session_file_path="sessions/test.session",
            process_messages_endpoint="ftp://invalid-url",
        )
