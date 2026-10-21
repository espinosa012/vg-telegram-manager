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


class TelegramDialog(BaseModel):
    """Represents a simplified Telegram dialog (channel, group, or user)."""
    id: int
    name: str
    username: Optional[str] = None
    access_hash: Optional[int] = None
    dialog_type: TelegramDialogType
    kind: str  # 'channel', 'supergroup', 'gigagroup', 'group', 'user', 'bot'
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
    phone: Optional[str] = None
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
