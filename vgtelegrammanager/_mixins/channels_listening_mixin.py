from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Awaitable, Callable, Optional

if TYPE_CHECKING:
    from telethon import TelegramClient
    from vgtelegrammanager._mixins.processing_mixin import MessageHandler


class ChannelsListeningMixin:
    """Mixin for managing channels and chats to listen from."""
    client: TelegramClient
    logger: logging.Logger
    telegram_user_id: Optional[str]
    channels_to_listen_from: list[str]
    _channel_callbacks: dict[str, list[MessageHandler]]
    _listening: bool

    # Provided by DiscoveryMixin & AuthMixin
    _resolve_channel_identifier: Callable[..., Awaitable[str]]
    _ensure_client_ready: Callable[[], None]
    is_authenticated: Callable[[], Awaitable[bool]]
    _set_telegram_user_id: Callable[[], Awaitable[None]]
    _register_channel_listeners: Callable[[], None]
    _add_listener: Callable[[str], None]
    _remove_listener: Callable[[str], None]
    add_message_handler: Callable[[MessageHandler, Optional[str]], None]

    async def start_listening_channels(self) -> None:
        """
        Starts listening for new messages on all configured channels/chats.
        Blocks until client disconnects.
        """
        self._ensure_client_ready()

        if not self.channels_to_listen_from:
            raise ValueError("No channels configured to listen from. Use add_channel_to_listen() first.")

        if not await self.is_authenticated():
            raise RuntimeError("Client not authenticated. Complete authentication flow first.")

        await self._set_telegram_user_id()
        self._register_channel_listeners()
        self.logger.info(f"User '{self.telegram_user_id}' started listening to {len(self.channels_to_listen_from)} channel(s)")

        await self.client.run_until_disconnected()

    async def add_channel_to_listen(
        self,
        channel: str,
        callback: Optional[MessageHandler] = None,
    ) -> bool:
        """
        Adds a channel, chat, or 'me' (Saved Messages) to the listening list.

        Args:
            channel: Username (@user), username without @, 'me'/'self', or full channel display name.
            callback: Optional sync or async callback called when a message arrives from this channel.

        Returns:
            True if channel was newly added, False if already in list.
        """
        if not channel or not isinstance(channel, str):
            raise ValueError("Channel must be a non-empty string")

        resolved = await self._resolve_channel_identifier(channel.strip())

        if callback is not None:
            self.add_message_handler(callback, channel=resolved)

        if resolved not in self.channels_to_listen_from:
            self.channels_to_listen_from.append(resolved)
            self.logger.info(f"Added channel to monitor: '{resolved}'")
            if self._listening:
                self._add_listener(resolved)
            return True
        else:
            self.logger.warning(f"Channel '{resolved}' is already being monitored")
            return False

    def remove_channel_to_listen(self, channel_identifier: str) -> bool:
        """
        Removes a channel from the listening list, detaching its Telethon listener
        and dropping its channel-specific callbacks.

        Args:
            channel_identifier: Channel identifier as returned/stored by add_channel_to_listen.
        """
        target = channel_identifier.strip()
        # Check alternative with or without @
        alt = target.lstrip("@") if target.startswith("@") else f"@{target}"

        for candidate in (target, alt):
            if candidate in self.channels_to_listen_from:
                self.channels_to_listen_from.remove(candidate)
                self._remove_listener(candidate)
                self._channel_callbacks.pop(candidate, None)
                self._channel_callbacks.pop(candidate.lstrip("@"), None)
                self.logger.info(f"Removed channel '{candidate}' from monitor list")
                return True

        return False

    def get_listening_channels(self) -> list[str]:
        """Returns a copy of the list of monitored channels."""
        return self.channels_to_listen_from.copy()
