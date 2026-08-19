import asyncio
import time
import threading
import logging
import yaml
import os
import re
from io import BytesIO

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import BufferedInputFile
from aiogram.filters import Command
from aiogram.client.telegram import TelegramAPIServer
from aiogram.client.session.aiohttp import AiohttpSession

try:
    from telegramify_markdown import markdownify
except ImportError:
    def markdownify(x, *a, **k):
        return x

from config_helper import is_category_blocked, get_spam_protection_config
import media_handler
import channels
from config import config_get_by_key

# auth.py and delivery_queue.py are shared channel infrastructure, but they sit
# in core's channels/ folder and are only importable by plugins loaded from
# there. Put that folder on the path so a channel plugin living anywhere can
# reuse them instead of reimplementing the auth handshake and the send queue.
def _core_channel_infra():
    """Import core's auth module and outbound queue, adding core's channels/
    folder to sys.path on the first try that fails."""
    try:
        import auth
        from delivery_queue import PendingMessages
    except ModuleNotFoundError:
        import plugin
        plugin.addLocationToPath("{REPO}/channels")
        import auth
        from delivery_queue import PendingMessages
    return auth, PendingMessages


auth, PendingMessages = _core_channel_infra()

# A plugin must not reconfigure the host's root logging or create files on
# import (the fork's tg_channel called logging.basicConfig with a FileHandler
# here). The channel's logging.info/error calls route to whatever the host has
# configured, matching the other plugin modules.

class _TelegramChannel:
    """Telegram bot channel with windowed batching and bot-tag gating using aiogram."""

    def __init__(self, config_path=None):
        self.config_path = os.path.join(os.path.dirname(__file__), "telegram_profile.yaml")
        self.policy_path = os.path.join(os.path.dirname(__file__), "policy.md")
        self.running = False
        self.thread = None
        self.loop = None
        self.bot = None
        self.dp = None
        self.connected = False
        self.chat_id = None
        self.allowed_chat_id = None
        self.allowed_chat_ids = set()
        
        self.bot_username = None
        self.bot_id = None
        self.msg_lock = threading.Lock()
        
        # Default settings
        self.reply_only_on_tag = True
        self.reply_on_reply = True
        self.admin_ids = []
        self.dm_enabled = False
        self.restrict_to_config_chat = True
        self.allow_group_bots = False
        self.reply_constraints = None
        
        # Policy messages
        self.start_msg = "Telegram mode active."
        self.about_msg = "I am a MeTTaClaw agent."
        self.privacy_msg = "No sensitive data is stored."
        
        # Load config and policies if they exist
        self.load_config(self.config_path)
        self.load_policies()

        self._muted_users = {}
        self._user_msg_rates = {}
        self._user_mute_counts = {}
        
        # Windowed batching state
        self._message_queue = []
        self._reply_to_ids = {}
        self._reply_to_id = None
        self._paused_chats = set()
        self.search_disabled = False
        self._ready_windows = []
        self._polling_task = None
        # Queue outbound messages instead of dropping them: the agent sends its
        # version banner right after the channel starts, before the polling
        # thread has connected, and a send that fails should be retried.
        self._outbox = PendingMessages()
        self._typing_threads = {}
        self._TYPING_TIMEOUT = 120  # max seconds to show typing regardless of agent state

    def _normalize_chat_id(self, chat_id):
        if chat_id is None:
            return None

        chat_id = str(chat_id).strip("\"' ")
        if not chat_id:
            return None

        if not chat_id.startswith("-") and chat_id.isdigit() and len(chat_id) > 10:
            chat_id = f"-{chat_id}"

        return chat_id

    def _normalize_chat_ids(self, chat_ids):
        if chat_ids is None:
            return set()

        if isinstance(chat_ids, (list, tuple, set)):
            values = chat_ids
        else:
            values = str(chat_ids).split(",")

        normalized = set()
        for chat_id in values:
            value = self._normalize_chat_id(chat_id)
            if value:
                normalized.add(value)
        return normalized

    def _is_paused(self, chat_id):
        """Whether a chat is currently paused. Chat ids reach this class as ints
        from aiogram and as strings from /pause and the config file, so both
        sides go through the same normalizer — comparing the two forms directly
        never matches, which made /pause report success and do nothing."""
        return self._normalize_chat_id(chat_id) in self._paused_chats

    def _is_allowed_chat(self, chat_id):
        if not self.restrict_to_config_chat:
            return True

        if not self.allowed_chat_ids:
            return True

        return self._normalize_chat_id(chat_id) in self.allowed_chat_ids

    def load_config(self, config_path):
        """Load bot configuration from a YAML file."""
        if not os.path.exists(config_path):
            print(f"Config file {config_path} not found. Using defaults.")
            logging.warning(f"Config file {config_path} not found. Using defaults.")
            return

        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
            
            tg_cfg = config.get("telegram", {})
            self.window_seconds = tg_cfg.get("batching", {}).get("window_seconds", 10)
            self.reply_only_on_tag = tg_cfg.get("reply_only_when_directly_tagged", True)
            self.reply_on_reply = tg_cfg.get("reply_on_reply_to_bot", True)
            self.dm_enabled = tg_cfg.get("dm_support", {}).get("enabled", False)
            self.restrict_to_config_chat = tg_cfg.get("restrict_to_config_chat", True)
            self.allow_group_bots = tg_cfg.get("allow_group_bots", False)
            self.allowed_chat_ids = self._normalize_chat_ids(tg_cfg.get("allowed_chats", []))
            self.allowed_chat_id = next(iter(self.allowed_chat_ids), None)
            self.admin_ids = config.get("admin_controls", {}).get("admin_ids", [])
            self.reply_constraints = tg_cfg.get("reply_constraints", {})

            logging.info(f"Loaded config from {config_path}: window={self.window_seconds}s, tag_only={self.reply_only_on_tag}")
        except Exception as e:
            logging.error(f"Error loading config {config_path}: {e}")

    def load_policies(self):
        """Load and parse policy sections from a markdown file."""
        
        if not os.path.exists(self.policy_path):
            logging.warning(f"Policy file {self.policy_path} not found. Using defaults.")
            return

        try:
            with open(self.policy_path, "r") as f:
                content = f.read()
            
            sections = {}
            current_section = None
            current_text = []
            
            for line in content.split("\n"):
                if line.startswith("# "):
                    if current_section:
                        sections[current_section] = "\n".join(current_text).strip()
                    current_section = line[2:].strip().upper()
                    current_text = []
                elif current_section:
                    current_text.append(line)
            
            if current_section:
                sections[current_section] = "\n".join(current_text).strip()
            
            self.start_msg = sections.get("START", self.start_msg)
            self.about_msg = sections.get("ABOUT", self.about_msg)
            self.privacy_msg = sections.get("PRIVACY", self.privacy_msg)
            
            logging.info(f"Loaded policies from {self.policy_path}: sections={list(sections.keys())}")
        except Exception as e:
            logging.error(f"Error loading policies {self.policy_path}: {e}")

    def get_last_message(self):
        """Retrieve and consume the most recent processed window, thread-safe.
        Doubles as the outbox pump: the agent calls this once per loop from its
        own thread, which is where a blocking delivery is safe to run."""
        self._flush_outbox()
        with self.msg_lock:
            if self._message_queue:
                ready_chat_id, text, reply_id, payload = self._message_queue.pop(0)

                if not self._is_allowed_chat(ready_chat_id) and ready_chat_id not in self.admin_ids:
                        return None

                self.chat_id = ready_chat_id
                self._reply_to_id = reply_id
                context = None
                if isinstance(payload, dict):
                    media_handler.set_pending_media(payload.get("media"))
                    context = payload.get("context")
                    media_handler.set_pending_context(context)
                else:
                    media_handler.set_pending_media(payload)
                    media_handler.set_pending_context(None)
                self._start_typing(str(ready_chat_id))
                # PDF text / audio transcripts have no on-demand skill like
                # describe-image does, so they must ride along in the message
                # itself or the agent never sees them at all.
                if context:
                    text = f"{text}\n\n{context}"
                return f"[{ready_chat_id}] [{reply_id}] {text}"
            return None
    
    def _is_admin_dm(self, message: types.Message) -> bool:
        """Whether this is an admin's direct message. Admin commands are the most
        destructive thing the channel exposes, so they clear the same auth
        handshake as ordinary traffic when the host has it enabled — otherwise
        /kill and /purge would be the only paths that skip it."""
        if not (
            message.chat.type == "private"
            and message.from_user is not None
            and message.from_user.id in self.admin_ids
        ):
            return False
        return self._passes_auth_handshake(message)
    
    def _is_chat_authorized(self, message: types.Message, user_id_override: int = None) -> bool:
        """Check if the chat and user are authorized to interact with the bot.
        Two gates apply: this plugin's own chat/DM rules from
        telegram_profile.yaml, and — when the host enables it — core's channel
        auth handshake, which binds the bot to one verified user."""

        # Handle Dms
        if message.chat.type == "private":
            user_id = user_id_override if user_id_override is not None else getattr(message.from_user, "id", None)
            if user_id not in self.admin_ids and not self.dm_enabled:
                return False
            return self._passes_auth_handshake(message, user_id_override)

        # Handle Groups
        if not self._is_allowed_chat(message.chat.id):
            return False

        return self._passes_auth_handshake(message, user_id_override)

    def _display_name(self, message: types.Message) -> str:
        user = getattr(message, "from_user", None)
        if user is None:
            return "telegram_user"
        return f"@{user.username}" if user.username else (user.full_name or str(user.id))

    def _passes_auth_handshake(self, message: types.Message, user_id_override: int = None) -> bool:
        """Run core's channel auth handshake when it is enabled. Until a user
        sends `auth <token>` the bot ignores them; a successful binding is
        confirmed through the outbox, because this runs on the bot's event loop
        thread where a blocking send would deadlock."""
        if not auth.is_auth_enabled():
            return True

        user_id = user_id_override if user_id_override is not None else getattr(message.from_user, "id", None)
        if user_id is None:
            return False

        text = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()
        candidate = _parse_auth_candidate(text) if _is_auth_command(text) else None
        state = auth.authenticate_channel_user("TELEGRAM", str(user_id), candidate)
        if state == "auth_bound":
            self._outbox.put((message.chat.id, None,
                              f"Authentication successful for {self._display_name(message)}."))
            return True
        return state == "allow"
    
    async def _start_cmd(self, message: types.Message):
        """Handle the /start command with interactive buttons."""
        if not self._is_chat_authorized(message):
            return
        
        if not self._is_admin_dm(message):
            return await message.answer("❌ Admin commands only work in direct messages.")

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="ℹ️ About", callback_data="show_about")
        builder.button(text="🛡️ Privacy", callback_data="show_privacy")

        if message.from_user and message.from_user.id in self.admin_ids:
            builder.button(text="⚙️ Admin Panel", callback_data="admin_panel")
        
        await message.answer(self.start_msg, reply_markup=builder.as_markup())

    async def _about_cmd(self, message: types.Message):
        """Handle /about command."""
        if not self._is_chat_authorized(message):
            return

        await message.answer(self.about_msg)

    async def _privacy_cmd(self, message: types.Message):
        """Handle /privacy command."""
        if not self._is_chat_authorized(message):
            return

        await message.answer(self.privacy_msg)

    async def _kill_cmd(self, message: types.Message):
        """Handle global kill switch (admin only)."""
        if not self._is_admin_dm(message):
            return await message.answer("❌ Admin commands only work in direct messages.")

        await message.answer("⚠️ Global Kill Switch activated. Shutting down...")
        logging.critical(f"KILLED by admin {message.from_user.id}")
        self.stop()
        os._exit(0)
    
    async def _pause_cmd(self, message: types.Message):
        """Handle /pause command (admin only)."""
        if not self._is_chat_authorized(message):
            return
        
        if not self._is_admin_dm(message):
             return await message.answer("❌ Admin commands only work in direct messages.")
        
        target_chat = self.allowed_chat_id or getattr(message.chat, "id", None)
        args = message.text.split()
        if len(args) > 1:
            target_chat = args[1]

        target_chat = self._normalize_chat_id(target_chat)
        if target_chat is None:
            return await message.answer("❌ Could not work out which chat to pause.")

        if target_chat in self._paused_chats:
            self._paused_chats.remove(target_chat)
            await message.answer(f"▶️ Chat {target_chat} unpaused.")
        else:
            self._paused_chats.add(target_chat)
            await message.answer(f"⏸️ Chat {target_chat} paused.")

    async def _togglesearch_cmd(self, message: types.Message):
        """Handle /togglesearch command (admin only)."""
        if not self._is_admin_dm(message):
            return await message.answer("❌ Admin commands only work in direct messages.")

        self.search_disabled = not self.search_disabled
        state = "DISABLED" if self.search_disabled else "ENABLED"
        await message.answer(f"🔍 Web search is now {state}.")
    
    async def _purge_cmd(self, message: types.Message):
        """Handle /purge command (admin only)."""
        if not self._is_admin_dm(message):
            return await message.answer("❌ Admin commands only work in direct messages.")

        try:
            _purge_long_term_memory()
            await message.answer("🗑️ Long-term memory purged successfully.")
        except Exception as e:
            await message.answer(f"❌ Failed to purge memory: {e}")


    async def _on_callback_query(self, callback: types.CallbackQuery):
        """Handle button clicks."""
        if not self._is_chat_authorized(callback.message, user_id_override=callback.from_user.id):
            await callback.answer("❌ This chat is not authorized.", show_alert=True)
            return
        
        if callback.data == "show_about":
            await callback.message.answer(self.about_msg)
        elif callback.data == "show_privacy":
            await callback.message.answer(self.privacy_msg)
        elif callback.data == "admin_panel":
            if callback.from_user.id in self.admin_ids:
                cmd_list = (
                    "🛠 **Admin Commands:**\n"
                    "/pause [chat_id] - Pause/unpause a chat\n"
                    "/togglesearch - Enable/Disable Web Search\n"
                    "/purge - Wipe ChromaDB Memory\n"
                    "/kill - Shutdown Bot globally"
                )
                await callback.message.answer(cmd_list)
            else:
                await callback.message.answer("❌ Access denied.")
        await callback.answer()
    
    async def _send_block_notice(self, message: types.Message, text: str):
        try:
            await message.answer(text, reply_to_message_id=message.message_id)
        except Exception as e:
            logging.error(f"Failed to send block notice: {e}")

    async def _on_message(self, message: types.Message):
        """Capture group messages into the buffer; flag reply if bot is tagged."""
        if message.text is None:
            return
        
        if self._is_paused(message.chat.id):
            return

        if not self._is_chat_authorized(message):
            return
        
        # Filter out messages from other bots and muted users
        if message.from_user:
            if message.chat.type in ["group", "supergroup"]:
                if message.from_user.is_bot and not self.allow_group_bots:
                    return
            
            if await self.is_user_muted(message.from_user):
                return
        
        has_media = bool(message.photo or message.video or message.audio or message.voice)
        if has_media and not self.reply_constraints.get("allow_media", False):
            await self._send_block_notice(message, "Media messages are not supported here. Please send text instead.")
            return

        has_files = bool(message.document)
        if has_files and not self.reply_constraints.get("allow_files", False):
            await self._send_block_notice(message, "File uploads are not supported here. Please send text instead.")
            return
        
        if message.chat is not None:
            chat_id = message.chat.id
            
        user = message.from_user
        name = "unknown user" if user is None else (user.username or user.full_name or str(user.id))
        name = f"@{name}" if name == user.username else name
        text = message.text

        if await is_category_blocked(text):
            logging.warning(f"Ethics/Security pass rejected incoming message from {name}: {text}")
            message = "From: " + user.username + ": " + text if user and user.username else text
            alert_ethics_violation("incoming_message", message)
            return

        is_private = message.chat.type == "private"
        if not is_private:
            is_tagged = self.bot_username and f"@{self.bot_username}" in text
            is_reply = (
                self.reply_on_reply and
                message.reply_to_message and
                message.reply_to_message.from_user and
                message.reply_to_message.from_user.id == self.bot_id
            )

            if self.reply_only_on_tag and not (is_tagged or is_reply):
                return
        
        with self.msg_lock:
            self._message_queue.append((chat_id, f"{name}: {text}", message.message_id, None))
            

    async def is_user_muted(self, user: types.User):
        """Feature: User mute / cool-down after repeated abuse."""
        spam_config = get_spam_protection_config()
        time_window = spam_config["time_window"]
        message_limit = spam_config["message_limit"]
        cooldown_duration = spam_config["cooldown_duration"]
        admin_alert_threshold = spam_config["admin_alert_threshold"]
        user_id = user.id

        if user_id in self._muted_users:
            if time.time() < self._muted_users[user_id]:
                return True
            else:
                del self._muted_users[user_id]
                
        now = time.time()
        history = self._user_msg_rates.get(user_id, [])
        history = [ts for ts in history if now - ts < time_window]
        history.append(now)
        self._user_msg_rates[user_id] = history
        
        if len(history) > message_limit:
            mute_count = self._user_mute_counts.get(user_id, 0) + 1
            self._user_mute_counts[user_id] = mute_count

            username = user.username or user.full_name or str(user_id)
            logging.warning(f"User with id: {user_id} | username: {username} muted for spamming.")
            self._muted_users[user_id] = now + cooldown_duration
            
            if mute_count >= admin_alert_threshold:
                for admin_id in self.admin_ids:
                    try:
                        alert_msg = (f"🚨 **Spam Alert** 🚨\n"
                                        f"User @{username} (ID: {user_id}) has been temporarily muted for spamming.\n"
                                        f"Total times muted: {mute_count}")
                        await self.bot.send_message(chat_id=admin_id, text=alert_msg)
                    except Exception as e:
                        logging.error(f"Failed to notify admin {admin_id}: {e}")
                        
            return True
            
        return False

    def _should_bot_respond(self, message: types.Message, text: str) -> bool:
        """Return True if the bot should respond to this message."""
        if message.chat.type == "private":
            return True
        is_tagged = self.bot_username and f"@{self.bot_username}" in (text or "")
        is_reply = (
            self.reply_on_reply and
            message.reply_to_message and
            message.reply_to_message.from_user and
            message.reply_to_message.from_user.id == self.bot_id
        )
        return bool(is_tagged or is_reply)

    async def _on_photo(self, message: types.Message):
        """Handle photo messages."""
        if self._is_paused(message.chat.id):
            return
        if not self._is_chat_authorized(message):
            return
        if message.from_user:
            if message.chat.type in ["group", "supergroup"]:
                if message.from_user.is_bot and not self.allow_group_bots:
                    return
            if await self.is_user_muted(message.from_user):
                return

        if not self.reply_constraints.get("allow_media", False):
            caption = message.caption or ""
            if self._should_bot_respond(message, caption):
                await self._send_block_notice(message, "Image uploads are not enabled. Please send text instead.")
            return

        caption = message.caption or ""
        if not self._should_bot_respond(message, caption):
            return

        if caption and await is_category_blocked(caption):
            logging.warning(f"Ethics pass rejected photo caption")
            sender = message.from_user.username if message.from_user and message.from_user.username else "unknown"
            alert_ethics_violation("incoming_message", f"From: {sender}: [photo caption] {caption}")
            return

        user = message.from_user
        name = "unknown user" if user is None else (user.username or user.full_name or str(user.id))
        name = f"@{name}" if user and name == user.username else name
        chat_id = message.chat.id

        try:
            buf = BytesIO()
            await self.bot.download(message.photo[-1], destination=buf)
            image_bytes = media_handler.sanitize_image(buf.getvalue())
            data_uri = media_handler.image_to_data_uri(image_bytes, "image/jpeg")
            pending_media = [{"type": "image_url", "image_url": {"url": data_uri}}]
        except Exception as e:
            logging.error(f"Failed to download photo: {e}")
            await self._send_block_notice(message, "Failed to process the image. Please try again.")
            return

        display_text = f"{name}: {caption}" if caption else f"{name}: [image]"
        with self.msg_lock:
            self._message_queue.append((chat_id, display_text, message.message_id, pending_media))
        logging.info("[IMGDBG] queued photo from %s chat=%s bytes=%d caption=%s", name, chat_id, len(image_bytes), bool(caption))

    async def _on_document(self, message: types.Message):
        """Handle document (file) messages — PDF only."""
        if self._is_paused(message.chat.id):
            return
        if not self._is_chat_authorized(message):
            return
        if message.from_user:
            if message.chat.type in ["group", "supergroup"]:
                if message.from_user.is_bot and not self.allow_group_bots:
                    return
            if await self.is_user_muted(message.from_user):
                return

        caption = message.caption or ""

        if not self.reply_constraints.get("allow_files", False):
            if self._should_bot_respond(message, caption):
                await self._send_block_notice(message, "File uploads are not enabled. Please send text instead.")
            return

        if not self._should_bot_respond(message, caption):
            return

        mime = message.document.mime_type or ""
        if mime != "application/pdf":
            await self._send_block_notice(message, "Only PDF files are supported. Please send a PDF.")
            return

        if caption and await is_category_blocked(caption):
            logging.warning(f"Ethics pass rejected document caption")
            sender = message.from_user.username if message.from_user and message.from_user.username else "unknown"
            alert_ethics_violation("incoming_message", f"From: {sender}: [document caption] {caption}")
            return

        user = message.from_user
        name = "unknown user" if user is None else (user.username or user.full_name or str(user.id))
        name = f"@{name}" if user and name == user.username else name
        chat_id = message.chat.id
        filename = message.document.file_name or "document.pdf"

        try:
            buf = BytesIO()
            await self.bot.download(message.document, destination=buf)
            pdf_text = media_handler.extract_pdf_text(buf.getvalue(), filename)
        except Exception as e:
            logging.error(f"Failed to download/extract PDF: {e}")
            await self._send_block_notice(message, "Failed to process the PDF. Please try again.")
            return

        if await is_category_blocked(pdf_text):
            logging.warning(f"Ethics pass rejected PDF content from '{filename}'")
            sender = user.username if user and user.username else "unknown"
            alert_ethics_violation("incoming_message", f"From: {sender}: [PDF content blocked] {filename}")
            return

        user_request = f" — {caption}" if caption else " — please summarize this PDF"
        display_text = f"{name}: [uploaded PDF '{filename}']{user_request}"
        with self.msg_lock:
            self._message_queue.append((chat_id, display_text, message.message_id, {"media": None, "context": pdf_text}))

    async def _on_audio(self, message: types.Message):
        """Handle voice notes and audio files — transcribe to text via Whisper."""
        if self._is_paused(message.chat.id):
            return
        if not self._is_chat_authorized(message):
            return
        if message.from_user:
            if message.chat.type in ["group", "supergroup"]:
                if message.from_user.is_bot and not self.allow_group_bots:
                    return
            if await self.is_user_muted(message.from_user):
                return

        caption = message.caption or ""

        if not self.reply_constraints.get("allow_audio", False):
            if self._should_bot_respond(message, caption):
                await self._send_block_notice(message, "Audio messages are not enabled. Please send text instead.")
            return

        if not self._should_bot_respond(message, caption):
            return

        if caption and await is_category_blocked(caption):
            logging.warning(f"Ethics pass rejected audio caption")
            sender = message.from_user.username if message.from_user and message.from_user.username else "unknown"
            alert_ethics_violation("incoming_message", f"From: {sender}: [audio caption] {caption}")
            return

        user = message.from_user
        name = "unknown user" if user is None else (user.username or user.full_name or str(user.id))
        name = f"@{name}" if user and name == user.username else name
        chat_id = message.chat.id
        media = message.voice or message.audio
        filename = getattr(media, "file_name", None) or ("voice.ogg" if message.voice else "audio")

        try:
            buf = BytesIO()
            await self.bot.download(media, destination=buf)
            transcript = await asyncio.to_thread(media_handler.transcribe_audio, buf.getvalue(), filename)
        except Exception as e:
            logging.error(f"Failed to download/transcribe audio: {e}")
            await self._send_block_notice(message, "Failed to process the audio. Please try again.")
            return

        if await is_category_blocked(transcript):
            logging.warning(f"Ethics pass rejected audio transcript from '{filename}'")
            sender = user.username if user and user.username else "unknown"
            alert_ethics_violation("incoming_message", f"From: {sender}: [audio transcript blocked] {filename}")
            return

        user_request = f" — {caption}" if caption else " — please respond to this voice message"
        display_text = f"{name}: [sent audio '{filename}']{user_request}"
        with self.msg_lock:
            self._message_queue.append((chat_id, display_text, message.message_id, {"media": None, "context": transcript}))

    async def _on_media_rejected(self, message: types.Message):
        if self._is_paused(message.chat.id):
            return

        if not self._is_chat_authorized(message):
            return

        caption = message.caption or ""
        if self._should_bot_respond(message, caption):
            logging.info("Denied capability invoked: unsupported media type uploaded.")
            await self._send_block_notice(
                message,
                "I can process text, images, PDF files, and voice/audio messages. Video and other file types are not supported."
            )

    async def _load_chat_admins(self, chat_ids):
        """Add each chat's administrators to the admin list."""
        for eval_chat_id in dict.fromkeys(chat_ids):
            try:
                admins = await self.bot.get_chat_administrators(eval_chat_id)
                for admin in admins:
                    if admin.user.id not in self.admin_ids:
                        self.admin_ids.append(int(admin.user.id))
                logging.info(f"Loaded admins from group {eval_chat_id}. Total admins: {len(self.admin_ids)}")
            except Exception as e:
                # A one-to-one chat has no administrators to load, and Telegram
                # reports asking for them as a bad request. Expected, not a
                # fault: logging it as an error made a healthy start look broken.
                if "no administrators in the private chat" in str(e):
                    logging.info(f"Chat {eval_chat_id} is a private chat; no admins to load.")
                else:
                    logging.error(f"Failed to fetch administrators for chat {eval_chat_id}: {e}")

    async def _runner(self, token):
        """Build the aiogram bot, start polling, and run until stopped."""
        self.bot = _build_bot(token)
        self.dp = Dispatcher()
        
        try:
            # Get bot info for tag detection
            bot_info = await self.bot.get_me()
            self.bot_username = bot_info.username
            self.bot_id = bot_info.id

            chat_ids_for_admin_scan = list(self.allowed_chat_ids)
            if self.chat_id:
                normalized_chat_id = self._normalize_chat_id(self.chat_id)
                if normalized_chat_id:
                    chat_ids_for_admin_scan.append(normalized_chat_id)

            await self._load_chat_admins(chat_ids_for_admin_scan)
            
            self.dp.message.register(self._start_cmd, Command("start"))
            self.dp.message.register(self._about_cmd, Command("about"))
            self.dp.message.register(self._privacy_cmd, Command("privacy"))
            self.dp.message.register(self._kill_cmd, Command("kill"))
            self.dp.message.register(self._pause_cmd, Command("pause"))
            self.dp.message.register(self._togglesearch_cmd, Command("togglesearch"))
            self.dp.message.register(self._purge_cmd, Command("purge"))
            self.dp.callback_query.register(self._on_callback_query)
            self.dp.message.register(self._on_document, F.document)
            self.dp.message.register(self._on_photo, F.photo)
            self.dp.message.register(self._on_audio, F.voice | F.audio)
            self.dp.message.register(self._on_message, F.text)
            self.dp.message.register(self._on_media_rejected, ~F.text & ~F.photo & ~F.document & ~F.voice & ~F.audio)

            self.connected = True
            self._polling_task = asyncio.create_task(self.dp.start_polling(self.bot, skip_updates=True, handle_signals=False))
            await self._polling_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Telegram runner error: {e}")
        finally:
            self.connected = False
            await self.bot.session.close()

    def _thread_main(self, token):
        """Create a dedicated asyncio event loop and run the bot in it."""
        loop = asyncio.new_event_loop()
        self.loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._runner(token))
        except Exception as e:
            logging.error(f"Telegram runner error in thread: {e}")
        finally:
            loop.close()
        self.loop = None

    def start(self, token, chat_id=None, config_path=None):
        """Launch the Telegram bot on a daemon thread and begin polling."""
        self.running = True
        # Reload config if path provided
        if config_path is None:
            self.load_config(self.config_path)

        runtime_chat_ids = self._normalize_chat_ids(chat_id)
        if runtime_chat_ids:
            self.allowed_chat_ids.update(runtime_chat_ids)
            self.allowed_chat_id = next(iter(self.allowed_chat_ids), None)
            self.chat_id = next(iter(runtime_chat_ids))
        else:
            self.chat_id = self.allowed_chat_id
            
        self.thread = threading.Thread(target=self._thread_main, args=(token,), daemon=True)
        self.thread.start()
        return self.thread

    def stop(self):
        """Signal the polling loop to stop gracefully."""
        self.running = False
        if self.loop and self._polling_task:
            self.loop.call_soon_threadsafe(self._polling_task.cancel)

    def _start_typing(self, chat_id):
        """Start typing indicator for a chat.

        Sends typing action every 4s until one of three things happens:
        - send_message() is called  -> _stop_typing() sets the stop event
        - a new message is dequeued -> _start_typing() replaces this one
        - hard timeout is reached   -> typing_loop exits on its own
        """
        self._stop_typing(chat_id)
        stop_event = threading.Event()
        deadline = time.time() + self._TYPING_TIMEOUT
        self._typing_threads[chat_id] = stop_event

        def typing_loop():
            while not stop_event.is_set() and time.time() < deadline:
                if self.connected and self.bot and self.loop:
                    asyncio.run_coroutine_threadsafe(
                        self.bot.send_chat_action(chat_id=chat_id, action="typing"),
                        self.loop
                    )
                stop_event.wait(4)
            self._typing_threads.pop(chat_id, None)

        threading.Thread(target=typing_loop, daemon=True).start()

    def _stop_typing(self, chat_id):
        """Stop the typing indicator for a given chat."""
        stop_event = self._typing_threads.pop(chat_id, None)
        if stop_event:
            stop_event.set()

    def _to_mdv2(self, text):
        return markdownify(text)

    def send_message(self, text, chat_id=None, reply_to_id=None):
        """Queue a text message for the target chat, then deliver whatever the
        bot is ready to take. Never call this from the bot's own event loop
        thread: delivery blocks on the coroutine's result."""
        text = text.replace("\\n", "\n")

        target_chat_id = chat_id or self.chat_id
        self._stop_typing(str(target_chat_id))
        target_reply_id = reply_to_id or (self._reply_to_id if target_chat_id == self.chat_id else None)

        self._outbox.put((target_chat_id, target_reply_id, text))
        self._flush_outbox()

    def _ready_to_send(self):
        return bool(self.connected and self.bot is not None and self.loop is not None)

    def _flush_outbox(self):
        """Drain the outbox. A message that cannot be delivered stays queued and
        is retried on the next flush rather than being lost."""
        try:
            self._outbox.flush(self._deliver, self._ready_to_send)
        except Exception as e:
            logging.warning(f"Telegram send failed, message stays queued: {e}")

    def _deliver(self, item):
        """Send one queued message. Raises on failure so the outbox keeps it."""
        target_chat_id, target_reply_id, text = item
        if target_chat_id is None:
            target_chat_id = self.chat_id
        if target_chat_id is None:
            raise RuntimeError("Telegram chat is not bound yet")

        fut = asyncio.run_coroutine_threadsafe(
            self.bot.send_message(chat_id=target_chat_id,
                                  text=self._to_mdv2(text),
                                  reply_to_message_id=target_reply_id,
                                  parse_mode="MarkdownV2"),
            self.loop,
        )
        try:
            fut.result(timeout=10)
            return
        except Exception as e:
            logging.error(f"Telegram formatting error, falling back to plain text: {e}")

        fut_fallback = asyncio.run_coroutine_threadsafe(
            self.bot.send_message(chat_id=target_chat_id,
                                  text=text,
                                  reply_to_message_id=target_reply_id),
            self.loop,
        )
        fut_fallback.result(timeout=10)

    def send_photo(self, image_bytes, caption=None, chat_id=None, reply_to_id=None):
        """Send a photo to the active chat, dispatched to the bot's event loop.
        Mirrors send_message's threading/targeting. Caption is sent plain (no
        MarkdownV2) to avoid escaping failures."""
        target_chat_id = chat_id or self.chat_id
        self._stop_typing(str(target_chat_id))
        target_reply_id = reply_to_id or (self._reply_to_id if target_chat_id == self.chat_id else None)
        logging.info(f"send_photo: chat_id={target_chat_id} reply_to={target_reply_id} "
                     f"connected={self.connected} bot={self.bot is not None} loop={self.loop is not None} "
                     f"bytes={len(image_bytes)}")

        if not self.connected or self.bot is None or self.loop is None or target_chat_id is None:
            raise RuntimeError(
                f"send_photo preconditions not met (connected={self.connected}, "
                f"bot={self.bot is not None}, loop={self.loop is not None}, chat_id={target_chat_id})")

        photo = BufferedInputFile(image_bytes, filename="image.png")
        fut = asyncio.run_coroutine_threadsafe(
            self.bot.send_photo(chat_id=target_chat_id,
                                photo=photo,
                                caption=caption,
                                reply_to_message_id=target_reply_id),
            self.loop,
        )
        try:
            fut.result(timeout=30)
            logging.info(f"send_photo: delivered to {target_chat_id}")
        except Exception as e:
            logging.error(f"Failed to send photo (retrying without caption/reply): {e}")
            fut_fallback = asyncio.run_coroutine_threadsafe(
                self.bot.send_photo(chat_id=target_chat_id,
                                    photo=BufferedInputFile(image_bytes, filename="image.png")),
                self.loop,
            )
            try:
                fut_fallback.result(timeout=30)
                logging.info(f"send_photo: delivered to {target_chat_id} (fallback, no caption)")
            except Exception as e2:
                logging.error(f"Failed to send photo: {e2}")
                raise

_channel = _TelegramChannel()

def _purge_long_term_memory():
    """Drop and recreate the agent's long-term memory collection.

    Goes through core's rag module rather than opening Chroma directly. rag owns
    where the database lives — CHROMA_DB_PATH overrides it — so a hardcoded
    relative path purges a different directory and still reports success. rag
    also caches its collection handle, so the cache is dropped here; purging
    behind its back leaves the agent querying a deleted collection until restart.
    """
    import rag

    rag._get_collection()
    rag._client.delete_collection(rag.COLLECTION_NAME)
    rag._collection = None
    rag._get_collection()
    logging.info(f"Purged long-term memory collection at {rag.DB_PATH}")


def _is_auth_command(msg):
    lower = msg.strip().lower()
    return lower.startswith("auth ") or lower.startswith("/auth ")


def _parse_auth_candidate(msg):
    text = msg.strip()
    lower = text.lower()
    if lower.startswith("auth "):
        return text[5:].strip()
    if lower.startswith("/auth "):
        return text[6:].strip()
    return text


# aiogram refuses a token that is not <digits>:<rest>, so the placeholder used
# when the real token lives in the gateway proxy still has to look like one.
_PROXY_TOKEN = "0:proxy"


def _build_bot(token):
    """Build the aiogram Bot. When a gateway proxy is configured the bot talks
    to the proxy instead of api.telegram.org, so the real bot token never enters
    this process — the proxy injects it. File downloads need their own route
    because Telegram serves files from /file/bot<token>/<path>, not /bot<token>/."""
    proxy = auth.get_proxy_url()
    if not proxy:
        return Bot(token=token)
    api = TelegramAPIServer(base=f"{proxy}/telegram/{{method}}",
                            file=f"{proxy}/telegram-file/{{path}}")
    logging.info(f"Telegram: routing API calls through proxy {proxy}/telegram/")
    return Bot(token=token, session=AiohttpSession(api=api))


def getLastMessage():
    """Return the last processed batch window."""        
    return _channel.get_last_message()

def start_telegram(token, chat_id=None):
    """Initialize and start the Telegram bot."""
    if isinstance(token, list) and len(token) > 0:
        token = str(token[0])
    
    token = str(token).strip("\"' ")
    
    if isinstance(chat_id, list):
        chat_id = [str(item).strip("\"' ") for item in chat_id if str(item).strip("\"' ")]
    elif chat_id is not None:
        chat_id = str(chat_id).strip("\"' ")
            
    return _channel.start(token, chat_id)

def stop_telegram():
    """Stop the Telegram bot."""
    _channel.stop()

def send_message(text):
    """Send a message to the active Telegram chat."""
    target_chat_id = _channel.chat_id
    target_reply_id = None
    text = text.strip().strip('“”‘’"\'').strip()
    m = re.match(r'^\[(-?\d+)\]\s*(?:\[(\d+)\])?\s*(.*)$', text, re.DOTALL)
    if m:
        target_chat_id = m.group(1)
        if m.group(2) and m.group(2) != "None":
            target_reply_id = int(m.group(2))

        text = m.group(3)

    # Run the async check safely in a synchronous context
    try:
        loop = asyncio.get_running_loop()
        is_blocked = loop.run_until_complete(is_category_blocked(text))
    except RuntimeError:
        is_blocked = asyncio.run(is_category_blocked(text))

    if is_blocked:
        alert_ethics_violation("send", text)
        return "Error: Refused: Unsafe response content."
        
    _channel.send_message(text, chat_id=target_chat_id, reply_to_id=target_reply_id)
    # The agent has replied to the user, so drop any attached PDF/image context.
    # This bounds the out-of-band slot to "arrival → first reply" and stops the
    # 20k-char PDF (or large base64 image) being re-injected on idle-tail cycles.
    media_handler.clear_pending()

def send_photo(image_bytes, caption=None):
    """Send a generated photo to the active Telegram chat (called from
    media_handler.generate_and_send). Targets the current chat / reply message;
    does not touch the inbound pending slots."""
    _channel.send_photo(image_bytes, caption=caption,
                        chat_id=_channel.chat_id,
                        reply_to_id=getattr(_channel, "_reply_to_id", None))

def is_search_disabled():
    """Check if admin disabled searching."""
    return _channel.search_disabled

def alert_ethics_violation(tool_name, text=None):
    """Allow MeTTa to trigger an ethics alert DM to admins.

    An alert that quietly fails is worse than none, because silence reads as "no
    blocks happened". Delivery runs on the bot's loop, so the outcome arrives in
    a callback rather than as a raised exception, and a channel with no admins
    configured says so instead of dropping the alert without a trace.
    """
    if not (_channel.loop and _channel.bot):
        logging.error(f"Ethics alert for {tool_name} not sent: the bot is not running")
        return

    if not _channel.admin_ids:
        logging.error(f"Ethics alert for {tool_name} not sent: no admin_ids are configured")
        return

    for admin_id in _channel.admin_ids:
        def _log_outcome(fut, admin_id=admin_id):
            exc = fut.exception()
            if exc is not None:
                logging.error(f"Failed to send ethics alert to admin {admin_id} for tool {tool_name}: {exc}")

        try:
            fut = asyncio.run_coroutine_threadsafe(
                _channel.bot.send_message(chat_id=admin_id, text=f"🚨 Ethics Pass Triggered!\nAction Blocked: {tool_name} | With message: {text}"),
                _channel.loop
            )
            fut.add_done_callback(_log_outcome)
        except Exception as e:
            logging.error(f"Failed to schedule ethics alert to admin {admin_id} for tool {tool_name}: {e}")


class TelegramChannel(channels.CommChannel):
    """CommChannel wrapper around the aiogram-based _TelegramChannel above.
    start() launches the bot on its own thread and event loop and returns
    immediately; receive() and send() proxy to the already-thread-safe module
    functions."""

    def start(self) -> None:
        chat_id = config_get_by_key("TG_CHAT_ID", "")
        if auth.get_proxy_url():
            token = _PROXY_TOKEN
        else:
            token = os.environ.get("TG_BOT_TOKEN", "").strip()
            if not token:
                raise ValueError("TG_BOT_TOKEN is required")
        start_telegram(token, chat_id)

    def stop(self) -> None:
        stop_telegram()

    def receive(self) -> str:
        return getLastMessage()

    def send(self, message: str) -> None:
        send_message(message)


def loadOmegaClawPlugin():
    import media_handler
    # Hand media_handler this module's live channel so generate-image can send
    # the images it produces; it cannot find them by importing us by name.
    media_handler.register_channel(send_photo, _channel)
    channels.registerCommChannel("telegram", TelegramChannel())
