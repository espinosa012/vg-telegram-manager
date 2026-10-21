from __future__ import annotations

from typing import Union

ChannelIdentifier = Union[str, int]


def channel_key(channel: ChannelIdentifier) -> ChannelIdentifier:
    """
    Normalizes a channel identifier for comparisons and dict lookups.

    Usernames are case-insensitive and may or may not carry a leading '@';
    'self' is an alias of 'me'. Numeric peer IDs are returned unchanged.
    """
    if isinstance(channel, int):
        return channel
    key = channel.strip().lstrip("@").lower()
    return "me" if key == "self" else key


def mask_phone(phone: str) -> str:
    """Masks a phone number for logging, keeping only its prefix and last two digits."""
    if len(phone) <= 5:
        return "*" * len(phone)
    return f"{phone[:3]}{'*' * (len(phone) - 5)}{phone[-2:]}"
