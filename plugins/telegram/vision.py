import os
import logging

logger = logging.getLogger(__name__)

# The vision provider is chosen INDEPENDENTLY of the chat `provider`: not every
# chat provider can see images, and an account's data policy can exclude the
# ones that can. Every entry speaks the OpenAI chat-completions dialect
# (Anthropic serves one at /v1/), so a single client shape covers them all and
# switching is a matter of base URL, key and model. Pick one with
# VISION_PROVIDER, override its model with VISION_MODEL.
VISION_PROVIDERS = {
    "Anthropic": {
        "route": "anthropic",
        "base_url": "https://api.anthropic.com/v1/",
        "key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-haiku-4-5-20251001",
    },
    "OpenRouter": {
        "route": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "default_model": "anthropic/claude-haiku-4.5",
    },
}
DEFAULT_PROVIDER = "Anthropic"


def _config():
    """Resolve the selected provider to its (name, settings) pair."""
    name = os.environ.get("VISION_PROVIDER") or DEFAULT_PROVIDER
    cfg = VISION_PROVIDERS.get(name)
    if cfg is None:
        raise RuntimeError(
            f"unknown VISION_PROVIDER {name!r}; expected one of {sorted(VISION_PROVIDERS)}")
    return name, cfg


def _model():
    return os.environ.get("VISION_MODEL") or _config()[1]["default_model"]


def _make_client():
    """Create the vision client. Isolated so tests can stub it.

    Behind the gateway proxy there is no key to read - the proxy holds it - so
    the destination comes from gateway.upstream rather than the environment."""
    import openai
    import gateway
    name, cfg = _config()
    base_url, api_key = gateway.upstream(cfg["route"], cfg["base_url"], cfg["key_env"])
    if not api_key:
        raise RuntimeError(
            f"vision provider {name} is not available (set {cfg['key_env']}, "
            "or run behind the gateway proxy)")
    return openai.OpenAI(api_key=api_key, base_url=base_url)


def vision_chat(image_parts, prompt, max_tokens=1024):
    """Caption image(s) with the configured vision provider.

    `image_parts` are OpenAI multimodal `image_url` parts, which is what the
    telegram channel already produces (one base64 `data:` URI per attached
    image), so no per-provider reshaping is needed. Returns the caption text
    and raises on any failure — `media_handler.describe_image` owns the
    graceful degradation.

    `max_tokens` is always sent because Anthropic's compatibility endpoint
    requires it; the default is ample for a caption.
    """
    client = _make_client()
    content = [{"type": "text", "text": prompt}] + list(image_parts)
    resp = client.chat.completions.create(
        model=_model(),
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
    )
    caption = (resp.choices[0].message.content or "").strip()
    if not caption:
        raise RuntimeError("empty caption from vision provider")
    logger.info("Vision described image: %d chars", len(caption))
    return caption


def loadOmegaClawPlugin():
    """Plugin entry point. Importing this module puts `plugins/telegram` on sys.path
    and imports media_handler, so `py-call (media_handler.describe_image ...)` in
    skills.metta resolves. describe_image calls vision_chat directly, so no
    LLMProvider needs registering for the describe-image path."""
    import media_handler  # noqa: F401 — ensures the media_handler alias is set
