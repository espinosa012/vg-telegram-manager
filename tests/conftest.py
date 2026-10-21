from unittest.mock import AsyncMock, MagicMock

import pytest

from vgtelegrammanager import VGTelegramManager


@pytest.fixture
def connected_manager(tmp_path):
    """Manager whose Telethon client is replaced by a connected, authorized mock."""
    mgr = VGTelegramManager(
        api_id=12345,
        api_hash="abcdef1234567890",
        phone_number="+34600000000",
        session_file_path=str(tmp_path / "test.session"),
    )
    client = MagicMock()
    client.is_connected.return_value = True
    client.is_user_authorized = AsyncMock(return_value=True)
    client.get_me = AsyncMock(return_value=MagicMock(id=777))
    client.sign_in = AsyncMock()
    client.send_code_request = AsyncMock()
    mgr.client = client
    return mgr
