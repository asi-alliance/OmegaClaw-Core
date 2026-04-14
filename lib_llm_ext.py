import os
import random
import time

import openai

def _init_openai_client(var_name, base_url):
    if var_name in os.environ:
        return openai.OpenAI(api_key=os.environ[var_name], base_url=base_url)
    else:
        return None

ASI_CLIENT = _init_openai_client(
    var_name="ASI_API_KEY",
    base_url="https://inference.asicloud.cudos.org/v1"
)

ANTHROPIC_CLIENT = _init_openai_client(
    var_name="ANTHROPIC_API_KEY",
    base_url="https://api.anthropic.com/v1/"
)

def _clean(text):
    return text.replace("_quote_", '"').replace("_apostrophe_", "'")


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _status_code(exc):
    code = getattr(exc, "status_code", None)
    if code is not None:
        return code
    response = getattr(exc, "response", None)
    if response is not None:
        return getattr(response, "status_code", None)
    return None


def _retry_after_seconds(exc):
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    value = headers.get("retry-after") or headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def _chat(client, model, content, max_tokens=6000):
    if client is None:
        return "error: missing API key"

    max_retries = _env_int("OMEGACLAW_429_MAX_RETRIES", 5)
    base_delay = _env_float("OMEGACLAW_429_BASE_DELAY_SECONDS", 1.5)
    max_delay = _env_float("OMEGACLAW_429_MAX_DELAY_SECONDS", 30.0)
    jitter = _env_float("OMEGACLAW_429_JITTER", 0.2)

    attempt = 0
    while True:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                max_tokens=max_tokens
            )
            return _clean(resp.choices[0].message.content)
        except Exception as e:
            code = _status_code(e)
            if code != 429 or attempt >= max_retries:
                return f"error: {e}"

            retry_after = _retry_after_seconds(e)
            if retry_after is not None:
                sleep_s = retry_after
            else:
                sleep_s = min(max_delay, base_delay * (2 ** attempt))
                if jitter > 0:
                    low = max(0.0, 1.0 - jitter)
                    high = 1.0 + jitter
                    sleep_s *= random.uniform(low, high)

            time.sleep(max(0.0, sleep_s))
            attempt += 1

def useMiniMax(content):
    return _chat(
        client=ASI_CLIENT,
        model="minimax/minimax-m2.5",
        content=content
    )

def useClaude(content):
    return _chat(
        client=ANTHROPIC_CLIENT,
        model="claude-opus-4-6",
        content=content
    )

_embedding_model = None

def initLocalEmbedding():
    model_name="intfloat/e5-large-v2"
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(model_name)
    return _embedding_model

def useLocalEmbedding(atom):
    global _embedding_model
    if _embedding_model is None:
        raise RuntimeError("Call initLocalEmbedding() first.")
    return _embedding_model.encode(
        atom,
        normalize_embeddings=True
    ).tolist()
