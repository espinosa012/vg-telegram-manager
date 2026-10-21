from unittest.mock import AsyncMock, MagicMock, call

import pytest
from telethon.errors import SessionPasswordNeededError


@pytest.fixture
def unauthorized_manager(connected_manager):
    connected_manager.client.is_user_authorized.return_value = False
    connected_manager.client.send_code_request.return_value = MagicMock(phone_code_hash="hash-1")
    return connected_manager


async def test_request_code_returns_phone_code_hash(unauthorized_manager):
    assert await unauthorized_manager.request_verification_code() == "hash-1"


async def test_request_code_returns_none_when_already_authenticated(connected_manager):
    assert await connected_manager.request_verification_code() is None
    connected_manager.client.send_code_request.assert_not_called()


async def test_verify_code_passes_stored_hash(unauthorized_manager):
    await unauthorized_manager.request_verification_code()

    await unauthorized_manager.verify_code(" 12345 ")

    unauthorized_manager.client.sign_in.assert_awaited_once_with(
        "+34600000000", "12345", phone_code_hash="hash-1"
    )
    assert unauthorized_manager._phone_code_hash is None


async def test_verify_code_accepts_hash_from_another_instance(unauthorized_manager):
    await unauthorized_manager.verify_code("12345", phone_code_hash="external-hash")

    unauthorized_manager.client.sign_in.assert_awaited_once_with(
        "+34600000000", "12345", phone_code_hash="external-hash"
    )


async def test_resend_updates_hash_used_by_verify_code(unauthorized_manager):
    await unauthorized_manager.request_verification_code()
    resend = AsyncMock(return_value=MagicMock(phone_code_hash="hash-2"))
    unauthorized_manager.client.side_effect = resend

    assert await unauthorized_manager.resend_verification_code_via_sms() == "hash-2"
    await unauthorized_manager.verify_code("12345")

    assert resend.await_args.args[0].phone_code_hash == "hash-1"
    unauthorized_manager.client.sign_in.assert_awaited_once_with(
        "+34600000000", "12345", phone_code_hash="hash-2"
    )


async def test_verify_code_with_2fa_and_password(unauthorized_manager):
    unauthorized_manager.client.sign_in.side_effect = [SessionPasswordNeededError(None), None]

    await unauthorized_manager.verify_code("12345", password="s3cret")

    assert unauthorized_manager.client.sign_in.await_args_list[1] == call(password="s3cret")


async def test_verify_code_with_2fa_without_password_raises(unauthorized_manager):
    unauthorized_manager.client.sign_in.side_effect = SessionPasswordNeededError(None)

    with pytest.raises(SessionPasswordNeededError):
        await unauthorized_manager.verify_code("12345")


async def test_two_step_flow_with_verify_password(unauthorized_manager):
    unauthorized_manager.client.sign_in.side_effect = [SessionPasswordNeededError(None), None]

    with pytest.raises(SessionPasswordNeededError):
        await unauthorized_manager.verify_code("12345")
    await unauthorized_manager.verify_password("s3cret")

    assert unauthorized_manager.client.sign_in.await_args_list[1] == call(password="s3cret")


async def test_verify_password_rejects_empty(connected_manager):
    with pytest.raises(ValueError):
        await connected_manager.verify_password("")
