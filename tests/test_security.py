import importlib.metadata
import logging
import os
import stat
from unittest.mock import MagicMock

import pytest

import vgtelegrammanager
from vgtelegrammanager import TelegramDialog, TelegramDialogType, VGTelegramManager
from vgtelegrammanager._utils import mask_phone


def _make(tmp_path, **kwargs):
    params = dict(
        api_id=12345,
        api_hash="abcdef1234567890",
        phone_number="+34600000000",
        session_file_path=str(tmp_path / "sessions" / "acc.session"),
    )
    params.update(kwargs)
    return VGTelegramManager(**params)


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def test_session_dir_and_file_are_private(tmp_path):
    _make(tmp_path)
    assert _mode(tmp_path / "sessions") == 0o700
    assert _mode(tmp_path / "sessions" / "acc.session") == 0o600


def test_session_permissions_without_extension(tmp_path):
    _make(tmp_path, session_file_path=str(tmp_path / "acc"))
    assert _mode(tmp_path / "acc.session") == 0o600


@pytest.mark.parametrize(
    "phone, masked",
    [("+34600000000", "+34*******00"), ("12345", "*****"), ("+1234567", "+12***67")],
)
def test_mask_phone(phone, masked):
    assert mask_phone(phone) == masked


async def test_phone_number_is_masked_in_logs(connected_manager, caplog):
    connected_manager.client.is_user_authorized.return_value = False
    connected_manager.client.send_code_request.return_value = MagicMock(phone_code_hash="h")

    with caplog.at_level(logging.DEBUG, logger="vgtelegrammanager"):
        await connected_manager.request_verification_code()

    assert "+34600000000" not in caplog.text
    assert "+34*******00" in caplog.text


@pytest.mark.parametrize(
    "endpoint, warns",
    [
        ("http://example.com/hook", True),
        ("http://localhost:8000/hook", False),
        ("http://127.0.0.1/hook", False),
        ("http://api.localhost/hook", False),
        ("https://example.com/hook", False),
    ],
)
def test_plain_http_endpoint_warns_unless_local(tmp_path, caplog, endpoint, warns):
    with caplog.at_level(logging.WARNING, logger="vgtelegrammanager"):
        _make(tmp_path, process_messages_endpoint=endpoint)
    assert ("unencrypted" in caplog.text) is warns


@pytest.mark.parametrize(
    "kwargs, error",
    [
        ({"process_messages_endpoint": "https://"}, "valid HTTP or HTTPS URL"),
        ({"process_messages_endpoint": 123}, "valid HTTP or HTTPS URL"),
        ({"webhook_secret": "s"}, "requires a process messages endpoint"),
        (
            {"webhook_secret": "", "process_messages_endpoint": "https://x.io"},
            "non-empty string",
        ),
    ],
)
def test_invalid_webhook_settings_are_rejected(tmp_path, kwargs, error):
    with pytest.raises(ValueError, match=error):
        _make(tmp_path, **kwargs)


def test_webhook_secret_is_stored(tmp_path):
    mgr = _make(tmp_path, process_messages_endpoint="https://x.io", webhook_secret="s")
    assert mgr.webhook_secret == "s"


def test_dialog_repr_hides_sensitive_fields():
    dialog = TelegramDialog(
        id=1,
        name="Bob",
        dialog_type=TelegramDialogType.USER,
        kind="user",
        phone="34611111111",
        access_hash=987654321,
    )
    assert "34611111111" not in repr(dialog)
    assert "987654321" not in repr(dialog)
    assert dialog.model_dump()["phone"] == "34611111111"


def test_version_comes_from_package_metadata():
    assert vgtelegrammanager.__version__ == importlib.metadata.version("vg-telegram-manager")
