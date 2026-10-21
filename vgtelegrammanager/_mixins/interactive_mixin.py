from __future__ import annotations

import logging
from types import TracebackType
from typing import TYPE_CHECKING, Optional

from vgtelegrammanager._utils import ChannelIdentifier

if TYPE_CHECKING:
    from telethon import TelegramClient
    from typing_extensions import Self


class InteractiveMixin:
    """Mixin for interactive terminal authentication flow and async context manager support."""
    client: TelegramClient
    logger: logging.Logger
    phone_number: str
    telegram_user_id: Optional[str]
    channels_to_listen_from: list[ChannelIdentifier]
    _listening: bool

    if TYPE_CHECKING:
        # Provided by AuthMixin & ProcessingMixin.
        # Only declared for type checkers: a runtime stub would shadow the real
        # implementation in the MRO.
        async def connect_client(self) -> None: ...
        def _register_channel_listeners(self) -> None: ...
        def _close_http_session(self) -> None: ...

    async def disconnect_client(self) -> None:
        """Gracefully disconnects from Telegram and releases the webhook HTTP session."""
        # Channels added while disconnected get their listener on the next start_*
        self._listening = False
        self._close_http_session()
        if hasattr(self, "client") and self.client and self.client.is_connected():
            await self.client.disconnect()
            self.logger.info("Client '%s' disconnected from Telegram", self.telegram_user_id or "unknown")

    async def _interactive_start(self) -> None:
        """
        Interactive start prompt via Telethon (uses terminal input()).
        Useful for CLI tools or scripts. Not suitable for headless/web apps.
        """
        await self.client.start(phone=self.phone_number)
        me = await self.client.get_me()
        self.telegram_user_id = str(me.id)
        self.logger.info("Interactive login successful for user %s", self.telegram_user_id)

    async def interactive_start_listening_channels(self) -> None:
        """
        Starts client interactively (prompts for code on console if needed)
        and listens to configured channels.
        """
        if not self.channels_to_listen_from:
            raise ValueError("No channels configured to listen from. Use add_channel_to_listen() first.")

        await self._interactive_start()
        self._register_channel_listeners()
        self.logger.info(
            "User '%s' listening to %d channel(s)",
            self.telegram_user_id,
            len(self.channels_to_listen_from),
        )
        await self.client.run_until_disconnected()

    def __enter__(self) -> None:
        """Prevent synchronous context manager usage."""
        raise RuntimeError("Use async context manager ('async with') instead of synchronous 'with'")

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        await self.connect_client()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Async context manager exit."""
        await self.disconnect_client()
