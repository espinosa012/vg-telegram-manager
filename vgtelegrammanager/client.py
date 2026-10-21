from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Awaitable, Callable, Optional

import requests

from ._mixins import (
    AuthMixin,
    ChannelsListeningMixin,
    DiscoveryMixin,
    InteractiveMixin,
    ProcessingMixin,
    ValidationMixin,
    telegram_dialog_from_telethon,
)
from ._utils import ChannelIdentifier
from .models import TelegramDialog, TelegramDialogKind, TelegramDialogType, TelegramMessage

if TYPE_CHECKING:
    from telethon import events

    from ._mixins import MessageHandler


class VGTelegramManager(
    InteractiveMixin,
    ChannelsListeningMixin,
    DiscoveryMixin,
    ProcessingMixin,
    AuthMixin,
    ValidationMixin,
):
    """
    High-level Telegram user-client manager.

    Provides channel monitoring, message listening with custom callbacks and/or
    HTTP webhook forwarding, full headless and interactive authentication,
    and dialog discovery.
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone_number: str,
        session_file_path: str,
        process_messages_endpoint: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        webhook_secret: Optional[str] = None,
    ) -> None:
        """
        Initializes the Telegram user manager.

        Args:
            api_id: Telegram API ID from my.telegram.org.
            api_hash: Telegram API Hash from my.telegram.org.
            phone_number: International phone number associated with the Telegram account.
            session_file_path: Path to the Telethon session file. It grants full access to
                the account, so it is created readable by its owner only.
            process_messages_endpoint: Optional HTTP(S) URL where incoming messages are POSTed.
            logger: Optional custom logging.Logger instance. Defaults to 'vgtelegrammanager' logger.
            webhook_secret: Optional shared secret used to sign webhook requests with
                HMAC-SHA256 (see vgtelegrammanager.webhook). Requires process_messages_endpoint.
        """
        self.logger = logger or logging.getLogger("vgtelegrammanager")
        self._validate_init_params(
            api_id, api_hash, phone_number, process_messages_endpoint, webhook_secret
        )
        self._warn_if_insecure_endpoint(process_messages_endpoint)

        self.app_api_id = api_id
        self.app_api_hash = api_hash
        self.phone_number = phone_number
        self.session_file_path = session_file_path
        self.process_messages_endpoint = process_messages_endpoint
        self.webhook_secret = webhook_secret

        self._setup_client()
        self.telegram_user_id: Optional[str] = None
        self.channels_to_listen_from: list[ChannelIdentifier] = []
        self._phone_code_hash: Optional[str] = None
        self._channel_callbacks: dict[ChannelIdentifier, list[MessageHandler]] = {}
        self._global_callbacks: list[MessageHandler] = []
        self._listeners: dict[
            ChannelIdentifier, Callable[[events.NewMessage.Event], Awaitable[None]]
        ] = {}
        self._listening = False
        self._http_session: Optional[requests.Session] = None


# Convenience aliases
TelegramUserManager = VGTelegramManager

__all__ = [
    "VGTelegramManager",
    "TelegramUserManager",
    "TelegramDialog",
    "TelegramDialogKind",
    "TelegramMessage",
    "TelegramDialogType",
    "telegram_dialog_from_telethon",
]
