import asyncio
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

_running = False
_thread = None
_loop = None
_application = None
_last_message = None
_chat_id = None
_msg_lock = threading.Lock()
_connected = False

def _set_last(msg):
    global _last_message
    with _msg_lock:
        _last_message = msg

def getLastMessage():
    with _msg_lock:
        return _last_message

async def _start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _chat_id
    if update.effective_chat is not None:
        _chat_id = update.effective_chat.id
    if update.message is not None:
        await update.message.reply_text("Telegram channel ready.")

async def _echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _chat_id
    if update.message is None or update.message.text is None:
        return
    if update.effective_chat is not None:
        _chat_id = update.effective_chat.id
    user = update.effective_user
    if user is None:
        name = "telegram"
    else:
        name = user.full_name or user.username or str(user.id)
    _set_last(f"{name}: {update.message.text}")

async def _runner(token):
    global _application, _connected
    _application = Application.builder().token(token).build()
    _application.add_handler(CommandHandler("start", _start_cmd))
    _application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _echo))
    await _application.initialize()
    await _application.start()
    if _application.updater is not None:
        await _application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    _connected = True
    try:
        while _running:
            await asyncio.sleep(0.5)
    finally:
        _connected = False
        if _application is not None and _application.updater is not None:
            await _application.updater.stop()
        if _application is not None:
            await _application.stop()
            await _application.shutdown()

def _thread_main(token):
    global _loop
    loop = asyncio.new_event_loop()
    _loop = loop
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_runner(token))
    loop.close()
    _loop = None

def start_telegram(BOT_TOKEN_, CHAT_ID_=None):
    global _running, _thread, _chat_id
    _running = True
    _chat_id = CHAT_ID_
    _thread = threading.Thread(target=_thread_main, args=(BOT_TOKEN_,), daemon=True)
    _thread.start()
    return _thread

def stop_telegram():
    global _running
    _running = False

def send_message(text):
    text = text.replace("\\n", "\n")
    if not _connected or _application is None or _loop is None or _chat_id is None:
        return
    fut = asyncio.run_coroutine_threadsafe(
        _application.bot.send_message(chat_id=_chat_id, text=text),
        _loop,
    )
    try:
        fut.result(timeout=10)
    except Exception:
        pass

