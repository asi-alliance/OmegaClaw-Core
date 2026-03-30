import asyncio
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
    """Telegram bot channel using polling-based message retrieval."""

    def __init__(self):
        self.running = False
        self.thread = None
        self.loop = None
        self.application = None
        self.last_message = None
        self.chat_id = None
        self.msg_lock = threading.Lock()
        self.connected = False

    def set_last(self, msg):
        """Store a message as the most recent received message, thread-safe."""
        with self.msg_lock:
            self.last_message = msg

    def get_last_message(self):
        """Retrieve the most recent received message, thread-safe."""
        with self.msg_lock:
            return self.last_message

    async def _start_cmd(self, update: Update):
        """Handle the /start command and register the chat ID."""
        if update.effective_chat is not None:
            self.chat_id = update.effective_chat.id
        if update.message is not None:
            await update.message.reply_text("Telegram channel ready.")

    async def _on_message(self, update: Update):
        """Capture incoming text messages and store them with the sender's name."""
        if update.message is None or update.message.text is None:
            return
        if update.effective_chat is not None:
            self.chat_id = update.effective_chat.id
        user = update.effective_user
        if user is None:
            name = "unknown user"
        else:
            name = user.full_name or user.username or str(user.id)
        self.set_last(f"{name}: {update.message.text}")

    async def _runner(self, token):
        """Build the Telegram application, start polling, and run until stopped."""
        self.application = Application.builder().token(token).build()
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
            self.application.bot.send_message(chat_id=self.chat_id, text=text),
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


def start_telegram(bot_token, chat_id=None):
    """Initialize and start the Telegram bot with the given token."""
    return _channel.start(bot_token, chat_id)


def stop_telegram():
    """Stop the running Telegram bot."""
    _channel.stop()


def send_message(text):
    """Send a text message to the active Telegram chat."""
    _channel.send_message(text)
