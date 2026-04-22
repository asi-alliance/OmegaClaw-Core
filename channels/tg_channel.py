import asyncio
import time
import threading
import logging
import yaml
import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from src.config_helper import is_category_blocked, get_spam_protection_config


log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "telegram.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)

class _TelegramChannel:
    """Telegram bot channel with windowed batching and bot-tag gating using aiogram."""

    def __init__(self, config_path=None):
        self.config_path = os.path.join(os.path.dirname(__file__),  "..", "memory", "telegram_profile.yaml")
        self.policy_path= os.path.join(os.path.dirname(__file__), "..", "memory", "policy.md")
        self.running = False
        self.thread = None
        self.loop = None
        self.bot = None
        self.dp = None
        self.connected = False
        self.chat_id = None
        self.allowed_chat_id = None
        
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
        self._paused_chats = set()
        self.search_disabled = False
        self._ready_windows = []
        self._polling_task = None

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
        """Retrieve and consume the most recent processed window, thread-safe."""
        with self.msg_lock:
            if self._message_queue:
                ready_chat_id, text, reply_id = self._message_queue.pop(0)
                self.chat_id = ready_chat_id
                self._reply_to_id = reply_id
                return text
            return None
    
    async def _start_cmd(self, message: types.Message):
        """Handle the /start command with interactive buttons."""
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="ℹ️ About", callback_data="show_about")
        builder.button(text="🛡️ Privacy", callback_data="show_privacy")

        if message.from_user and message.from_user.id in self.admin_ids:
            builder.button(text="⚙️ Admin Panel", callback_data="admin_panel")
        
        await message.answer(self.start_msg, reply_markup=builder.as_markup())

    async def _about_cmd(self, message: types.Message):
        """Handle /about command."""
        await message.answer(self.about_msg)

    async def _privacy_cmd(self, message: types.Message):
        """Handle /privacy command."""
        await message.answer(self.privacy_msg)

    async def _kill_cmd(self, message: types.Message):
        """Handle global kill switch (admin only)."""
        user_id = message.from_user.id if message.from_user else None
        if user_id in self.admin_ids:
            await message.answer("⚠️ Global Kill Switch activated. Shutting down...")
            logging.critical(f"KILLED by admin {user_id}")
            self.stop()
            os._exit(0)
        else:
            await message.answer("❌ Access denied. Admin only.")
    
    async def _pause_cmd(self, message: types.Message):
        """Handle /pause command (admin only)."""
        if message.from_user.id not in self.admin_ids:
            return await message.answer("❌ Access denied.")
        
        target_chat = message.chat.id
        args = message.text.split()
        if len(args) > 1:
            target_chat = args[1]
            
        if target_chat in self._paused_chats:
            self._paused_chats.remove(target_chat)
            await message.answer(f"▶️ Chat {target_chat} unpaused.")
        else:
            self._paused_chats.add(target_chat)
            await message.answer(f"⏸️ Chat {target_chat} paused.")

    async def _togglesearch_cmd(self, message: types.Message):
        """Handle /togglesearch command (admin only)."""
        if message.from_user.id not in self.admin_ids:
            return await message.answer("❌ Access denied.")
        
        self.search_disabled = not self.search_disabled
        state = "DISABLED" if self.search_disabled else "ENABLED"
        await message.answer(f"🔍 Web search is now {state}.")

    
    async def _purge_cmd(self, message: types.Message):
        """Handle /purge command (admin only)."""
        if message.from_user.id not in self.admin_ids:
            return await message.answer("❌ Access denied.")
        
        try:
            import chromadb
            client = chromadb.PersistentClient(path="./chroma_db")
            client.delete_collection("memories")
            client.get_or_create_collection(name="memories")
            await message.answer("🗑️ Long-term memory purged successfully.")
        except Exception as e:
            await message.answer(f"❌ Failed to purge memory: {e}")


    async def _on_callback_query(self, callback: types.CallbackQuery):
        """Handle button clicks."""
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

    async def _on_message(self, message: types.Message):
        """Capture group messages into the buffer; flag reply if bot is tagged."""
        if message.text is None:
            return
        
        if message.chat.id in self._paused_chats:
            return

        # Check DM support
        if message.chat.type == "private":
            if getattr(message.from_user, "id", None) not in self.admin_ids and not self.dm_enabled:
                return
        # Check for multiple chat support and config restriction
        else:
            if self.restrict_to_config_chat:
                if hasattr(self, 'allowed_chat_id') and self.allowed_chat_id:
                    if str(message.chat.id) != str(self.allowed_chat_id):
                        return
        
        # Filter out messages from other bots and muted users
        if message.from_user:
            if message.chat.type not in ["group", "supergroup"] or not self.allow_group_bots:
                    return
            if await self.is_user_muted(message.from_user):
                return
        
        has_media = bool(message.photo or message.video or message.audio or message.voice)
        if has_media and not self.reply_constraints.get("allow_media", False):
            return
            
        has_files = bool(message.document)
        if has_files and not self.reply_constraints.get("allow_files", False):
            return

        if message.chat is not None:
            chat_id = message.chat.id
            
        user = message.from_user
        name = "unknown user" if user is None else (user.full_name or user.username or str(user.id))
        text = message.text

        if await is_category_blocked(text):
            logging.warning(f"Ethics/Security pass rejected incoming message from {name}: {text}")
            message = "From: " + user.username + ": " + text if user and user.username else text
            alert_ethics_violation("incoming_message", message)
            return

        is_tagged = self.bot_username and f"@{self.bot_username}" in text
        is_reply = (self.reply_on_reply and 
                    message.reply_to_message and 
                    message.reply_to_message.from_user and 
                    message.reply_to_message.from_user.id == self.bot_id)
        
        if self.reply_only_on_tag and not (is_tagged or is_reply):
            return
        
        with self.msg_lock:
            self._message_queue.append((chat_id, f"{name}: {text}", message.message_id))
            

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

    async def _on_media_rejected(self, message: types.Message):
        """Feature: Block files, images, audio, voice notes."""
        logging.info("Denied capability invoked: Media/File uploaded. Discarding.")
        # Silently discard to prevent abuse surface / leakage
        pass

    async def _runner(self, token):
        """Build the aiogram bot, start polling, and run until stopped."""
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        
        try:
            # Get bot info for tag detection
            bot_info = await self.bot.get_me()
            self.bot_username = bot_info.username
            self.bot_id = bot_info.id

            if self.chat_id:
                try:
                    eval_chat_id = str(self.chat_id)
                    if not eval_chat_id.startswith('-') and len(eval_chat_id) > 10:
                        eval_chat_id = f"-{eval_chat_id}"
                    admins = await self.bot.get_chat_administrators(eval_chat_id)
                    for admin in admins:
                        if admin.user.id not in self.admin_ids:
                            self.admin_ids.append(int(admin.user.id))
                    logging.info(f"Loaded admins from group {self.chat_id}. Total admins: {len(self.admin_ids)}")
                except Exception as e:
                    logging.error(f"Failed to fetch administrators for chat {self.chat_id}: {e}")
            
            self.dp.message.register(self._start_cmd, Command("start"))
            self.dp.message.register(self._about_cmd, Command("about"))
            self.dp.message.register(self._privacy_cmd, Command("privacy"))
            self.dp.message.register(self._kill_cmd, Command("kill"))
            self.dp.message.register(self._pause_cmd, Command("pause"))
            self.dp.message.register(self._togglesearch_cmd, Command("togglesearch"))
            self.dp.message.register(self._purge_cmd, Command("purge"))
            self.dp.callback_query.register(self._on_callback_query)
            self.dp.message.register(self._on_message, F.text)
            self.dp.message.register(self._on_media_rejected, ~F.text)

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
        self.chat_id = chat_id
        self.allowed_chat_id = chat_id
        # Reload config if path provided
        if config_path is None:
            self.load_config(self.config_path)
            
        self.thread = threading.Thread(target=self._thread_main, args=(token,), daemon=True)
        self.thread.start()
        return self.thread

    def stop(self):
        """Signal the polling loop to stop gracefully."""
        self.running = False
        if self.loop and self._polling_task:
            self.loop.call_soon_threadsafe(self._polling_task.cancel)

    def send_message(self, text):
        """Send a text message to the active chat, dispatched to the bot's event loop."""
        text = text.replace("\\n", "\n")
        if not self.connected or self.bot is None or self.loop is None or self.chat_id is None:
            return
        
        fut = asyncio.run_coroutine_threadsafe(
            self.bot.send_message(chat_id=self.chat_id,
                                  text=text,
                                  reply_to_message_id=self._reply_to_id,
                                  parse_mode="MarkdownV2"),
            self.loop,
        )
        try:
            fut.result(timeout=10)
        except Exception as e:
            logging.error(f"Telegram formatting error, falling back to plain text: {e}")
            fut_fallback = asyncio.run_coroutine_threadsafe(
                self.bot.send_message(
                    chat_id=self.chat_id, 
                    text=text, 
                    reply_to_message_id=self._reply_to_id
                ),
                self.loop,
            )
            try:
                fut_fallback.result(timeout=10)
            except Exception:
                pass

_channel = _TelegramChannel()

def getLastMessage():
    """Return the last processed batch window."""        
    return _channel.get_last_message()

def start_telegram(token, chat_id=None):
    """Initialize and start the Telegram bot."""
    if isinstance(token, list) and len(token) > 0:
        token = str(token[0])
    
    token = str(token).strip("\"' ")
    
    if isinstance(chat_id, list) and len(chat_id) > 0:
        chat_id = str(chat_id[0])

    if chat_id is not None:
        chat_id = str(chat_id).strip("\"' ")
            
    return _channel.start(token, chat_id)

def stop_telegram():
    """Stop the Telegram bot."""
    _channel.stop()

def send_message(text):
    """Send a message to the active Telegram chat."""    
    # Run the async check safely in a synchronous context
    try:
        loop = asyncio.get_running_loop()
        is_blocked = loop.run_until_complete(is_category_blocked(text))
    except RuntimeError:
        is_blocked = asyncio.run(is_category_blocked(text))

    if is_blocked:
        alert_ethics_violation("send", text)
        return "Error: Refused: Unsafe response content."
        
    _channel.send_message(text)

def is_search_disabled():
    """Check if admin disabled searching."""
    return _channel.search_disabled

def alert_ethics_violation(tool_name, text=None):
    """Allow MeTTa to trigger an ethics alert DM to admins."""
    if _channel.loop and _channel.bot:
        for admin_id in _channel.admin_ids:
            try:
                fut = asyncio.run_coroutine_threadsafe(
                    _channel.bot.send_message(chat_id=admin_id, text=f"🚨 Ethics Pass Triggered!\nAction Blocked: {tool_name} | With message: {text}"),
                    _channel.loop
                )
            except Exception:
                logging.error(f"Failed to send ethics alert to admin {admin_id} for tool {tool_name}")