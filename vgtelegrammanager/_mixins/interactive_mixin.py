from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from telethon import TelegramClient


class InteractiveMixin:
    """Mixin for interactive terminal authentication flow and async context manager support."""
    client: TelegramClient
    logger: logging.Logger
    phone_number: str
    telegram_user_id: Optional[str]
    channels_to_listen_from: list[str]

    _register_channel_listeners: Callable[[], None]

    async def disconnect_client(self) -> None:
        """Gracefully disconnects from Telegram."""
        if hasattr(self, "client") and self.client and self.client.is_connected():
            await self.client.disconnect()
            self.logger.info(f"Client '{self.telegram_user_id or 'unknown'}' disconnected from Telegram")

    async def _interactive_start(self) -> None:
        """
        Interactive start prompt via Telethon (uses terminal input()).
        Useful for CLI tools or scripts. Not suitable for headless/web apps.
        """
        await self.client.start(phone=self.phone_number)
        me = await self.client.get_me()
        self.telegram_user_id = str(me.id)
        self.logger.info(f"Interactive login successful for user {self.telegram_user_id}")

    async def interactive_start_listening_channels(self) -> None:
        """
        Starts client interactively (prompts for code on console if needed)
        and listens to configured channels.
        """
        if not self.channels_to_listen_from:
            raise ValueError("No channels configured to listen from. Use add_channel_to_listen() first.")

        await self._interactive_start()
        self._register_channel_listeners()
        self.logger.info(f"User '{self.telegram_user_id}' listening to {len(self.channels_to_listen_from)} channel(s)")
        await self.client.run_until_disconnected()

    def __enter__(self):
        """Prevent synchronous context manager usage."""
        raise RuntimeError("Use async context manager ('async with') instead of synchronous 'with'")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect_client()
