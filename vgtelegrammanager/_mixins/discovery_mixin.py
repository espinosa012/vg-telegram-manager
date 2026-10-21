from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncGenerator, Optional

from vgtelegrammanager.models import TelegramDialog, TelegramDialogType

if TYPE_CHECKING:
    from telethon import TelegramClient
    from telethon.tl.custom.dialog import Dialog


def telegram_dialog_from_telethon(dialog: Dialog) -> TelegramDialog:
    """
    Constructs a TelegramDialog model from a Telethon Dialog object.
    """
    entity = dialog.entity
    raw = dialog.dialog
    entity_type = type(entity).__name__

    if entity_type == "Channel":
        dialog_type = TelegramDialogType.CHANNEL
        if getattr(entity, "gigagroup", False):
            kind = "gigagroup"
        elif getattr(entity, "megagroup", False):
            kind = "supergroup"
        else:
            kind = "channel"
    elif entity_type == "User":
        dialog_type = TelegramDialogType.USER
        kind = "bot" if getattr(entity, "bot", False) else "user"
    else:
        dialog_type = TelegramDialogType.CHAT
        kind = "group"

    username = getattr(entity, "username", None)
    raw_extra = getattr(entity, "usernames", None) or []
    extra_usernames = [
        u.username for u in raw_extra
        if getattr(u, "username", None) and u.username != username
    ]
    if not username and extra_usernames:
        username = extra_usernames.pop(0)

    return TelegramDialog(
        id=entity.id,
        name=dialog.name,
        username=username,
        access_hash=getattr(entity, "access_hash", None),
        dialog_type=dialog_type,
        kind=kind,
        extra_usernames=extra_usernames,
        verified=getattr(entity, "verified", None),
        scam=getattr(entity, "scam", None),
        fake=getattr(entity, "fake", None),
        restricted=getattr(entity, "restricted", None),
        participants_count=getattr(entity, "participants_count", None),
        date=getattr(entity, "date", None),
        first_name=getattr(entity, "first_name", None),
        last_name=getattr(entity, "last_name", None),
        phone=getattr(entity, "phone", None),
        is_bot=getattr(entity, "bot", None),
        is_self=getattr(entity, "is_self", None),
        premium=getattr(entity, "premium", None),
        unread_count=getattr(raw, "unread_count", 0) or 0,
        unread_mentions_count=getattr(raw, "unread_mentions_count", 0) or 0,
        pinned=bool(getattr(raw, "pinned", False)),
    )


class DiscoveryMixin:
    """Mixin for Telegram channels and dialogs discovery."""
    client: TelegramClient
    logger: logging.Logger

    # Required from AuthMixin & ValidationMixin
    def _ensure_client_ready(self) -> None: ...
    async def is_authenticated(self) -> bool: ...

    async def _resolve_channel_identifier(self, channel: str) -> str:
        """
        Resolves channel identifier into a Telethon-usable target.

        Accepts:
          - 'me' or 'self' -> returns 'me' (Saved Messages).
          - '@username' -> returned as-is.
          - 'username' -> returned as-is.
          - Display name -> searched via get_dialog_username_by_name().
        """
        stripped = channel.strip()
        if stripped.lower() in ("me", "self"):
            return "me"
        if stripped.startswith("@"):
            return stripped

        try:
            username = await self.get_dialog_username_by_name(stripped)
            return f"@{username}" if username else stripped
        except LookupError:
            return stripped

    async def iter_messages_from_dialog(self, chat: str) -> AsyncGenerator:
        """
        Async generator yielding messages from `chat`, newest first.
        """
        if not chat or not isinstance(chat, str):
            raise ValueError("'chat' must be a non-empty string")

        self._ensure_client_ready()
        if not await self.is_authenticated():
            raise RuntimeError("Cannot iterate messages: client not authenticated")

        resolved = await self._resolve_channel_identifier(chat)
        self.logger.info(f"Iterating messages from '{resolved}'")
        async for msg in self.client.iter_messages(resolved):
            yield msg

    async def get_messages_from_dialog(self, chat: str, n: int) -> list:
        """
        Retrieves the last n messages from a dialog.
        """
        if not chat or not isinstance(chat, str):
            raise ValueError("'chat' must be a non-empty string")
        if not isinstance(n, int) or n <= 0:
            raise ValueError("'n' must be a positive integer")

        self._ensure_client_ready()
        if not await self.is_authenticated():
            raise RuntimeError("Cannot get messages: client not authenticated")

        resolved = await self._resolve_channel_identifier(chat)
        messages = await self.client.get_messages(resolved, limit=n)
        self.logger.info(f"Retrieved {len(messages)} message(s) from '{resolved}'")
        return list(messages)

    async def get_dialog_username_by_name(
        self,
        channel_name: str,
        entity_types: Optional[list[TelegramDialogType]] = None,
    ) -> Optional[str]:
        """
        Finds a dialog by exact display name and returns its @username.
        """
        if not channel_name or not isinstance(channel_name, str):
            raise ValueError("'channel_name' must be a non-empty string")

        types = entity_types if entity_types is not None else list(TelegramDialogType)
        dialogs = await self.get_user_dialogs(types)
        for dialog in dialogs:
            if dialog.name == channel_name:
                self.logger.info(f"Dialog '{channel_name}' found with username: {dialog.username}")
                return dialog.username

        raise LookupError(f"No dialog found with name '{channel_name}'")

    async def get_user_dialogs(
        self,
        entity_types: Optional[list[TelegramDialogType]] = None,
    ) -> list[TelegramDialog]:
        """
        Returns the user's dialogs filtered by entity type.
        """
        if entity_types is None:
            entity_types = list(TelegramDialogType)
        if not isinstance(entity_types, list):
            raise ValueError("'entity_types' must be a list of TelegramDialogType values")

        self._ensure_client_ready()
        if not await self.is_authenticated():
            raise RuntimeError("Cannot get dialogs: client not authenticated")

        requested_types = {ct.value for ct in entity_types}
        dialogs: list[TelegramDialog] = []

        async for dialog in self.client.iter_dialogs():
            entity_type = type(dialog.entity).__name__
            if entity_type not in requested_types:
                continue
            dialogs.append(telegram_dialog_from_telethon(dialog))

        self.logger.info(f"Found {len(dialogs)} dialog(s) for types {[ct.value for ct in entity_types]}")
        return dialogs
