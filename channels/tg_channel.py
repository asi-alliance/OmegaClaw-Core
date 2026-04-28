import asyncio
import logging
import os
import threading
import time

import yaml
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command

from src.tg_config_helper import get_spam_protection_config, is_category_blocked

BASE_DIR = os.path.dirname(__file__)
log_dir = os.path.join(BASE_DIR, "..", "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(os.path.join(log_dir, "telegram.log"))],
)


class _TelegramChannel:
    def __init__(self, config_path=None):
        self.config_path = os.path.join(BASE_DIR, "..", "memory", "telegram_profile.yaml")
        self.policy_path = os.path.join(BASE_DIR, "..", "memory", "policy.md")
        self.running = self.connected = self.search_disabled = False
        self.thread = self.loop = self.bot = self.dp = self.chat_id = self.allowed_chat_id = None
        self.allowed_chat_ids = set()
        self.bot_username = self.bot_id = None
        self.msg_lock = threading.Lock()

        self.reply_only_on_tag = self.reply_on_reply = self.restrict_to_config_chat = True
        self.dm_enabled = self.allow_group_bots = False
        self.admin_ids = []
        self.reply_constraints = None
        self.start_msg = "Telegram mode active."
        self.about_msg = "I am a MeTTaClaw agent."
        self.privacy_msg = "No sensitive data is stored."

        self.load_config(self.config_path)
        self.load_policies()

        self._muted_users = {}
        self._user_msg_rates = {}
        self._user_mute_counts = {}
        self._message_queue = []
        self._reply_to_ids = {}
        self._paused_chats = set()
        self._polling_task = None

    def _normalize_chat_id(self, chat_id):
        if chat_id is None:
            return None
        chat_id = str(chat_id).strip("\"' ")
        if not chat_id:
            return None
        return f"-{chat_id}" if not chat_id.startswith("-") and chat_id.isdigit() and len(chat_id) > 10 else chat_id

    def _normalize_chat_ids(self, chat_ids):
        if chat_ids is None:
            return set()
        values = chat_ids if isinstance(chat_ids, (list, tuple, set)) else str(chat_ids).split(",")
        return {value for chat_id in values if (value := self._normalize_chat_id(chat_id))}

    def _is_allowed_chat(self, chat_id):
        return not self.restrict_to_config_chat or not self.allowed_chat_ids or self._normalize_chat_id(chat_id) in self.allowed_chat_ids

    def load_config(self, config_path):
        if not os.path.exists(config_path):
            print(f"Config file {config_path} not found. Using defaults.")
            logging.warning(f"Config file {config_path} not found. Using defaults.")
            return
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
            tg_cfg = config.get("telegram", {})
            self.reply_only_on_tag = tg_cfg.get("reply_only_when_directly_tagged", True)
            self.reply_on_reply = tg_cfg.get("reply_on_reply_to_bot", True)
            self.dm_enabled = tg_cfg.get("dm_support", {}).get("enabled", False)
            self.restrict_to_config_chat = tg_cfg.get("restrict_to_config_chat", True)
            self.allow_group_bots = tg_cfg.get("allow_group_bots", False)
            self.allowed_chat_ids = self._normalize_chat_ids(tg_cfg.get("allowed_chats", []))
            self.allowed_chat_id = next(iter(self.allowed_chat_ids), None)
            self.admin_ids = config.get("admin_controls", {}).get("admin_ids", [])
            self.reply_constraints = tg_cfg.get("reply_constraints", {})
            logging.info(f"Loaded config from {config_path}: tag_only={self.reply_only_on_tag}")
        except Exception as e:
            logging.error(f"Error loading config {config_path}: {e}")

    def load_policies(self):
        if not os.path.exists(self.policy_path):
            logging.warning(f"Policy file {self.policy_path} not found. Using defaults.")
            return
        try:
            with open(self.policy_path) as f:
                content = f.read()
            sections, current_section, current_text = {}, None, []
            for line in content.split("\n"):
                if line.startswith("# "):
                    if current_section:
                        sections[current_section] = "\n".join(current_text).strip()
                    current_section, current_text = line[2:].strip().upper(), []
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
        with self.msg_lock:
            if not self._message_queue:
                return None
            ready_chat_id, text, reply_id = self._message_queue.pop(0)
            if not self._is_allowed_chat(ready_chat_id) and ready_chat_id not in self.admin_ids:
                return None
            self.chat_id, self._reply_to_id = ready_chat_id, reply_id
            return text

    def _is_admin_dm(self, message: types.Message) -> bool:
        return message.chat.type == "private" and message.from_user is not None and message.from_user.id in self.admin_ids

    def _is_chat_authorized(self, message: types.Message) -> bool:
        if message.chat.type == "private":
            return getattr(message.from_user, "id", None) in self.admin_ids or self.dm_enabled
        return self._is_allowed_chat(message.chat.id)

    async def _admin_dm_required(self, message):
        if self._is_admin_dm(message):
            return False
        await message.answer("❌ Admin commands only work in direct messages.")
        return True

    async def _start_cmd(self, message: types.Message):
        if not self._is_chat_authorized(message) or await self._admin_dm_required(message):
            return
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        for text, data in [("ℹ️ About", "show_about"), ("🛡️ Privacy", "show_privacy"), ("⚙️ Admin Panel", "admin_panel")]:
            builder.button(text=text, callback_data=data)
        await message.answer(self.start_msg, reply_markup=builder.as_markup())

    async def _about_cmd(self, message: types.Message):
        await message.answer(self.about_msg)

    async def _privacy_cmd(self, message: types.Message):
        if self._is_chat_authorized(message):
            await message.answer(self.privacy_msg)

    async def _kill_cmd(self, message: types.Message):
        if await self._admin_dm_required(message):
            return
        await message.answer("⚠️ Global Kill Switch activated. Shutting down...")
        logging.critical(f"KILLED by admin {message.from_user.id}")
        self.stop()
        os._exit(0)

    async def _pause_cmd(self, message: types.Message):
        if not self._is_chat_authorized(message) or await self._admin_dm_required(message):
            return
        args = message.text.split()
        target_chat = args[1] if len(args) > 1 else self.allowed_chat_id or getattr(message.chat, "id", None)
        paused = target_chat in self._paused_chats
        (self._paused_chats.remove if paused else self._paused_chats.add)(target_chat)
        await message.answer(f"{'▶️' if paused else '⏸️'} Chat {target_chat} {'unpaused' if paused else 'paused'}.")

    async def _togglesearch_cmd(self, message: types.Message):
        if await self._admin_dm_required(message):
            return
        self.search_disabled = not self.search_disabled
        await message.answer(f"🔍 Web search is now {'DISABLED' if self.search_disabled else 'ENABLED'}.")

    async def _purge_cmd(self, message: types.Message):
        if await self._admin_dm_required(message):
            return
        try:
            import chromadb
            client = chromadb.PersistentClient(path="./chroma_db")
            client.delete_collection("memories")
            client.get_or_create_collection(name="memories")
            await message.answer("🗑️ Long-term memory purged successfully.")
        except Exception as e:
            await message.answer(f"❌ Failed to purge memory: {e}")

    async def _on_callback_query(self, callback: types.CallbackQuery):
        if not self._is_chat_authorized(callback.message):
            await callback.answer("❌ This chat is not authorized.", show_alert=True)
            return
        responses = {"show_about": self.about_msg, "show_privacy": self.privacy_msg}
        if callback.data in responses:
            await callback.message.answer(responses[callback.data])
        elif callback.data == "admin_panel":
            await callback.message.answer(
                "🛠 **Admin Commands:**\n/pause [chat_id] - Pause/unpause a chat\n/togglesearch - Enable/Disable Web Search\n/purge - Wipe ChromaDB Memory\n/kill - Shutdown Bot globally"
                if callback.from_user.id in self.admin_ids else "❌ Access denied."
            )
        await callback.answer()

    async def _on_message(self, message: types.Message):
        if message.text is None or message.chat.id in self._paused_chats or not self._is_chat_authorized(message):
            return
        if message.from_user:
            if message.chat.type in ["group", "supergroup"] and message.from_user.is_bot and not self.allow_group_bots:
                return
            if await self.is_user_muted(message.from_user):
                return
        if bool(message.photo or message.video or message.audio or message.voice) and not self.reply_constraints.get("allow_media", False):
            return
        if bool(message.document) and not self.reply_constraints.get("allow_files", False):
            return

        chat_id, user, text = message.chat.id, message.from_user, message.text
        name = "unknown user" if user is None else user.full_name or user.username or str(user.id)

        if await is_category_blocked(text):
            logging.warning(f"Ethics/Security pass rejected incoming message from {name}: {text}")
            alert_ethics_violation("incoming_message", "From: " + user.username + ": " + text if user and user.username else text)
            return

        if message.chat.type != "private":
            is_tagged = self.bot_username and f"@{self.bot_username}" in text
            is_reply = self.reply_on_reply and message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == self.bot_id
            if self.reply_only_on_tag and not (is_tagged or is_reply):
                return

        with self.msg_lock:
            self._message_queue.append((chat_id, f"{name}: {text}", message.message_id))

    async def is_user_muted(self, user: types.User):
        spam_config = get_spam_protection_config()
        time_window, message_limit = spam_config["time_window"], spam_config["message_limit"]
        cooldown_duration, admin_alert_threshold = spam_config["cooldown_duration"], spam_config["admin_alert_threshold"]
        user_id, now = user.id, time.time()

        if user_id in self._muted_users:
            if now < self._muted_users[user_id]:
                return True
            del self._muted_users[user_id]

        history = [ts for ts in self._user_msg_rates.get(user_id, []) if now - ts < time_window] + [now]
        self._user_msg_rates[user_id] = history

        if len(history) <= message_limit:
            return False

        mute_count = self._user_mute_counts.get(user_id, 0) + 1
        self._user_mute_counts[user_id] = mute_count
        username = user.username or user.full_name or str(user_id)
        logging.warning(f"User with id: {user_id} | username: {username} muted for spamming.")
        self._muted_users[user_id] = now + cooldown_duration

        if mute_count >= admin_alert_threshold:
            for admin_id in self.admin_ids:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text=f"🚨 **Spam Alert** 🚨\nUser @{username} (ID: {user_id}) has been temporarily muted for spamming.\nTotal times muted: {mute_count}",
                    )
                except Exception as e:
                    logging.error(f"Failed to notify admin {admin_id}: {e}")

        return True

    async def _on_media_rejected(self, message: types.Message):
        if self._is_chat_authorized(message):
            logging.info("Denied capability invoked: Media/File uploaded. Discarding.")

    async def _runner(self, token):
        self.bot, self.dp = Bot(token=token), Dispatcher()
        try:
            bot_info = await self.bot.get_me()
            self.bot_username, self.bot_id = bot_info.username, bot_info.id

            chat_ids_for_admin_scan = list(self.allowed_chat_ids)
            if self.chat_id and (normalized_chat_id := self._normalize_chat_id(self.chat_id)):
                chat_ids_for_admin_scan.append(normalized_chat_id)

            for eval_chat_id in dict.fromkeys(chat_ids_for_admin_scan):
                try:
                    admins = await self.bot.get_chat_administrators(eval_chat_id)
                    self.admin_ids += [int(admin.user.id) for admin in admins if admin.user.id not in self.admin_ids]
                    logging.info(f"Loaded admins from group {eval_chat_id}. Total admins: {len(self.admin_ids)}")
                except Exception as e:
                    logging.error(f"Failed to fetch administrators for chat {eval_chat_id}: {e}")

            for cmd, handler in {
                "start": self._start_cmd,
                "about": self._about_cmd,
                "privacy": self._privacy_cmd,
                "kill": self._kill_cmd,
                "pause": self._pause_cmd,
                "togglesearch": self._togglesearch_cmd,
                "purge": self._purge_cmd,
            }.items():
                self.dp.message.register(handler, Command(cmd))

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
        self.loop = loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._runner(token))
        except Exception as e:
            logging.error(f"Telegram runner error in thread: {e}")
        finally:
            loop.close()
            self.loop = None

    def start(self, token, chat_id=None, config_path=None):
        self.running = True
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
        self.running = False
        if self.loop and self._polling_task:
            self.loop.call_soon_threadsafe(self._polling_task.cancel)

    def send_message(self, text):
        text = text.replace("\\n", "\n")
        if not self.connected or self.bot is None or self.loop is None or self.chat_id is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    reply_to_message_id=self._reply_to_id,
                    parse_mode="MarkdownV2",
                ),
                self.loop,
            ).result(timeout=10)
        except Exception as e:
            logging.error(f"Telegram formatting error, falling back to plain text: {e}")
            try:
                asyncio.run_coroutine_threadsafe(
                    self.bot.send_message(chat_id=self.chat_id, text=text, reply_to_message_id=self._reply_to_id),
                    self.loop,
                ).result(timeout=10)
            except Exception:
                pass


_channel = _TelegramChannel()


def getLastMessage():
    return _channel.get_last_message()


def start_telegram(token, chat_id=None):
    token = str(token[0] if isinstance(token, list) and token else token).strip("\"' ")
    if isinstance(chat_id, list):
        chat_id = [value for item in chat_id if (value := str(item).strip("\"' "))]
    elif chat_id is not None:
        chat_id = str(chat_id).strip("\"' ")
    return _channel.start(token, chat_id)


def stop_telegram():
    _channel.stop()


def send_message(text):
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
    return _channel.search_disabled


def alert_ethics_violation(tool_name, text=None):
    if _channel.loop and _channel.bot:
        for admin_id in _channel.admin_ids:
            try:
                asyncio.run_coroutine_threadsafe(
                    _channel.bot.send_message(
                        chat_id=admin_id,
                        text=f"🚨 Ethics Pass Triggered!\nAction Blocked: {tool_name} | With message: {text}",
                    ),
                    _channel.loop,
                )
            except Exception:
                logging.error(f"Failed to send ethics alert to admin {admin_id} for tool {tool_name}")