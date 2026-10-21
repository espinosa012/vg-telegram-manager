from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.auth import ResendCodeRequest

from vgtelegrammanager._utils import mask_phone

if TYPE_CHECKING:
    from telethon import TelegramClient


class AuthMixin:
    """Mixin for Telegram connection and authentication management."""
    client: TelegramClient
    logger: logging.Logger
    phone_number: str
    telegram_user_id: Optional[str]
    _phone_code_hash: Optional[str]

    if TYPE_CHECKING:
        # Provided by ValidationMixin.
        # Only declared for type checkers: a runtime stub would shadow the real
        # implementation in the MRO.
        def _ensure_client_ready(self) -> None: ...

    async def connect_client(self) -> None:
        """Connects the underlying Telethon client."""
        if not hasattr(self, "client") or self.client is None:
            raise RuntimeError("Telegram client is not initialized")
        if not self.client.is_connected():
            await self.client.connect()
            self.logger.info("Client successfully connected to Telegram")

    async def request_verification_code(self, force_sms: bool = False) -> Optional[str]:
        """
        Requests the Telegram login verification code.

        Args:
            force_sms: If True, attempts to request code via SMS instead of in-app notification.

        Returns:
            The phone_code_hash for this login attempt, or None if already authenticated.
            Persist it if verify_code() will run in another process or manager instance.
        """
        self._ensure_client_ready()

        if await self.is_authenticated():
            self.logger.info("User is already authenticated; no need to request code")
            return None

        sent = await self.client.send_code_request(self.phone_number, force_sms=force_sms)
        self._phone_code_hash = sent.phone_code_hash
        method = "SMS" if force_sms else "Telegram app"
        self.logger.info("Verification code sent to %s via %s", mask_phone(self.phone_number), method)
        return self._phone_code_hash

    async def resend_verification_code_via_sms(
        self, phone_code_hash: Optional[str] = None
    ) -> str:
        """
        Resends verification code via SMS. Must follow request_verification_code().

        Args:
            phone_code_hash: Hash returned by request_verification_code(). Defaults to
                the one stored on this instance.

        Returns:
            The (possibly new) phone_code_hash to pass to verify_code().
        """
        self._ensure_client_ready()

        current_hash = phone_code_hash or self._phone_code_hash
        if not current_hash:
            raise RuntimeError(
                "No phone_code_hash available. Call request_verification_code() first."
            )

        sent = await self.client(ResendCodeRequest(
            phone_number=self.phone_number,
            phone_code_hash=current_hash
        ))
        self._phone_code_hash = sent.phone_code_hash
        self.logger.info("Verification code resent to %s via SMS", mask_phone(self.phone_number))
        return self._phone_code_hash

    async def verify_code(
        self,
        code: str,
        password: Optional[str] = None,
        phone_code_hash: Optional[str] = None,
    ) -> None:
        """
        Completes authentication with received verification code.

        Args:
            code: Verification code received via Telegram app or SMS.
            password: Two-step verification password. Only used if the account has 2FA
                enabled; otherwise call verify_password() when SessionPasswordNeededError
                is raised.
            phone_code_hash: Hash returned by request_verification_code(). Defaults to
                the one stored on this instance.

        Raises:
            SessionPasswordNeededError: If the account has 2FA enabled and no password
                was provided.
        """
        self._ensure_client_ready()
        if not code or not isinstance(code, str):
            raise ValueError("Verification code must be a non-empty string")

        try:
            await self.client.sign_in(
                self.phone_number,
                code.strip(),
                phone_code_hash=phone_code_hash or self._phone_code_hash,
            )
        except SessionPasswordNeededError:
            if not password:
                self.logger.info(
                    "Two-step verification is enabled; call verify_password() to finish login"
                )
                raise
            await self.verify_password(password)
            return
        except Exception as e:
            self.logger.error("Authentication failed: %s", e)
            raise

        self._phone_code_hash = None
        self.logger.info("User authenticated successfully")

    async def verify_password(self, password: str) -> None:
        """Completes authentication for accounts with two-step verification enabled."""
        self._ensure_client_ready()
        if not password or not isinstance(password, str):
            raise ValueError("Password must be a non-empty string")

        try:
            await self.client.sign_in(password=password)
        except Exception as e:
            self.logger.error("Two-step verification failed: %s", e)
            raise

        self._phone_code_hash = None
        self.logger.info("User authenticated successfully")

    async def is_authenticated(self) -> bool:
        """Checks if current session is authorized."""
        self._ensure_client_ready()
        return await self.client.is_user_authorized()

    async def _ensure_authenticated(self, action: str) -> None:
        """Raises unless the client is connected and authorized. `action` names the caller."""
        self._ensure_client_ready()
        if not await self.is_authenticated():
            raise RuntimeError(f"Cannot {action}: client not authenticated")

    async def _set_telegram_user_id(self) -> None:
        """Retrieves and stores the authenticated user's ID."""
        await self._ensure_authenticated("get user ID")

        if self.telegram_user_id:
            self.logger.debug("User ID already set: %s", self.telegram_user_id)
            return

        me = await self.client.get_me()
        self.telegram_user_id = str(me.id)
        self.logger.info("User ID set: %s", self.telegram_user_id)
