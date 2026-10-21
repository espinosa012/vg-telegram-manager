import pytest

from vgtelegrammanager import VGTelegramManager


@pytest.fixture
def session_file(tmp_path):
    return str(tmp_path / "sessions" / "test.session")


def test_init_validation_success(session_file):
    client = VGTelegramManager(
        api_id=12345,
        api_hash="abcdef1234567890",
        phone_number="+34600000000",
        session_file_path=session_file,
    )
    assert client.app_api_id == 12345
    assert client.process_messages_endpoint is None


def test_init_validation_with_endpoint(session_file):
    client = VGTelegramManager(
        api_id=12345,
        api_hash="abcdef1234567890",
        phone_number="+34600000000",
        session_file_path=session_file,
        process_messages_endpoint="https://example.com/webhook",
    )
    assert client.process_messages_endpoint == "https://example.com/webhook"


def test_init_validation_invalid_api_id(session_file):
    with pytest.raises(ValueError, match="API ID must be a positive integer"):
        VGTelegramManager(
            api_id=-1,
            api_hash="abcdef",
            phone_number="+34600000000",
            session_file_path=session_file,
        )


def test_init_validation_invalid_endpoint(session_file):
    with pytest.raises(ValueError, match="must be a valid HTTP or HTTPS URL"):
        VGTelegramManager(
            api_id=12345,
            api_hash="abcdef",
            phone_number="+34600000000",
            session_file_path=session_file,
            process_messages_endpoint="ftp://invalid-url",
        )
