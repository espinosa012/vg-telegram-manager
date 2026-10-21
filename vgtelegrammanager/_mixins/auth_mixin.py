from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from telethon.tl.functions.auth import ResendCodeRequest

if TYPE_CHECKING:
    from telethon import TelegramClient


class AuthMixin:
    """Mixin for Telegram connection and authentication management."""
    client: TelegramClient
    logger: logging.Logger
    phone_number: str
    telegram_user_id: Optional[str]
    _phone_code_hash: Optional[str]

    # Required from ValidationMixin
    def _ensure_client_ready(self) -> None: ...

    async def connect_client(self) -> None:
        """Connects the underlying Telethon client."""
        if not hasattr(self, "client") or self.client is None:
            raise RuntimeError("Telegram client is not initialized")
        if not self.client.is_connected():
            await self.client.connect()
            self.logger.info("Client successfully connected to Telegram")

    async def request_verification_code(self, force_sms: bool = False) -> None:
        """
        Requests the Telegram login verification code.

        Args:
            force_sms: If True, attempts to request code via SMS instead of in-app notification.
        """
        self._ensure_client_ready()

        if await self.is_authenticated():
            self.logger.info("User is already authenticated; no need to request code")
            return

        sent = await self.client.send_code_request(self.phone_number, force_sms=force_sms)
        self._phone_code_hash = sent.phone_code_hash
        method = "SMS" if force_sms else "Telegram app"
        self.logger.info(f"Verification code sent to {self.phone_number} via {method}")

    async def resend_verification_code_via_sms(self) -> None:
        """
        Resends verification code via SMS. Must follow request_verification_code().
        """
        self._ensure_client_ready()

        if not self._phone_code_hash:
            raise RuntimeError(
                "No phone_code_hash available. Call request_verification_code() first."
            )

        sent = await self.client(ResendCodeRequest(
            phone_number=self.phone_number,
            phone_code_hash=self._phone_code_hash
        ))
        self._phone_code_hash = sent.phone_code_hash
        self.logger.info(f"Verification code resent to {self.phone_number} via SMS")

    async def verify_code(self, code: str) -> None:
        """Completes authentication with received verification code."""
        self._ensure_client_ready()
        if not code or not isinstance(code, str):
            raise ValueError("Verification code must be a non-empty string")

        try:
            await self.client.sign_in(self.phone_number, code.strip())
            self.logger.info("User authenticated successfully")
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            raise

    async def is_authenticated(self) -> bool:
        """Checks if current session is authorized."""
        self._ensure_client_ready()
        return await self.client.is_user_authorized()

    async def _set_telegram_user_id(self) -> None:
        """Retrieves and stores the authenticated user's ID."""
        self._ensure_client_ready()

        if not await self.is_authenticated():
            raise RuntimeError("Cannot get user ID: client not authenticated")

        if self.telegram_user_id:
            self.logger.debug(f"User ID already set: {self.telegram_user_id}")
            return

        me = await self.client.get_me()
        self.telegram_user_id = str(me.id)
        self.logger.info(f"User ID set: {self.telegram_user_id}")
