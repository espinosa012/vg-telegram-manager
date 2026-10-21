from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from telethon import TelegramClient

if TYPE_CHECKING:
    from telethon import TelegramClient as _TelegramClient


class ValidationMixin:
    """Mixin for parameter validation and Telegram client setup."""
    session_file_path: str
    app_api_id: int
    app_api_hash: str
    client: _TelegramClient

    @staticmethod
    def _validate_init_params(
        api_id: int,
        api_hash: str,
        phone_number: str,
        process_messages_endpoint: Optional[str] = None,
    ) -> None:
        if not isinstance(api_id, int) or api_id <= 0:
            raise ValueError("API ID must be a positive integer")
        if not api_hash or not isinstance(api_hash, str):
            raise ValueError("API hash must be a non-empty string")
        if not phone_number or not isinstance(phone_number, str):
            raise ValueError("Phone number must be a non-empty string")
        if process_messages_endpoint is not None:
            if not isinstance(process_messages_endpoint, str) or not process_messages_endpoint.startswith(('http://', 'https://')):
                raise ValueError("Process messages endpoint must be a valid HTTP or HTTPS URL")

    def _ensure_client_ready(self) -> None:
        """Verifies that the client is initialized and connected."""
        if not hasattr(self, "client") or self.client is None:
            raise RuntimeError("Telegram client is not initialized")
        if not self.client.is_connected():
            raise RuntimeError("Client is not connected. Call connect_client() first.")

    def _setup_client(self) -> None:
        session_dir = os.path.dirname(self.session_file_path)
        if session_dir:
            os.makedirs(session_dir, exist_ok=True)

        self.client = TelegramClient(self.session_file_path, self.app_api_id, self.app_api_hash)
        self.client.parse_mode = 'html'
