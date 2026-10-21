from __future__ import annotations

import logging
import os
from typing import Optional
from urllib.parse import urlsplit

from telethon import TelegramClient

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class ValidationMixin:
    """Mixin for parameter validation and Telegram client setup."""
    session_file_path: str
    app_api_id: int
    app_api_hash: str
    client: TelegramClient
    logger: logging.Logger

    @staticmethod
    def _validate_init_params(
        api_id: int,
        api_hash: str,
        phone_number: str,
        process_messages_endpoint: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> None:
        if not isinstance(api_id, int) or api_id <= 0:
            raise ValueError("API ID must be a positive integer")
        if not api_hash or not isinstance(api_hash, str):
            raise ValueError("API hash must be a non-empty string")
        if not phone_number or not isinstance(phone_number, str):
            raise ValueError("Phone number must be a non-empty string")
        if process_messages_endpoint is not None:
            parts = (
                urlsplit(process_messages_endpoint)
                if isinstance(process_messages_endpoint, str)
                else None
            )
            if parts is None or parts.scheme not in ("http", "https") or not parts.hostname:
                raise ValueError("Process messages endpoint must be a valid HTTP or HTTPS URL")
        if webhook_secret is not None:
            if not webhook_secret or not isinstance(webhook_secret, str):
                raise ValueError("Webhook secret must be a non-empty string")
            if process_messages_endpoint is None:
                raise ValueError("Webhook secret requires a process messages endpoint")

    def _warn_if_insecure_endpoint(self, endpoint: Optional[str]) -> None:
        """Warns when messages would be forwarded unencrypted to a non-local host."""
        if endpoint is None:
            return
        parts = urlsplit(endpoint)
        host = parts.hostname or ""
        if parts.scheme == "http" and host not in _LOCAL_HOSTS and not host.endswith(".localhost"):
            self.logger.warning(
                "Webhook endpoint host '%s' uses plain HTTP: message contents will be sent "
                "unencrypted. Use HTTPS.",
                host,
            )

    def _ensure_client_ready(self) -> None:
        """Verifies that the client is initialized and connected."""
        if not hasattr(self, "client") or self.client is None:
            raise RuntimeError("Telegram client is not initialized")
        if not self.client.is_connected():
            raise RuntimeError("Client is not connected. Call connect_client() first.")

    def _setup_client(self) -> None:
        session_dir = os.path.dirname(self.session_file_path)
        if session_dir:
            os.makedirs(session_dir, mode=0o700, exist_ok=True)

        self.client = TelegramClient(self.session_file_path, self.app_api_id, self.app_api_hash)
        self.client.parse_mode = 'html'
        self._restrict_session_file_permissions()

    def _restrict_session_file_permissions(self) -> None:
        """
        The session file grants full access to the Telegram account: make it
        readable and writable by its owner only.
        """
        path = self.session_file_path
        if not path.endswith(".session"):
            # Telethon appends the extension when it is missing
            path += ".session"
        try:
            os.chmod(path, 0o600)
        except FileNotFoundError:
            pass
        except OSError as e:
            self.logger.warning("Could not restrict permissions of session file '%s': %s", path, e)
