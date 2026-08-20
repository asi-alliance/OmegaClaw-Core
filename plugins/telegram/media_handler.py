import base64
import hashlib
import threading
import logging
import sys

logger = logging.getLogger(__name__)

# skills.metta reaches this via `py-call (media_handler.describe_image ...)`, so
# the module must resolve under the bare name `media_handler` even when Python
# first imported it under a package-qualified name. Alias to one instance.
_self = sys.modules[__name__]
sys.modules.setdefault("media_handler", _self)
sys.modules.setdefault("src.media_handler", _self)

_lock = threading.Lock()
_pending_media = None
_pending_context = None
_describe_media = None          # kept for describe-image; survives a reply's clear_pending()
_pending_description = {}       # (image_key, query) -> caption, per-turn memo

VISION_PROMPT = (
    "Describe this image for a text-only assistant. Report objects, any visible "
    "text verbatim, layout, and notable details. Be concise and factual."
)


def set_pending_media(media):
    global _pending_media, _describe_media
    with _lock:
        _pending_media = media
        imgs = _image_parts(media)
        if imgs:
            _describe_media = media
            _pending_description.clear()
            logger.info("[IMGDBG] pending media set: %d image part(s)", len(imgs))
        elif media is None:
            _describe_media = None


def get_pending_media():
    with _lock:
        return _pending_media


def set_pending_context(text):
    global _pending_context
    with _lock:
        _pending_context = text


def get_pending_context():
    with _lock:
        return _pending_context


def clear_pending():
    """Drop the pending slots and memo once the agent has replied. The describe
    source is kept so describe-image is not blinded mid-turn by a reply."""
    global _pending_media, _pending_context
    with _lock:
        had = bool(_pending_media) or bool(_pending_context)
        _pending_media = None
        _pending_context = None
        _pending_description.clear()
    if had:
        logger.info("[IMGDBG] clear_pending: dropped pending media/context (describe source kept)")


def _image_parts(media):
    return [p for p in (media or [])
            if isinstance(p, dict) and p.get("type") == "image_url"]


def _image_key(image_parts):
    urls = "".join((p.get("image_url") or {}).get("url", "") for p in image_parts)
    return hashlib.sha256(urls.encode("utf-8")).hexdigest()


def _call_vision_model(image_parts, prompt):
    """Vision call via the configured vision provider. Isolated so tests stub it."""
    from vision import vision_chat
    return vision_chat(image_parts, prompt)


def describe_image(query=""):
    """describe-image skill: caption the currently-pending image so a non-vision
    agent can 'see' it. Memoized per turn; never raises — any failure, including
    a malformed pending-media value from a producer, returns a failure marker."""
    try:
        query = (query or "").strip()
        with _lock:
            source = _pending_media if _image_parts(_pending_media) else _describe_media
        parts = _image_parts(source)
        if not parts:
            logger.info("[IMGDBG] describe_image: no pending image available")
            return "[NO_IMAGE: nothing is attached to describe]"

        key = (_image_key(parts), query)
        with _lock:
            cached = _pending_description.get(key)
        if cached is not None:
            return cached

        prompt = VISION_PROMPT if not query else f"{VISION_PROMPT} Focus on: {query}"
        caption = _call_vision_model(parts, prompt)
        result = f"[IMAGE DESCRIPTION]\n{caption}"
        with _lock:
            _pending_description[key] = result
        logger.info("Described pending image: %d chars", len(caption))
        return result
    except Exception as e:
        logger.error("Image description failed: %s", e)
        return f"[IMAGE_DESCRIPTION_FAILED: {e}]"


def image_to_data_uri(file_bytes, mime_type):
    """Helper for image ingestion (used by the channel plugin)."""
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def build_multimodal_content(text, media):
    return [{"type": "text", "text": text}] + media


def sanitize_image(file_bytes, max_dim=2048, quality=85):
    """Re-encode an image via Pillow: strips EXIF/metadata and destroys most
    LSB-embedded steganographic payloads. Raises on undecodable input so the
    caller's existing error path rejects the file."""
    from PIL import Image
    from io import BytesIO
    img = Image.open(BytesIO(file_bytes))
    img = img.convert("RGB")
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim))
    out = BytesIO()
    img.save(out, format="JPEG", quality=quality)
    return out.getvalue()


def extract_pdf_text(file_bytes, filename, max_chars=20000):
    try:
        from pypdf import PdfReader
        from io import BytesIO

        reader = PdfReader(BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        text = "\n".join(pages)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[truncated]"
        logger.info(f"Extracted text from {filename}: {len(text)}")
        return f"[PDF: {filename}]\n{text}"
    except Exception as e:
        logger.error(f"PDF extraction failed for {filename}: {e}")
        return f"[PDF: {filename}]\n[Could not extract text: {e}]"


def transcribe_audio(file_bytes, filename, model="openai/whisper-large-v3", max_bytes=25 * 1024 * 1024, language=None, temperature=None):
    """Transcribe an audio/voice file to text via OpenRouter Whisper Large V3.

    Returns a marker-prefixed string for the PDF-style context slot, or an
    error note (never raises) so the agent still gets a usable turn.
    """
    try:
        if len(file_bytes) > max_bytes:
            return f"[AUDIO TRANSCRIPT: {filename}]\n[Audio too large to transcribe]"

        import io, openai
        import gateway

        base_url, api_key = gateway.upstream(
            "openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY")
        if not api_key:
            return f"[AUDIO TRANSCRIPT: {filename}]\n[Could not transcribe: OPENROUTER_API_KEY is not set]"

        client = openai.OpenAI(api_key=api_key, base_url=base_url)
        audio_file = io.BytesIO(file_bytes)
        audio_file.name = filename
        kwargs = { "model": model, "file": audio_file,}
        if language:
            kwargs["language"] = language

        if temperature is not None:
            kwargs["temperature"] = temperature

        resp = client.audio.transcriptions.create(**kwargs)
        text = (getattr(resp, "text", "") or "").strip()
        logger.info(f"Transcribed {filename}: {len(text)} chars")

        return f"[AUDIO TRANSCRIPT: {filename}]\n{text}"

    except Exception as e:
        logger.error(f"Audio transcription failed for {filename}: {e}")
        return f"[AUDIO TRANSCRIPT: {filename}]\n[Could not transcribe: {e}]"


# --- Image generation (outbound) -------------------------------------------
# Provider-agnostic text-to-image. The default is OpenRouter FLUX; the image
# provider is chosen INDEPENDENTLY of the chat `provider` (not every chat
# provider can generate images) via IMAGE_PROVIDER / IMAGE_MODEL env vars.
# OpenRouter's image endpoint is NOT OpenAI-SDK compatible (dedicated
# POST /api/v1/images), so that path uses a raw requests POST; both styles
# return the image as base64 in data[0].b64_json.
IMAGE_PROVIDERS = {
    "OpenRouter": {
        "style": "openrouter",
        "route": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "path": "images",
        "key_env": "OPENROUTER_API_KEY",
        "default_model": "black-forest-labs/flux.2-pro",
    },
    "OpenAI": {
        "style": "openai_sdk",
        "route": "openai",
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "default_model": "gpt-image-1",
    },
}


def _generate_image_bytes(prompt):
    """Generate an image for `prompt` via the configured image provider.
    Returns raw image bytes, or None on any failure (never raises)."""
    import os
    import gateway
    provider_name = os.environ.get("IMAGE_PROVIDER", "OpenRouter")
    cfg = IMAGE_PROVIDERS.get(provider_name) or IMAGE_PROVIDERS["OpenRouter"]
    model = os.environ.get("IMAGE_MODEL", cfg["default_model"])
    base_url, api_key = gateway.upstream(cfg["route"], cfg["base_url"], cfg["key_env"])
    if not api_key:
        logger.error(f"Image generation: {cfg['key_env']} not set for provider {provider_name}")
        return None
    try:
        if cfg["style"] == "openrouter":
            import requests
            resp = requests.post(
                f"{base_url.rstrip('/')}/{cfg['path']}",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"model": model, "prompt": prompt},
                timeout=120,
            )
            resp.raise_for_status()
            b64 = resp.json()["data"][0]["b64_json"]
        elif cfg["style"] == "openai_sdk":
            import openai
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            resp = client.images.generate(model=model, prompt=prompt)
            b64 = resp.data[0].b64_json
        else:
            logger.error(f"Image generation: unknown style for provider {provider_name}")
            return None
        image_bytes = base64.b64decode(b64)
        logger.info(f"Generated image via {provider_name}/{model}: {len(image_bytes)} bytes")
        return image_bytes
    except Exception as e:
        logger.error(f"Image generation failed ({provider_name}/{model}): {e}")
        return None


_live_send_photo = None
_live_channel = None


def register_channel(send_photo, channel):
    """Give this module a direct handle on the LIVE channel, called by the
    channel plugin's loadOmegaClawPlugin.

    Registration is explicit rather than looked up by module name because the
    plugin loader execs plugin modules without adding them to sys.modules, so
    `import telegram` here would build a second, never-started copy whose
    bot and event loop are None — generated images would be produced and then
    dropped."""
    global _live_send_photo, _live_channel
    _live_send_photo = send_photo
    _live_channel = channel


def _image_generation_allowed():
    """Read the allow_image_generation gate from the active channel's reply
    constraints. Fail closed (False) if unavailable."""
    try:
        constraints = getattr(_live_channel, "reply_constraints", None) or {}
        return bool(constraints.get("allow_image_generation", False))
    except Exception as e:
        logger.error(f"Could not read allow_image_generation gate: {e}")
        return False


def _prompt_is_unsafe(prompt):
    """Run the ethics classifier on the image prompt before spending money on
    generation. Sync bridge over the async is_category_blocked, mirroring
    tg_channel.send_message. Fail closed (unsafe) on unexpected error."""
    import asyncio
    from config_helper import is_category_blocked
    try:
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(is_category_blocked(prompt))
        except RuntimeError:
            return asyncio.run(is_category_blocked(prompt))
    except Exception as e:
        logger.error(f"Image prompt ethics check failed: {e}")
        return True


def generate_and_send(prompt):
    """generate-image skill: generate an image for `prompt` and send it to the
    user. Returns a short status string (never raises) that the agent sees next
    cycle in LAST_SKILL_USE_RESULTS. Bytes are generated and dispatched here
    (not through MeTTa, which only handles strings)."""
    prompt = (prompt or "").strip()
    if not prompt:
        return "IMAGE_FAILED: empty prompt"
    if not _image_generation_allowed():
        return "IMAGE_DISABLED: image generation is turned off"
    if _prompt_is_unsafe(prompt):
        return "Refused: unsafe image prompt"
    image_bytes = _generate_image_bytes(prompt)
    if not image_bytes:
        return f"IMAGE_FAILED: could not generate image for: {prompt}"
    if _live_send_photo is None:
        return "IMAGE_FAILED: generated but no channel is registered to send it"
    try:
        _live_send_photo(image_bytes, caption=prompt[:1024])
    except Exception as e:
        logger.error(f"Failed to send generated image: {e}")
        return f"IMAGE_FAILED: generated but could not send: {e}"
    return f"IMAGE_SENT: {prompt}"
