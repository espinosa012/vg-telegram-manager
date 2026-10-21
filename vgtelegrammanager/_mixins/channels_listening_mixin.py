from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from vgtelegrammanager._utils import ChannelIdentifier, channel_key

if TYPE_CHECKING:
    from telethon import TelegramClient

    from vgtelegrammanager._mixins.processing_mixin import MessageHandler


class ChannelsListeningMixin:
    """Mixin for managing channels and chats to listen from."""
    client: TelegramClient
    logger: logging.Logger
    telegram_user_id: Optional[str]
    channels_to_listen_from: list[ChannelIdentifier]
    _channel_callbacks: dict[ChannelIdentifier, list[MessageHandler]]
    _listening: bool

    if TYPE_CHECKING:
        # Provided by DiscoveryMixin, AuthMixin & ProcessingMixin.
        # Only declared for type checkers: a runtime stub would shadow the real
        # implementation in the MRO.
        async def _resolve_channel_identifier(self, channel: str) -> ChannelIdentifier: ...
        async def _ensure_authenticated(self, action: str) -> None: ...
        async def _set_telegram_user_id(self) -> None: ...
        def _register_channel_listeners(self) -> None: ...
        def _add_listener(self, listen_target: ChannelIdentifier) -> None: ...
        def _remove_listener(self, listen_target: ChannelIdentifier) -> None: ...
        def add_message_handler(
            self, handler: MessageHandler, channel: Optional[ChannelIdentifier] = None
        ) -> None: ...

    async def start_listening_channels(self) -> None:
        """
        Starts listening for new messages on all configured channels/chats.
        Blocks until client disconnects.
        """
        if not self.channels_to_listen_from:
            raise ValueError("No channels configured to listen from. Use add_channel_to_listen() first.")

        await self._ensure_authenticated("start listening")
        await self._set_telegram_user_id()
        self._register_channel_listeners()
        self.logger.info(
            "User '%s' started listening to %d channel(s)",
            self.telegram_user_id,
            len(self.channels_to_listen_from),
        )

        await self.client.run_until_disconnected()

    def _find_listening_channel(self, channel: ChannelIdentifier) -> Optional[ChannelIdentifier]:
        """Returns the stored identifier equivalent to `channel` (ignoring '@' and case), if any."""
        key = channel_key(channel)
        return next((c for c in self.channels_to_listen_from if channel_key(c) == key), None)

    async def add_channel_to_listen(
        self,
        channel: ChannelIdentifier,
        callback: Optional[MessageHandler] = None,
    ) -> bool:
        """
        Adds a channel, chat, or 'me' (Saved Messages) to the listening list.

        Args:
            channel: Username (@user), username without @, 'me'/'self', numeric peer ID,
                or full channel display name.
            callback: Optional sync or async callback called when a message arrives from this channel.

        Returns:
            True if channel was newly added, False if already in list.
        """
        if isinstance(channel, int) and not isinstance(channel, bool):
            resolved: ChannelIdentifier = channel
        elif isinstance(channel, str) and channel.strip():
            resolved = await self._resolve_channel_identifier(channel.strip())
        else:
            raise ValueError("Channel must be a non-empty string or a numeric peer ID")

        if callback is not None:
            self.add_message_handler(callback, resolved)

        existing = self._find_listening_channel(resolved)
        if existing is not None:
            self.logger.warning("Channel '%s' is already being monitored", existing)
            return False

        self.channels_to_listen_from.append(resolved)
        self.logger.info("Added channel to monitor: '%s'", resolved)
        if self._listening:
            self._add_listener(resolved)
        return True

    def remove_channel_to_listen(self, channel_identifier: ChannelIdentifier) -> bool:
        """
        Removes a channel from the listening list, detaching its Telethon listener
        and dropping its channel-specific callbacks.

        Args:
            channel_identifier: Channel identifier as returned/stored by add_channel_to_listen.
                A leading '@' and letter case are ignored.
        """
        stored = self._find_listening_channel(channel_identifier)
        if stored is None:
            return False

        self.channels_to_listen_from.remove(stored)
        self._remove_listener(stored)
        self._channel_callbacks.pop(channel_key(stored), None)
        self.logger.info("Removed channel '%s' from monitor list", stored)
        return True

    def get_listening_channels(self) -> list[ChannelIdentifier]:
        """Returns a copy of the list of monitored channels."""
        return self.channels_to_listen_from.copy()
