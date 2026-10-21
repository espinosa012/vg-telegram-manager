from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TelegramDialogType(str, Enum):
    """Types of Telegram dialogs matching Telethon entity class names."""
    CHANNEL = "Channel"
    USER = "User"
    CHAT = "Chat"


class TelegramDialogKind(str, Enum):
    """Finer-grained kind of a dialog. Compares equal to its plain string value."""
    CHANNEL = "channel"
    SUPERGROUP = "supergroup"
    GIGAGROUP = "gigagroup"
    GROUP = "group"
    USER = "user"
    BOT = "bot"


class TelegramDialog(BaseModel):
    """Represents a simplified Telegram dialog (channel, group, or user)."""
    id: int
    name: str
    username: Optional[str] = None
    # Lets anyone holding it address the entity; kept out of repr() so it does not end up in logs.
    access_hash: Optional[int] = Field(default=None, repr=False)
    dialog_type: TelegramDialogType
    kind: TelegramDialogKind
    extra_usernames: list[str] = Field(default_factory=list)

    # Channel / Group specific metadata
    verified: Optional[bool] = None
    scam: Optional[bool] = None
    fake: Optional[bool] = None
    restricted: Optional[bool] = None
    participants_count: Optional[int] = None
    date: Optional[datetime] = None

    # User specific metadata
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    # Personal data of a third party; kept out of repr() so it does not end up in logs.
    phone: Optional[str] = Field(default=None, repr=False)
    is_bot: Optional[bool] = None
    is_self: Optional[bool] = None
    premium: Optional[bool] = None

    # Dialog state
    unread_count: int = 0
    unread_mentions_count: int = 0
    pinned: bool = False


class TelegramMessage(BaseModel):
    """Standard message payload for events and forwarded data."""
    telegram_message_id: str
    telegram_user_id: Optional[str] = None
    from_telegram_chat_id: Optional[str] = None
    from_telegram_chat_name: Optional[str] = None
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_event: Optional[Any] = Field(default=None, exclude=True)
