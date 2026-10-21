from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncGenerator, Optional

from vgtelegrammanager._utils import ChannelIdentifier
from vgtelegrammanager.models import TelegramDialog, TelegramDialogKind, TelegramDialogType

if TYPE_CHECKING:
    from telethon import TelegramClient
    from telethon.tl.custom.dialog import Dialog
    from telethon.tl.custom.message import Message


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
            kind = TelegramDialogKind.GIGAGROUP
        elif getattr(entity, "megagroup", False):
            kind = TelegramDialogKind.SUPERGROUP
        else:
            kind = TelegramDialogKind.CHANNEL
    elif entity_type == "User":
        dialog_type = TelegramDialogType.USER
        kind = TelegramDialogKind.BOT if getattr(entity, "bot", False) else TelegramDialogKind.USER
    else:
        dialog_type = TelegramDialogType.CHAT
        kind = TelegramDialogKind.GROUP

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


def _requested_type_names(entity_types: Optional[list[TelegramDialogType]]) -> set[str]:
    if entity_types is None:
        entity_types = list(TelegramDialogType)
    if not isinstance(entity_types, list):
        raise ValueError("'entity_types' must be a list of TelegramDialogType values")
    return {ct.value for ct in entity_types}


class DiscoveryMixin:
    """Mixin for Telegram channels and dialogs discovery."""
    client: TelegramClient
    logger: logging.Logger

    if TYPE_CHECKING:
        # Provided by AuthMixin.
        # Only declared for type checkers: a runtime stub would shadow the real
        # implementation in the MRO.
        async def _ensure_authenticated(self, action: str) -> None: ...

    async def _resolve_channel_identifier(self, channel: str) -> ChannelIdentifier:
        """
        Resolves channel identifier into a Telethon-usable target.

        Accepts:
          - 'me' or 'self' -> returns 'me' (Saved Messages).
          - '@username' -> returned as-is.
          - Numeric peer ID (e.g. '-1001234567890') -> returned as int.
          - Display name -> '@username' of the matching dialog, or its peer ID if it
            has no username (private chats and channels).
          - Anything else -> returned as-is (treated as a username by Telethon).
        """
        stripped = channel.strip()
        if stripped.lower() in ("me", "self"):
            return "me"
        if stripped.startswith("@"):
            return stripped
        if stripped.lstrip("-").isdigit():
            return int(stripped)

        try:
            dialog = await self._find_dialog_by_name(stripped)
        except LookupError:
            return stripped
        except RuntimeError as e:
            self.logger.warning(
                "Cannot look up '%s' by display name (%s); treating it as a username", stripped, e
            )
            return stripped

        username = telegram_dialog_from_telethon(dialog).username
        # dialog.id is the marked peer ID (e.g. -100... for channels) that Telethon expects
        return f"@{username}" if username else dialog.id

    async def _find_dialog_by_name(
        self,
        name: str,
        entity_types: Optional[list[TelegramDialogType]] = None,
    ) -> Dialog:
        """Returns the first dialog whose display name matches exactly, without listing the rest."""
        requested_types = _requested_type_names(entity_types)
        await self._ensure_authenticated("search dialogs")

        async for dialog in self.client.iter_dialogs():
            if dialog.name == name and type(dialog.entity).__name__ in requested_types:
                return dialog

        raise LookupError(f"No dialog found with name '{name}'")

    async def iter_messages_from_dialog(self, chat: str) -> AsyncGenerator[Message, None]:
        """
        Async generator yielding messages from `chat`, newest first.
        """
        if not chat or not isinstance(chat, str):
            raise ValueError("'chat' must be a non-empty string")

        await self._ensure_authenticated("iterate messages")

        resolved = await self._resolve_channel_identifier(chat)
        self.logger.info("Iterating messages from '%s'", resolved)
        async for msg in self.client.iter_messages(resolved):
            yield msg

    async def get_messages_from_dialog(self, chat: str, n: int) -> list[Message]:
        """
        Retrieves the last n messages from a dialog.
        """
        if not chat or not isinstance(chat, str):
            raise ValueError("'chat' must be a non-empty string")
        if not isinstance(n, int) or n <= 0:
            raise ValueError("'n' must be a positive integer")

        await self._ensure_authenticated("get messages")

        resolved = await self._resolve_channel_identifier(chat)
        messages = await self.client.get_messages(resolved, limit=n)
        self.logger.info("Retrieved %d message(s) from '%s'", len(messages), resolved)
        return list(messages)

    async def get_dialog_username_by_name(
        self,
        channel_name: str,
        entity_types: Optional[list[TelegramDialogType]] = None,
    ) -> Optional[str]:
        """
        Finds a dialog by exact display name and returns its username (without '@'),
        or None if the dialog has no public username.

        Raises:
            LookupError: If no dialog matches.
        """
        if not channel_name or not isinstance(channel_name, str):
            raise ValueError("'channel_name' must be a non-empty string")

        dialog = await self._find_dialog_by_name(channel_name, entity_types)
        username = telegram_dialog_from_telethon(dialog).username
        self.logger.info("Dialog '%s' found with username: %s", channel_name, username)
        return username

    async def get_user_dialogs(
        self,
        entity_types: Optional[list[TelegramDialogType]] = None,
    ) -> list[TelegramDialog]:
        """
        Returns the user's dialogs filtered by entity type.
        """
        requested_types = _requested_type_names(entity_types)
        await self._ensure_authenticated("get dialogs")

        dialogs: list[TelegramDialog] = []
        async for dialog in self.client.iter_dialogs():
            if type(dialog.entity).__name__ in requested_types:
                dialogs.append(telegram_dialog_from_telethon(dialog))

        self.logger.info("Found %d dialog(s) for types %s", len(dialogs), sorted(requested_types))
        return dialogs
