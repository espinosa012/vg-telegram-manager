from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import inspect
import logging
from typing import Any, Optional, Union

import requests
import requests.exceptions
from telethon import TelegramClient, events

from vgtelegrammanager.models import TelegramMessage

# Type alias for message handlers
MessageHandler = Callable[[TelegramMessage], Union[None, Awaitable[None]]]


class ProcessingMixin:
    """Mixin for message listening, callback dispatching, and optional HTTP forwarding."""
    client: TelegramClient
    logger: logging.Logger
    telegram_user_id: Optional[str]
    process_messages_endpoint: Optional[str]
    channels_to_listen_from: list[str]
    _channel_callbacks: dict[str, list[MessageHandler]]
    _global_callbacks: list[MessageHandler]
    _listeners: dict[str, Callable[[events.NewMessage.Event], Awaitable[None]]]
    _listening: bool

    def add_message_handler(self, handler: MessageHandler, channel: Optional[str] = None) -> None:
        """
        Registers a custom message handler.

        Args:
            handler: Sync or async callable that receives a TelegramMessage instance.
            channel: If specified, only messages from this channel trigger the handler.
                     If None, handler is called for all monitored channels.
        """
        if channel:
            target = channel.strip()
            self._channel_callbacks.setdefault(target, []).append(handler)
        else:
            self._global_callbacks.append(handler)

    def _register_channel_listeners(self) -> None:
        """
        Register a new-message listener for every configured channel or chat.
        Idempotent: channels that already have a listener are skipped. Once called,
        channels added later via add_channel_to_listen() are registered immediately.
        """
        for channel in self.channels_to_listen_from:
            self._add_listener(channel)
        self._listening = True

    def _add_listener(self, listen_target: str) -> None:
        """
        Attaches a Telethon NewMessage handler for the specified chat/channel,
        unless one is already attached. Using chats=... ensures both regular channel
        posts and messages forwarded to 'me' (Saved Messages) are correctly received.
        """
        if listen_target in self._listeners:
            return

        async def _handler(event: events.NewMessage.Event) -> None:
            try:
                message_text = event.message.message or ""
                message_id = str(event.message.id)
                chat_id = str(event.chat_id)
                chat = event.chat
                chat_name = getattr(chat, "username", None) or getattr(chat, "title", None) or str(listen_target)

                payload = TelegramMessage(
                    telegram_message_id=message_id,
                    telegram_user_id=self.telegram_user_id,
                    from_telegram_chat_id=chat_id,
                    from_telegram_chat_name=chat_name,
                    content=message_text,
                    timestamp=datetime.now(timezone.utc),
                    raw_event=event,
                )

                await self._dispatch_message(listen_target, payload)

            except Exception as e:
                self.logger.error(f"Error handling message from '{listen_target}': {e}", exc_info=True)

        # Telethon accepts usernames, IDs, and 'me' in chats parameter
        self.client.add_event_handler(_handler, events.NewMessage(chats=listen_target))
        self._listeners[listen_target] = _handler
        self.logger.info(f"Registered listener for '{listen_target}'")

    def _remove_listener(self, listen_target: str) -> None:
        """Detaches the Telethon handler for the specified chat/channel, if any."""
        handler = self._listeners.pop(listen_target, None)
        if handler is not None:
            self.client.remove_event_handler(handler)
            self.logger.info(f"Unregistered listener for '{listen_target}'")

    async def _dispatch_message(self, channel: str, message: TelegramMessage) -> None:
        """Dispatches incoming message to registered handlers and optional HTTP endpoint."""
        # 1. Channel-specific handlers
        for handler in self._channel_callbacks.get(channel, []):
            await self._invoke_handler(handler, message)

        # Also check without leading '@'
        norm_channel = channel.lstrip("@")
        if norm_channel != channel:
            for handler in self._channel_callbacks.get(norm_channel, []):
                await self._invoke_handler(handler, message)

        # 2. Global handlers
        for handler in self._global_callbacks:
            await self._invoke_handler(handler, message)

        # 3. Optional HTTP endpoint forwarding
        if self.process_messages_endpoint:
            payload_dict = message.model_dump(mode="json", exclude={"raw_event"})
            await self._send_message_to_endpoint(payload_dict)

    async def _invoke_handler(self, handler: MessageHandler, message: TelegramMessage) -> None:
        try:
            if _is_async_callable(handler):
                await handler(message)
            else:
                result = await asyncio.to_thread(handler, message)
                # Sync callables may still return an awaitable (e.g. a lambda wrapping a coroutine)
                if inspect.isawaitable(result):
                    await result
        except Exception as e:
            handler_name = getattr(handler, "__name__", None) or repr(handler)
            self.logger.error(f"Handler {handler_name} raised error: {e}", exc_info=True)

    async def _send_message_to_endpoint(self, payload_json: dict[str, Any]) -> None:
        """Posts serialised message JSON to configured HTTP endpoint."""
        if not self.process_messages_endpoint:
            return

        message_id = payload_json.get("telegram_message_id", "unknown")
        try:
            response = await asyncio.to_thread(
                requests.post,
                url=self.process_messages_endpoint,
                json=payload_json,
                timeout=30,
            )

            if 200 <= response.status_code < 300:
                self.logger.info(f"Message '{message_id}' successfully forwarded to endpoint.")
            else:
                self.logger.error(
                    f"Failed to forward message '{message_id}'. Status: {response.status_code}, Response: {response.text}"
                )
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout forwarding message '{message_id}'")
        except requests.exceptions.ConnectionError:
            self.logger.error(f"Connection error forwarding message '{message_id}'")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error forwarding message '{message_id}': {e}")


def _is_async_callable(handler: Any) -> bool:
    """True for coroutine functions, including partials and objects with an async __call__."""
    return inspect.iscoroutinefunction(handler) or inspect.iscoroutinefunction(
        getattr(handler, "__call__", None)
    )
