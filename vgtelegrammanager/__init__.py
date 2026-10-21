from importlib.metadata import PackageNotFoundError, version

from ._mixins.processing_mixin import MessageHandler
from ._utils import ChannelIdentifier
from .client import (
    TelegramUserManager,
    VGTelegramManager,
    telegram_dialog_from_telethon,
)
from .models import (
    TelegramDialog,
    TelegramDialogKind,
    TelegramDialogType,
    TelegramMessage,
)
from .webhook import verify_webhook_signature

try:
    __version__ = version("vg-telegram-manager")
except PackageNotFoundError:  # running from a source checkout without installing
    __version__ = "0.0.0+unknown"

__all__ = [
    "VGTelegramManager",
    "TelegramUserManager",
    "TelegramDialog",
    "TelegramDialogKind",
    "TelegramDialogType",
    "TelegramMessage",
    "MessageHandler",
    "ChannelIdentifier",
    "telegram_dialog_from_telethon",
    "verify_webhook_signature",
]
