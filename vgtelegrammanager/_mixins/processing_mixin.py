from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, Optional, Union

import requests
import requests.exceptions
from telethon import TelegramClient, events

from vgtelegrammanager._utils import ChannelIdentifier, channel_key
from vgtelegrammanager.models import TelegramMessage
from vgtelegrammanager.webhook import sign_webhook_body

# Type alias for message handlers
MessageHandler = Callable[[TelegramMessage], Union[None, Awaitable[None]]]

# Statuses worth retrying: the request may succeed later without changes
_RETRYABLE_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
_MAX_LOGGED_RESPONSE_CHARS = 500


class ProcessingMixin:
    """Mixin for message listening, callback dispatching, and optional HTTP forwarding."""
    client: TelegramClient
    logger: logging.Logger
    telegram_user_id: Optional[str]
    process_messages_endpoint: Optional[str]
    webhook_secret: Optional[str]
    channels_to_listen_from: list[ChannelIdentifier]
    _channel_callbacks: dict[ChannelIdentifier, list[MessageHandler]]
    _global_callbacks: list[MessageHandler]
    _listeners: dict[ChannelIdentifier, Callable[[events.NewMessage.Event], Awaitable[None]]]
    _listening: bool
    _http_session: Optional[requests.Session]

    # Webhook delivery settings; override per instance if needed
    webhook_timeout: float = 30
    webhook_max_attempts: int = 3
    webhook_backoff_seconds: float = 1.0

    def add_message_handler(
        self, handler: MessageHandler, channel: Optional[ChannelIdentifier] = None
    ) -> None:
        """
        Registers a custom message handler.

        Args:
            handler: Sync or async callable that receives a TelegramMessage instance.
            channel: If specified, only messages from this channel trigger the handler.
                     If None, handler is called for all monitored channels.
        """
        if channel is None or channel == "":
            self._global_callbacks.append(handler)
        else:
            self._channel_callbacks.setdefault(channel_key(channel), []).append(handler)

    def _register_channel_listeners(self) -> None:
        """
        Register a new-message listener for every configured channel or chat.
        Idempotent: channels that already have a listener are skipped. Once called,
        channels added later via add_channel_to_listen() are registered immediately.
        """
        for channel in self.channels_to_listen_from:
            self._add_listener(channel)
        self._listening = True

    def _add_listener(self, listen_target: ChannelIdentifier) -> None:
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
                chat_name = (
                    getattr(chat, "username", None)
                    or getattr(chat, "title", None)
                    or str(listen_target)
                )

                payload = TelegramMessage(
                    telegram_message_id=message_id,
                    telegram_user_id=self.telegram_user_id,
                    from_telegram_chat_id=chat_id,
                    from_telegram_chat_name=chat_name,
                    content=message_text,
                    timestamp=event.message.date or datetime.now(timezone.utc),
                    raw_event=event,
                )

                await self._dispatch_message(listen_target, payload)

            except Exception as e:
                self.logger.error("Error handling message from '%s': %s", listen_target, e, exc_info=True)

        # Telethon accepts usernames, IDs, and 'me' in chats parameter
        self.client.add_event_handler(_handler, events.NewMessage(chats=listen_target))
        self._listeners[listen_target] = _handler
        self.logger.info("Registered listener for '%s'", listen_target)

    def _remove_listener(self, listen_target: ChannelIdentifier) -> None:
        """Detaches the Telethon handler for the specified chat/channel, if any."""
        handler = self._listeners.pop(listen_target, None)
        if handler is not None:
            self.client.remove_event_handler(handler)
            self.logger.info("Unregistered listener for '%s'", listen_target)

    async def _dispatch_message(self, channel: ChannelIdentifier, message: TelegramMessage) -> None:
        """Dispatches incoming message to registered handlers and optional HTTP endpoint."""
        # 1. Channel-specific handlers
        for handler in self._channel_callbacks.get(channel_key(channel), []):
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
                await handler(message)  # type: ignore[misc]
            else:
                result = await asyncio.to_thread(handler, message)
                # Sync callables may still return an awaitable (e.g. a lambda wrapping a coroutine)
                if inspect.isawaitable(result):
                    await result
        except Exception as e:
            handler_name = getattr(handler, "__name__", None) or repr(handler)
            self.logger.error("Handler %s raised error: %s", handler_name, e, exc_info=True)

    def _get_http_session(self) -> requests.Session:
        """Returns a shared HTTP session so webhook calls reuse connections (keep-alive)."""
        if self._http_session is None:
            self._http_session = requests.Session()
        return self._http_session

    def _close_http_session(self) -> None:
        if self._http_session is not None:
            self._http_session.close()
            self._http_session = None

    async def _send_message_to_endpoint(self, payload_json: dict[str, Any]) -> None:
        """
        Posts serialised message JSON to configured HTTP endpoint, signing it when a
        webhook secret is configured. Timeouts, connection errors and transient HTTP
        statuses are retried with exponential backoff.
        """
        endpoint = self.process_messages_endpoint
        if not endpoint:
            return

        message_id = payload_json.get("telegram_message_id", "unknown")
        body = json.dumps(payload_json, separators=(",", ":"), ensure_ascii=False).encode()
        headers = {"Content-Type": "application/json"}
        if self.webhook_secret:
            headers.update(sign_webhook_body(self.webhook_secret, body))

        session = self._get_http_session()
        for attempt in range(1, self.webhook_max_attempts + 1):
            try:
                response = await asyncio.to_thread(
                    session.post, endpoint, data=body, headers=headers, timeout=self.webhook_timeout
                )
            except requests.exceptions.RequestException as e:
                error = f"{type(e).__name__}: {e}"
                retryable = isinstance(
                    e, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
                )
            else:
                if 200 <= response.status_code < 300:
                    self.logger.info("Message '%s' successfully forwarded to endpoint.", message_id)
                    return
                error = (
                    f"Status: {response.status_code}, "
                    f"Response: {response.text[:_MAX_LOGGED_RESPONSE_CHARS]!r}"
                )
                retryable = response.status_code in _RETRYABLE_STATUSES

            if not retryable or attempt == self.webhook_max_attempts:
                self.logger.error(
                    "Failed to forward message '%s' after %d attempt(s). %s", message_id, attempt, error
                )
                return

            delay = self.webhook_backoff_seconds * 2 ** (attempt - 1)
            self.logger.warning(
                "Forwarding message '%s' failed (%s); retrying in %.1fs", message_id, error, delay
            )
            await asyncio.sleep(delay)


def _is_async_callable(handler: Any) -> bool:
    """True for coroutine functions, including partials and objects with an async __call__."""
    return inspect.iscoroutinefunction(handler) or inspect.iscoroutinefunction(
        type(handler).__call__
    )
