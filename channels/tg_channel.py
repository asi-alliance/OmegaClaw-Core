import asyncio
import time
import threading
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


class _TelegramChannel:
    """Telegram bot channel with windowed batching and bot-tag gating."""

    def __init__(self):
        self.running = False
        self.thread = None
        self.loop = None
        self.application = None
        self.connected = False
        self.chat_id = None
        self.bot_username = None
        self.msg_lock = threading.Lock()
        # Windowed batching state
        self._message_buffer = []  # List of (timestamp, name, text, message_id)
        self._should_reply = False
        self._last_processed_window = ""
        self._reply_to = None

    def get_last_message(self):
        """Retrieve and consume the most recent processed window, thread-safe."""
        with self.msg_lock:
            tmp = self._last_processed_window
            self._last_processed_window = ""
            return tmp

    async def _start_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command."""
        if update.effective_chat is not None:
            self.chat_id = update.effective_chat.id
        if update.message is not None:
            await update.message.reply_text(
                "Telegram channel ready. Observation mode active. Tag me to get a reply."
            )

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Capture group messages into the buffer; flag reply if bot is tagged."""
        if update.message is None or update.message.text is None:
            return
        # Filter out messages from other bots
        if update.message.from_user and update.message.from_user.is_bot:
            return
        if update.effective_chat is not None:
            self.chat_id = update.effective_chat.id

        user = update.effective_user
        if user is None:
            name = "unknown user"
        else:
            name = user.full_name or user.username or str(user.id)
        text = update.message.text

        with self.msg_lock:
            self._message_buffer.append(
                (time.time(), name, text, update.message.message_id)
            )
            # Check if bot is @-tagged
            if self.bot_username and f"@{self.bot_username}" in text:
                self._should_reply = True
            # Check if it's a direct reply to the bot
            if (
                update.message.reply_to_message
                and update.message.reply_to_message.from_user
                and update.message.reply_to_message.from_user.id == context.bot.id
            ):
                self._should_reply = True

    async def _window_manager(self):
        """Every 60s, batch buffered messages and surface them if bot was tagged."""
        while self.running:
            await asyncio.sleep(60)
            with self.msg_lock:
                if not self._message_buffer:
                    continue
                if self._should_reply:
                    batched = "\n".join(
                        [f"{m[1]}: {m[2]}" for m in self._message_buffer]
                    )
                    self._last_processed_window = batched
                    # Use the last message's id for reply threading
                    self._reply_to = self._message_buffer[-1][3]
                    self._should_reply = False
                # Clear buffer each window
                self._message_buffer = []

    async def _runner(self, token):
        """Build the Telegram application, start polling, and run until stopped."""
        self.application = Application.builder().token(token).build()

        # Get bot username for tag detection
        bot_info = await self.application.bot.get_me()
        self.bot_username = bot_info.username

        self.application.add_handler(CommandHandler("start", self._start_cmd))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message)
        )
        await self.application.initialize()
        await self.application.start()
        if self.application.updater is not None:
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES
            )
        self.connected = True

        # Start window manager
        asyncio.create_task(self._window_manager())

        try:
            while self.running:
                await asyncio.sleep(0.5)
        finally:
            self.connected = False
            if (
                self.application is not None
                and self.application.updater is not None
            ):
                await self.application.updater.stop()
            if self.application is not None:
                await self.application.stop()
                await self.application.shutdown()

    def _thread_main(self, token):
        """Create a dedicated asyncio event loop and run the bot in it."""
        loop = asyncio.new_event_loop()
        self.loop = loop
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._runner(token))
        loop.close()
        self.loop = None

    def start(self, bot_token, chat_id=None):
        """Launch the Telegram bot on a daemon thread and begin polling for messages."""
        self.running = True
        self.chat_id = chat_id or None
        self.thread = threading.Thread(
            target=self._thread_main, args=(bot_token,), daemon=True
        )
        self.thread.start()
        return self.thread

    def stop(self):
        """Signal the polling loop to stop gracefully."""
        self.running = False

    def send_message(self, text):
        """Send a text message to the active chat, dispatched to the bot's event loop."""
        text = text.replace("\\n", "\n")
        if (
            not self.connected
            or self.application is None
            or self.loop is None
            or self.chat_id is None
        ):
            return
        fut = asyncio.run_coroutine_threadsafe(
            self.application.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                reply_to_message_id=self._reply_to,
            ),
            self.loop,
        )
        try:
            fut.result(timeout=10)
        except Exception:
            pass


_channel = _TelegramChannel()


def getLastMessage():
    """Return the last received message from the Telegram chat."""
    return _channel.get_last_message()


def start_telegram(bot_token, chat_id):
    """Initialize and start the Telegram bot with the given token."""
    return _channel.start(bot_token, chat_id)


def stop_telegram():
    """Stop the running Telegram bot."""
    _channel.stop()


def send_message(text):
    """Send a text message to the active Telegram chat."""
    _channel.send_message(text)
