from __future__ import annotations

import logging
from typing import Optional

from ._mixins import (
    AuthMixin,
    ChannelsListeningMixin,
    DiscoveryMixin,
    InteractiveMixin,
    ProcessingMixin,
    ValidationMixin,
    telegram_dialog_from_telethon,
)
from .models import TelegramDialog, TelegramDialogType, TelegramMessage


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
    ) -> None:
        """
        Initializes the Telegram user manager.

        Args:
            api_id: Telegram API ID from my.telegram.org.
            api_hash: Telegram API Hash from my.telegram.org.
            phone_number: International phone number associated with the Telegram account.
            session_file_path: Path to the Telethon session file.
            process_messages_endpoint: Optional HTTP(S) URL where incoming messages are POSTed.
            logger: Optional custom logging.Logger instance. Defaults to 'vgtelegrammanager' logger.
        """
        self.logger = logger or logging.getLogger("vgtelegrammanager")
        self._validate_init_params(api_id, api_hash, phone_number, process_messages_endpoint)

        self.app_api_id = api_id
        self.app_api_hash = api_hash
        self.phone_number = phone_number
        self.session_file_path = session_file_path
        self.process_messages_endpoint = process_messages_endpoint

        self._setup_client()
        self.telegram_user_id: Optional[str] = None
        self.channels_to_listen_from: list[str] = []
        self._phone_code_hash: Optional[str] = None
        self._channel_callbacks: dict = {}
        self._global_callbacks: list = []


# Convenience aliases
TelegramUserManager = VGTelegramManager

__all__ = [
    "VGTelegramManager",
    "TelegramUserManager",
    "TelegramDialog",
    "TelegramMessage",
    "TelegramDialogType",
    "telegram_dialog_from_telethon",
]
