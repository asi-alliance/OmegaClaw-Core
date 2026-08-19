import asyncio
import logging
import os
import sys
import threading
import time
import types
from types import SimpleNamespace

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_DIR = os.path.dirname(_HERE)
_REPO_ROOT = os.path.dirname(os.path.dirname(_PLUGIN_DIR))

# telegram_channel.py pulls in core's channels/config modules (src/) and core's shared
# channel infrastructure (channels/auth.py, channels/delivery_queue.py) the same
# way it does when loaded as a real plugin.
for _path in (_REPO_ROOT,
              os.path.join(_REPO_ROOT, "channels"),
              os.path.join(_REPO_ROOT, "src"),
              _PLUGIN_DIR):
    sys.path.insert(0, _path)

try:
    import channels  # noqa: F401
except ModuleNotFoundError:
    # Checked out on its own, with no core tree above this directory. Stub the
    # host modules the channel touches so the suite stays runnable standalone;
    # the real ones only matter when the plugin is loaded by core.
    _chan = types.ModuleType("channels")

    class _CommChannel:
        def start(self): pass
        def stop(self): pass
        def receive(self): pass
        def send(self, message): pass

    _chan.CommChannel = _CommChannel
    _chan.registerCommChannel = lambda name, channel: None
    sys.modules["channels"] = _chan

    _cfg = types.ModuleType("config")
    _cfg.config_get_by_key = lambda key, default=None: os.environ.get(f"OMEGACLAW_{key}", default)
    sys.modules["config"] = _cfg

    _auth = types.ModuleType("auth")
    _auth.get_proxy_url = lambda: ""
    _auth.is_auth_enabled = lambda: False
    _auth.authenticate_channel_user = lambda channel, user_id, candidate=None: "allow"
    sys.modules["auth"] = _auth

    _dq = types.ModuleType("delivery_queue")

    class _PendingMessages:
        """Minimum viable stand-in: ordered, retains the head on failure."""

        def __init__(self):
            self._items = []

        def put(self, message):
            self._items.append(message)

        def flush(self, deliver, ready=None):
            while self._items and (ready is None or ready()):
                deliver(self._items[0])
                self._items.pop(0)

        def __len__(self):
            return len(self._items)

    _dq.PendingMessages = _PendingMessages
    sys.modules["delivery_queue"] = _dq

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import telegram_channel as tm
import media_handler as mh
from aiogram.types import BufferedInputFile


def _stub(monkeys):
    """Set module attributes, return a restore function."""
    saved = {}
    for mod, name, value in monkeys:
        saved[(mod, name)] = getattr(mod, name)
        setattr(mod, name, value)

    def restore():
        for (mod, name), value in saved.items():
            setattr(mod, name, value)
    return restore


def _fake_message(chat_id=1, chat_type="private", user_id=42, is_bot=False,
                   text=None, caption=None, photo=None, document=None,
                   voice=None, audio=None, video=None, reply_to_message=None,
                   message_id=1):
    answers = []

    async def answer(text, **kwargs):
        answers.append((text, kwargs))

    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id, type=chat_type),
        from_user=SimpleNamespace(id=user_id, username="tester", full_name="Tester",
                                   is_bot=is_bot),
        text=text,
        caption=caption,
        photo=photo,
        document=document,
        voice=voice,
        audio=audio,
        video=video,
        reply_to_message=reply_to_message,
        message_id=message_id,
        answer=answer,
        _answers=answers,
    )


def _new_channel(admin_ids=(42,)):
    """A fresh _TelegramChannel loaded from the real plugin-local config, with
    admin_ids overridden so a private-chat admin test doesn't depend on the
    (empty by default) telegram_profile.yaml admin list."""
    ch = tm._TelegramChannel()
    ch.admin_ids = list(admin_ids)
    return ch


class FakeBot:
    """Stub aiogram Bot: download() fills the destination buffer; send_photo()
    records the call instead of hitting the network."""

    def __init__(self, download_bytes=b"raw-bytes", reject_markdown=False):
        self.download_bytes = download_bytes
        self.sent_photo = None
        self.sent_messages = []
        self.reject_markdown = reject_markdown

    async def download(self, file_obj, destination):
        destination.write(self.download_bytes)

    async def send_message(self, chat_id, text, reply_to_message_id=None, parse_mode=None):
        if parse_mode == "MarkdownV2" and self.reject_markdown:
            raise RuntimeError("can't parse entities")
        self.sent_messages.append({"chat_id": chat_id, "text": text,
                                    "reply_to_message_id": reply_to_message_id,
                                    "parse_mode": parse_mode})
        return SimpleNamespace()

    async def send_photo(self, chat_id, photo, caption=None, reply_to_message_id=None):
        self.sent_photo = {"chat_id": chat_id, "photo": photo, "caption": caption,
                            "reply_to_message_id": reply_to_message_id}
        return SimpleNamespace()


def test_photo_handler_buffers_image_and_queues_marker():
    ch = _new_channel()
    ch.bot = FakeBot()
    restore = _stub([
        (mh, "sanitize_image", lambda raw: b"sanitized-jpeg"),
        (mh, "image_to_data_uri", lambda img, mime: "data:image/jpeg;base64,AAAA"),
    ])
    calls = {}

    def fake_set_pending_media(media):
        calls["media"] = media
    mh.set_pending_media = fake_set_pending_media

    try:
        message = _fake_message(photo=[SimpleNamespace(), SimpleNamespace()])
        asyncio.run(ch._on_photo(message))
        assert len(ch._message_queue) == 1
        result = ch.get_last_message()
        assert result is not None and "[image]" in result, result
        assert calls["media"] == [{"type": "image_url",
                                    "image_url": {"url": "data:image/jpeg;base64,AAAA"}}]
    finally:
        restore()


def test_pdf_handler_extracts_text():
    ch = _new_channel()
    ch.bot = FakeBot()

    async def not_blocked(text):
        return False
    restore = _stub([
        (mh, "extract_pdf_text", lambda raw, filename: "extracted text here"),
        (tm, "is_category_blocked", not_blocked),
    ])
    try:
        message = _fake_message(document=SimpleNamespace(mime_type="application/pdf",
                                                           file_name="report.pdf"))
        asyncio.run(ch._on_document(message))
        assert len(ch._message_queue) == 1
        chat_id, display_text, reply_id, payload = ch._message_queue[0]
        assert "report.pdf" in display_text, display_text
        assert payload == {"media": None, "context": "extracted text here"}

        # Regression: the extracted text must reach the agent. There is no
        # on-demand skill for PDFs like describe-image, so if get_last_message
        # doesn't inline it, the agent never sees the document at all.
        result = ch.get_last_message()
        assert "extracted text here" in result, result
    finally:
        restore()


def test_pdf_handler_rejects_non_pdf_document():
    ch = _new_channel()
    ch.bot = FakeBot()
    message = _fake_message(document=SimpleNamespace(mime_type="text/plain",
                                                       file_name="notes.txt"))
    asyncio.run(ch._on_document(message))
    assert len(ch._message_queue) == 0
    assert message._answers, "expected a rejection notice"
    assert "PDF" in message._answers[0][0]


def test_voice_handler_transcribes_audio():
    ch = _new_channel()
    ch.bot = FakeBot()

    async def not_blocked(text):
        return False
    restore = _stub([
        (mh, "transcribe_audio", lambda raw, filename: "hello from the transcript"),
        (tm, "is_category_blocked", not_blocked),
    ])
    try:
        message = _fake_message(voice=SimpleNamespace(file_id="v1", file_name=None))
        asyncio.run(ch._on_audio(message))
        assert len(ch._message_queue) == 1
        chat_id, display_text, reply_id, payload = ch._message_queue[0]
        assert "sent audio" in display_text, display_text
        assert payload == {"media": None, "context": "hello from the transcript"}

        result = ch.get_last_message()
        assert "hello from the transcript" in result, result
    finally:
        restore()


def test_muted_user_is_gated_from_message_queue():
    ch = _new_channel()

    async def not_blocked(text):
        return False
    restore = _stub([
        (tm, "get_spam_protection_config", lambda: {
            "time_window": 10, "message_limit": 1,
            "cooldown_duration": 120, "admin_alert_threshold": 3,
        }),
        (tm, "is_category_blocked", not_blocked),
    ])
    try:
        user = SimpleNamespace(id=99, username="spammer", full_name="Spammer", is_bot=False)
        # First call establishes history; second exceeds message_limit=1 and mutes.
        assert asyncio.run(ch.is_user_muted(user)) is False
        assert asyncio.run(ch.is_user_muted(user)) is True

        message = _fake_message(user_id=99, text="hello again")
        asyncio.run(ch._on_message(message))
        assert len(ch._message_queue) == 0, "muted user's message must not be queued"
    finally:
        restore()


def test_inbound_ethics_block_prevents_queueing():
    ch = _new_channel()

    async def blocked(text):
        return True
    restore = _stub([
        (tm, "is_category_blocked", blocked),
        (tm, "alert_ethics_violation", lambda tool_name, text=None: None),
    ])
    try:
        message = _fake_message(text="something unsafe")
        asyncio.run(ch._on_message(message))
        assert len(ch._message_queue) == 0, "blocked message must not be queued"
    finally:
        restore()


def test_send_photo_dispatches_expected_aiogram_call():
    ch = _new_channel()
    bot = FakeBot()
    ch.bot = bot
    ch.connected = True
    ch.chat_id = "555"
    ch._reply_to_id = None

    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    ch.loop = loop
    try:
        ch.send_photo(b"image-bytes", caption="a cat")
        assert bot.sent_photo is not None
        assert bot.sent_photo["chat_id"] == "555"
        assert bot.sent_photo["caption"] == "a cat"
        assert isinstance(bot.sent_photo["photo"], BufferedInputFile)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        t.join(timeout=2)


def test_admin_command_refuses_non_admin_allows_admin():
    """_purge_cmd (admin-only, private-DM-only) must refuse a non-admin and
    take no destructive effect, and must proceed for an admin. The purge must go
    through core's rag module: it owns the database location and caches the
    collection handle, so purging around it targets the wrong directory and
    leaves the agent holding a deleted collection."""
    ch = _new_channel(admin_ids=(42,))
    calls = {"deleted": False}

    class FakeRagClient:
        def delete_collection(self, name):
            assert name == "memories", name
            calls["deleted"] = True

    fake_rag = SimpleNamespace(
        DB_PATH="/somewhere/else/chroma_db",
        COLLECTION_NAME="memories",
        _client=FakeRagClient(),
        _collection=object(),
        _get_collection=lambda: None,
    )
    sys.modules["rag"] = fake_rag
    try:
        non_admin = _fake_message(chat_type="private", user_id=999)
        assert ch._is_admin_dm(non_admin) is False
        asyncio.run(ch._purge_cmd(non_admin))
        assert calls["deleted"] is False, "non-admin must not trigger the purge"
        assert non_admin._answers, "expected a refusal reply"
        assert "Admin commands only work in direct messages" in non_admin._answers[0][0]

        admin = _fake_message(chat_type="private", user_id=42)
        assert ch._is_admin_dm(admin) is True
        asyncio.run(ch._purge_cmd(admin))
        assert calls["deleted"] is True, "admin command must proceed"
        assert fake_rag._collection is None, "rag's cached handle must be dropped"
    finally:
        del sys.modules["rag"]


def test_destructive_admin_commands_clear_the_auth_handshake():
    """/kill, /purge and /togglesearch gate on _is_admin_dm alone. With core's
    auth enabled an admin who has not bound themselves must not reach them —
    otherwise the most destructive commands are the only ones skipping auth."""
    ch = _new_channel(admin_ids=(42,))
    states = {"result": "ignore"}
    restore = _stub([
        (tm.auth, "is_auth_enabled", lambda: True),
        (tm.auth, "authenticate_channel_user",
         lambda channel, user_id, candidate=None: states["result"]),
    ])
    try:
        admin = _fake_message(chat_type="private", user_id=42, text="/purge")
        assert ch._is_admin_dm(admin) is False, "unbound admin must be refused"

        states["result"] = "allow"
        assert ch._is_admin_dm(admin) is True, "a bound admin must get through"
    finally:
        restore()


def test_ethics_alert_reports_when_it_cannot_be_delivered():
    """A silent ethics alert reads as 'no blocks happened'. Both no-admin and
    failed-delivery must leave a record."""
    ch = tm._channel
    saved = (ch.loop, ch.bot, list(ch.admin_ids))
    records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = _Capture(level=logging.ERROR)
    logging.getLogger().addHandler(handler)

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        class FailingBot:
            async def send_message(self, chat_id, text):
                raise RuntimeError("bot was blocked by the user")

        ch.loop, ch.bot, ch.admin_ids = loop, FailingBot(), []
        tm.alert_ethics_violation("send", "unsafe")
        assert any("no admin_ids" in m for m in records), records

        records.clear()
        ch.admin_ids = [42]
        tm.alert_ethics_violation("send", "unsafe")
        for _ in range(100):
            if any("blocked by the user" in m for m in records):
                break
            time.sleep(0.01)
        assert any("blocked by the user" in m for m in records), records
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)
        logging.getLogger().removeHandler(handler)
        ch.loop, ch.bot, ch.admin_ids = saved


def test_about_respects_the_allowed_chat_list():
    """/about answered in any chat regardless of restrict_to_config_chat, which
    is exactly what that setting exists to prevent."""
    ch = _new_channel()
    ch.restrict_to_config_chat = True
    ch.allowed_chat_ids = {"-1001234567890"}

    outside = _fake_message(chat_type="group", chat_id=-1009999999999, user_id=7)
    asyncio.run(ch._about_cmd(outside))
    assert not outside._answers, "must not answer in a chat outside allowed_chats"

    inside = _fake_message(chat_type="group", chat_id=-1001234567890, user_id=7)
    asyncio.run(ch._about_cmd(inside))
    assert inside._answers, "must answer in an allowed chat"


def test_pause_actually_gates_the_chat_it_names():
    """/pause is an admin safety control. Chat ids arrive as ints from aiogram
    and as strings from the command and the config, so a pause recorded in one
    form must still be seen in the other."""
    ch = _new_channel(admin_ids=(42,))
    ch.allowed_chat_ids = {"-1001234567890"}
    ch.allowed_chat_id = "-1001234567890"

    admin_dm = _fake_message(chat_type="private", user_id=42,
                              text="/pause -1001234567890")
    asyncio.run(ch._pause_cmd(admin_dm))
    assert ch._paused_chats, "the chat must be recorded as paused"
    assert ch._is_paused(-1001234567890), "the int form aiogram delivers must match"

    async def not_blocked(text):
        return False
    restore = _stub([(tm, "is_category_blocked", not_blocked)])
    try:
        ch.bot_username = "mybot"
        ch.bot_id = 555
        paused = _fake_message(chat_type="group", chat_id=-1001234567890,
                               user_id=1001, text="@mybot hello")
        asyncio.run(ch._on_message(paused))
        assert len(ch._message_queue) == 0, "a paused chat must not reach the queue"
    finally:
        restore()

    asyncio.run(ch._pause_cmd(admin_dm))
    assert not ch._paused_chats, "a second /pause must unpause"


def test_group_message_requires_tag_or_reply():
    """Untagged group chatter must be dropped; a tagged message or a reply to
    the bot must be queued."""
    ch = _new_channel()
    ch.bot_username = "mybot"
    ch.bot_id = 555

    async def not_blocked(text):
        return False
    restore = _stub([(tm, "is_category_blocked", not_blocked)])
    try:
        untagged = _fake_message(chat_type="group", user_id=1001, text="just chatting")
        asyncio.run(ch._on_message(untagged))
        assert len(ch._message_queue) == 0, "untagged group chatter must not be queued"

        tagged = _fake_message(chat_type="group", user_id=1002, text="@mybot hello there")
        asyncio.run(ch._on_message(tagged))
        assert len(ch._message_queue) == 1, "a message tagging the bot must be queued"

        reply_to_bot = _fake_message(
            chat_type="group", user_id=1003, text="answering you",
            reply_to_message=SimpleNamespace(from_user=SimpleNamespace(id=555)),
        )
        asyncio.run(ch._on_message(reply_to_bot))
        assert len(ch._message_queue) == 2, "a reply to the bot must be queued"
    finally:
        restore()


def test_dm_authorization_gates_non_admin_allows_admin():
    """_is_chat_authorized DM branch: with dm_enabled False (shipped default),
    a non-admin DM is not authorized; an admin DM is."""
    ch = _new_channel(admin_ids=(42,))
    ch.dm_enabled = False

    non_admin_dm = _fake_message(chat_type="private", user_id=7)
    assert ch._is_chat_authorized(non_admin_dm) is False

    admin_dm = _fake_message(chat_type="private", user_id=42)
    assert ch._is_chat_authorized(admin_dm) is True

    # End-to-end: an unauthorized DM must not reach the message queue.
    async def not_blocked(text):
        return False
    restore = _stub([(tm, "is_category_blocked", not_blocked)])
    try:
        blocked_msg = _fake_message(chat_type="private", user_id=7, text="hi")
        asyncio.run(ch._on_message(blocked_msg))
        assert len(ch._message_queue) == 0, "unauthorized DM must not be queued"
    finally:
        restore()


def test_plugin_registration_exposes_comm_channel():
    """Core drives a channel through start/stop/receive/send. A channel that
    still exposes the older config() is never started at all."""
    channel_api = __import__("channels").CommChannel
    assert issubclass(tm.TelegramChannel, channel_api)
    channel = tm.TelegramChannel()
    for name in ("start", "stop", "receive", "send"):
        assert callable(getattr(channel, name, None)), name


def test_outbox_holds_messages_until_the_bot_connects():
    """A send before the bot has connected must be queued, not dropped: the
    agent sends its version banner before polling is up."""
    ch = _new_channel()
    ch.connected = False
    ch.chat_id = "555"

    ch.send_message("version banner")
    assert len(ch._outbox) == 1, "an undeliverable message must stay queued"

    delivered = []
    ch._deliver = lambda item: delivered.append(item)
    ch.bot = FakeBot()
    ch.loop = object()
    ch.connected = True

    ch.get_last_message()          # the agent-side pump
    assert delivered == [("555", None, "version banner")], delivered
    assert len(ch._outbox) == 0


def _run_delivery(bot, text):
    """Deliver one queued message through the real _deliver on a live loop, the
    way the agent thread does, and return the calls the bot saw."""
    ch = _new_channel()
    ch.bot = bot
    ch.connected = True
    ch.chat_id = "555"
    ch._reply_to_id = None

    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    ch.loop = loop
    try:
        ch.send_message(text)
        return bot.sent_messages
    finally:
        loop.call_soon_threadsafe(loop.stop)
        t.join(timeout=2)


def test_outbound_text_is_delivered_as_markdown():
    sent = _run_delivery(FakeBot(), "hello *there*")
    assert len(sent) == 1, sent
    assert sent[0]["chat_id"] == "555"
    assert sent[0]["parse_mode"] == "MarkdownV2"


def test_outbound_text_falls_back_to_plain_when_markdown_is_rejected():
    """Telegram rejects malformed MarkdownV2 outright. The message must still
    arrive, unformatted, rather than being lost to the parse error."""
    sent = _run_delivery(FakeBot(reject_markdown=True), "unbalanced *markdown")
    assert len(sent) == 1, sent
    assert sent[0]["parse_mode"] is None
    assert sent[0]["text"] == "unbalanced *markdown"


def test_auth_handshake_gates_then_binds_a_user():
    """With core's channel auth enabled an unbound user is ignored; the binding
    message lets them through and queues a confirmation."""
    ch = _new_channel(admin_ids=(42,))
    states = {"result": "ignore"}
    restore = _stub([
        (tm.auth, "is_auth_enabled", lambda: True),
        (tm.auth, "authenticate_channel_user",
         lambda channel, user_id, candidate=None: states["result"]),
    ])
    try:
        unbound = _fake_message(chat_type="private", user_id=42, text="hello")
        assert ch._is_chat_authorized(unbound) is False
        assert len(ch._outbox) == 0

        states["result"] = "auth_bound"
        binding = _fake_message(chat_type="private", user_id=42, text="auth s3cret")
        assert ch._is_chat_authorized(binding) is True
        assert len(ch._outbox) == 1, "a fresh binding must be confirmed to the user"
    finally:
        restore()


def test_proxy_routes_api_calls_and_file_downloads():
    """When a gateway proxy is configured the bot must talk to the proxy, so the
    real token never enters this process, and file downloads need their own
    route because Telegram serves files from a different path prefix."""
    restore = _stub([(tm.auth, "get_proxy_url", lambda: "http://proxy:8080")])
    try:
        bot = tm._build_bot(tm._PROXY_TOKEN)
        api = bot.session.api
        assert api.api_url("ignored", "getUpdates") == "http://proxy:8080/telegram/getUpdates"
        assert api.file_url("ignored", "photos/f.jpg") == "http://proxy:8080/telegram-file/photos/f.jpg"
    finally:
        restore()


def _admin_scan_levels(raised, admin_ids=()):
    """Run the real admin scan against a bot that raises `raised`, and return
    (log level numbers emitted, resulting admin_ids)."""
    ch = _new_channel(admin_ids=admin_ids)

    class _Bot:
        async def get_chat_administrators(self, chat_id):
            if isinstance(raised, BaseException):
                raise raised
            return raised

    ch.bot = _Bot()
    levels = []

    class _Capture(logging.Handler):
        def emit(self, record):
            levels.append(record.levelno)

    handler = _Capture()
    root = logging.getLogger()
    prior = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        asyncio.run(ch._load_chat_admins([777]))
    finally:
        root.removeHandler(handler)
        root.setLevel(prior)
    return levels, ch.admin_ids


def test_private_chat_admin_scan_is_not_an_error():
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import GetChatAdministrators

    exc = TelegramBadRequest(
        method=GetChatAdministrators(chat_id=777),
        message="Bad Request: there are no administrators in the private chat")
    levels, _ = _admin_scan_levels(exc)
    assert logging.ERROR not in levels, levels
    assert logging.INFO in levels, levels


def test_other_admin_scan_failures_still_log_errors():
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import GetChatAdministrators

    exc = TelegramBadRequest(
        method=GetChatAdministrators(chat_id=777),
        message="Bad Request: chat not found")
    levels, _ = _admin_scan_levels(exc)
    assert logging.ERROR in levels, levels


def test_admin_scan_collects_admin_ids():
    admins = [SimpleNamespace(user=SimpleNamespace(id=5)),
              SimpleNamespace(user=SimpleNamespace(id=6))]
    levels, admin_ids = _admin_scan_levels(admins)
    assert admin_ids == [5, 6], admin_ids
    assert logging.ERROR not in levels, levels


if __name__ == "__main__":
    test_photo_handler_buffers_image_and_queues_marker()
    test_pdf_handler_extracts_text()
    test_pdf_handler_rejects_non_pdf_document()
    test_voice_handler_transcribes_audio()
    test_muted_user_is_gated_from_message_queue()
    test_inbound_ethics_block_prevents_queueing()
    test_send_photo_dispatches_expected_aiogram_call()
    test_admin_command_refuses_non_admin_allows_admin()
    test_pause_actually_gates_the_chat_it_names()
    test_destructive_admin_commands_clear_the_auth_handshake()
    test_about_respects_the_allowed_chat_list()
    test_ethics_alert_reports_when_it_cannot_be_delivered()
    test_group_message_requires_tag_or_reply()
    test_dm_authorization_gates_non_admin_allows_admin()
    test_plugin_registration_exposes_comm_channel()
    test_private_chat_admin_scan_is_not_an_error()
    test_other_admin_scan_failures_still_log_errors()
    test_admin_scan_collects_admin_ids()
    test_outbox_holds_messages_until_the_bot_connects()
    test_outbound_text_is_delivered_as_markdown()
    test_outbound_text_falls_back_to_plain_when_markdown_is_rejected()
    test_auth_handshake_gates_then_binds_a_user()
    test_proxy_routes_api_calls_and_file_downloads()
    print("all telegram channel tests passed")
