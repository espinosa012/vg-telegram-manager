# vg-telegram-manager

A versatile, high-level Telegram **user-client manager** built on top of [Telethon](https://github.com/LonamiWebs/Telethon). It allows you to monitor channels, groups, and Saved Messages (`'me'`), process incoming messages with custom Python callbacks, and optionally forward them to HTTP endpoints.

Unlike standard Telegram bots, a **user-client** connects with an authorized Telegram account, allowing it to read any public or private channel/group your account has joined.

---

## Features

- 🔐 **Headless & Interactive Auth** — Complete verification code flows programmatically (ideal for web apps/APIs) or interactively in CLI scripts.
- 📡 **Multi-Channel Listener** — Monitor public/private channels, supergroups, and Saved Messages (`'me'`).
- ⚡ **Flexible Event Handlers** — Register custom sync or async Python callbacks globally or per channel.
- 🌐 **Optional HTTP Forwarding** — Automatically post incoming messages as JSON to a configurable webhook endpoint without blocking the async event loop.
- 💬 **Saved Messages ('me') Support** — Monitor your own "Saved Messages" chat, including messages forwarded from mobile or desktop.
- 🔍 **Dialog & Message Discovery** — List user dialogs, search channels by name, and read recent message history.
- 🗂️ **Session Persistence** — Telethon SQLite session files keep authentication active across restarts.
- 🔄 **Async Context Manager** — Clean lifecycle management (`async with VGTelegramManager(...)`).
- 🛡️ **Zero Vendor Coupling** — Standalone library with standard PyPI dependencies (`telethon`, `pydantic`, `requests`).

---

## Installation

```bash
pip install git+https://github.com/espinosa012/vg-telegram-manager.git
```

Or for development:

```bash
git clone https://github.com/espinosa012/vg-telegram-manager.git
cd vg-telegram-manager
pip install -e ".[dev]"   # or: uv sync --extra dev
```

Run the checks with `ruff check .`, `mypy` and `pytest`.

---

## Quick Start

### 1. Obtain Telegram API Credentials

Go to [https://my.telegram.org/apps](https://my.telegram.org/apps), create an application, and retrieve your **API ID** and **API Hash**.

---

### 2. Authentication

#### Programmatic Flow (for Web APIs and Headless Services)

```python
import asyncio
from getpass import getpass

from telethon.errors import SessionPasswordNeededError
from vgtelegrammanager import VGTelegramManager

API_ID = 12345678
API_HASH = "your_api_hash"
PHONE = "+34600000000"
SESSION = "sessions/user.session"

async def authenticate():
    client = VGTelegramManager(
        api_id=API_ID,
        api_hash=API_HASH,
        phone_number=PHONE,
        session_file_path=SESSION,
    )

    await client.connect_client()

    if not await client.is_authenticated():
        # Request code (sent to Telegram app by default)
        await client.request_verification_code()
        
        # In a web app, receive this code from user input/form
        code = input("Enter verification code: ")
        try:
            await client.verify_code(code)
        except SessionPasswordNeededError:
            # Account has two-step verification enabled
            await client.verify_password(getpass("Enter 2FA password: "))

    print("Authenticated successfully!")
    await client.disconnect_client()

asyncio.run(authenticate())
```

> **Note:** Once authenticated, the session file stores the credentials. Subsequent runs do not require code verification.
> The session file grants full access to the account: it is created with owner-only permissions (`0600`, directory `0700`). Never commit or share it.

#### Interactive Flow (CLI Scripts)

```python
import asyncio
from vgtelegrammanager import VGTelegramManager

async def main():
    async with VGTelegramManager(
        api_id=12345678,
        api_hash="your_api_hash",
        phone_number="+34600000000",
        session_file_path="sessions/user.session",
    ) as client:
        await client.add_channel_to_listen("@my_channel")
        await client.interactive_start_listening_channels()

asyncio.run(main())
```

---

## Listening to Channels and Saved Messages

### Using Custom Python Callbacks

You can register callbacks globally or specifically for particular channels:

```python
import asyncio
from vgtelegrammanager import VGTelegramManager, TelegramMessage

async def on_all_messages(msg: TelegramMessage):
    print(f"[{msg.from_telegram_chat_name}] {msg.content}")

async def on_saved_notes(msg: TelegramMessage):
    print(f"New saved message: {msg.content}")

async def main():
    client = VGTelegramManager(
        api_id=12345678,
        api_hash="your_api_hash",
        phone_number="+34600000000",
        session_file_path="sessions/user.session",
    )

    await client.connect_client()

    # Global handler
    client.add_message_handler(on_all_messages)

    # Monitor standard channels
    await client.add_channel_to_listen("@tech_news")
    
    # Monitor Telegram 'Saved Messages' with a specific callback
    await client.add_channel_to_listen("me", callback=on_saved_notes)

    # Blocks until disconnected
    await client.start_listening_channels()

asyncio.run(main())
```

### Forwarding to an HTTP Endpoint (Webhook)

If you pass `process_messages_endpoint`, all incoming messages are automatically POSTed to that URL as JSON. Connections are reused between messages, and timeouts, connection errors and transient statuses (408, 425, 429, 5xx) are retried up to 3 times with exponential backoff (tune with the `webhook_max_attempts`, `webhook_backoff_seconds` and `webhook_timeout` attributes). Any 2xx response counts as delivered.

Use HTTPS: a plain `http://` endpoint outside localhost logs a warning, because message contents would travel unencrypted.

```python
client = VGTelegramManager(
    api_id=12345678,
    api_hash="your_api_hash",
    phone_number="+34600000000",
    session_file_path="sessions/user.session",
    process_messages_endpoint="https://my-backend.example.com/api/telegram-webhook",
    webhook_secret="a-long-random-shared-secret",  # optional, signs every request
)
```

The payload sent to your endpoint matches `TelegramMessage`:

```json
{
  "telegram_message_id": "123456",
  "telegram_user_id": "987654321",
  "from_telegram_chat_id": "-1001234567890",
  "from_telegram_chat_name": "tech_news",
  "content": "Message body here...",
  "timestamp": "2026-10-21T06:30:00Z"
}
```

`timestamp` is the date the message was sent on Telegram.

#### Verifying webhook signatures

With `webhook_secret` set, each request carries an `X-VGTM-Timestamp` header and an `X-VGTM-Signature: sha256=<hex>` header, the HMAC-SHA256 of `"<timestamp>.<raw body>"`. Verify it on the receiving side against the **raw** body before trusting the payload:

```python
from vgtelegrammanager import verify_webhook_signature

if not verify_webhook_signature(
    secret, raw_body, headers["X-VGTM-Timestamp"], headers["X-VGTM-Signature"]
):
    return 401  # reject: forged, tampered with, or older than 5 minutes
```

---

## Dialog & Message Discovery

### List Dialogs

```python
from vgtelegrammanager import TelegramDialogType

# Filter by entity types (CHANNEL, USER, CHAT)
dialogs = await client.get_user_dialogs([TelegramDialogType.CHANNEL])
for d in dialogs:
    print(f"{d.name} (@{d.username}) - {d.kind.value}")  # kind is a TelegramDialogKind
```

### Retrieve Message History

```python
# Fetch last 10 messages from a channel or from 'me'
messages = await client.get_messages_from_dialog("@tech_news", n=10)
for msg in messages:
    print(msg.id, msg.message)
```

---

## API Reference

### `VGTelegramManager`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_id` | `int` | *required* | Telegram application API ID. |
| `api_hash` | `str` | *required* | Telegram application API hash. |
| `phone_number` | `str` | *required* | Phone number with country code. |
| `session_file_path` | `str` | *required* | Path to Telethon `.session` file. |
| `process_messages_endpoint` | `Optional[str]` | `None` | HTTP(S) URL to POST messages to. |
| `logger` | `Optional[logging.Logger]` | `None` | Custom logger (defaults to standard library logger). |
| `webhook_secret` | `Optional[str]` | `None` | Shared secret to HMAC-sign webhook requests. Requires `process_messages_endpoint`. |

### Key Methods

- **`connect_client()`**: Connects to Telegram MTProto servers.
- **`disconnect_client()`**: Disconnects gracefully.
- **`request_verification_code(force_sms=False)`**: Requests verification code via app or SMS. Returns the `phone_code_hash` (persist it if verification happens in another process).
- **`resend_verification_code_via_sms(phone_code_hash=None)`**: Requests SMS fallback. Returns the updated `phone_code_hash`.
- **`verify_code(code, password=None, phone_code_hash=None)`**: Submits verification code. Raises `SessionPasswordNeededError` if 2FA is enabled and no `password` is given.
- **`verify_password(password)`**: Completes login for accounts with two-step verification.
- **`is_authenticated()`**: Checks authorization status.
- **`add_channel_to_listen(channel, callback=None)`**: Subscribes to a channel: `'@username'`, `'me'`, a numeric peer ID, or a dialog display name (private chats without username resolve to their peer ID). Can be called while already listening.
- **`remove_channel_to_listen(channel)`**: Unsubscribes from channel, detaching its listener and channel-specific callbacks. A leading `@` and letter case are ignored.
- **`add_message_handler(handler, channel=None)`**: Registers sync/async callback.
- **`start_listening_channels()`**: Starts listening loop (blocking).
- **`get_user_dialogs(entity_types=None)`**: Lists user chats.
- **`get_messages_from_dialog(chat, n)`**: Reads last `n` messages.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
