import yaml
import os
import json
import logging
import re
import openai
import asyncio

_config_cache = None
_config_mtime = 0
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "telegram_profile.yaml")

_openai_client = None


def _get_openai_client():
    """Build the moderation client lazily so importing this module (which
    happens whenever the plugin loads, independent of which channel is
    active) does not require OPENAI_API_KEY to be set. Isolated so tests
    can stub it."""
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _openai_client

def _load_config():
    """Loads and caches the telegram profile YAML configuration."""
    global _config_cache, _config_mtime

    if _config_cache is not None:
        return _config_cache

    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Critical Error: Telegram profile not found at {CONFIG_PATH}")

    try:
        with open(CONFIG_PATH, "r") as f:
            _config_cache = yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Error loading {CONFIG_PATH}: {e}")
        _config_cache = {}

    return _config_cache

def is_tool_disabled(tool_name):
    """Checks if a specified tool is disabled in the configuration."""
    config = _load_config()
    return config.get("disabled_tools", {}).get(tool_name, False)

def get_blocked_ethics_categories():
    """Retrieves the list of blocked ethics categories."""
    config = _load_config()
    categories = config.get("ethics_pass", {}).get("blocked_categories", [])
    return categories

def get_forbidden_memory_categories():
    """Retrieves the list of forbidden categories for memory storage."""
    config = _load_config()
    return config.get("internal_learning", {}).get("durable_memory", {}).get("categories_forbidden", [])

async def use_model(text, categories):
    """Uses an LLM to classify if text violates the provided categories."""
    config = _load_config()
    model_config = config.get("classification_model", {})
    model_name = model_config.get("name", "gpt-4o-mini")
    max_tokens = model_config.get("max_tokens", 10)
    temperature = model_config.get("temperature", 0.0)

    try:
        prompt = f"""
            You are a context-aware safety classifier.

            Forbidden categories:
            {categories}

            Classify the expression. Do NOT flag:
            - jokes
            - idioms
            - metaphors
            - sarcasm
            - figures of speech
            - fictional/hypothetical non-actionable language

            Flag only if the text clearly and literally expresses, requests, encourages,
            or provides actionable content in a forbidden category.

            Return JSON ONLY:
            {{
            "violates": true/false,
            "confidence": 0.0-1.0,
            "reason": "short reason",
            "is_joke_or_figure_of_speech": true/false
            }}

            Expression: {text!r}
            """
        client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = await client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=120,
        response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)

        return (
            data["violates"] is True
            and data["confidence"] >= 0.80
            and not data.get("is_joke_or_figure_of_speech", False)
        )

    except Exception as e:
        logging.error(f"OpenAI classification error: {e}")
        return False

async def _llm_classify(text, categories, memCheck=False):
    """Classifies text using OpenAI's Moderation API or falls back to standard LLM classification."""
    if not categories or not text.strip():
        return False

    if memCheck:
        return await use_model(text, categories)

    try:
        response = await _get_openai_client().moderations.create(input=text)
        result = response.results[0]

        thresholds = {
            "violence": 0.85,
            "harassment": 0.85,
            "hate": 0.85,
            "self-harm": 0.70,
            "sexual/minors": 0.30,
        }

        for category, threshold in thresholds.items():
            if result.category_scores.model_dump().get(category, 0) >= threshold:
                return True

        return False

    except Exception as e:
        logging.error(f"OpenAI moderation error: {e}")
        logging.info(f"Opting to model usage for classification...")
        return await use_model(text, categories)

async def is_category_blocked(text):
    """Checks if the text violates any blocked ethics categories."""
    config = _load_config()
    blocked = config.get("ethics_pass", {}).get("blocked_categories", [])
    return await _llm_classify(text, blocked)


async def is_memory_forbidden(text):
    """Checks if the text contains topics forbidden from long-term memory."""
    config = _load_config()
    forbidden = config.get("internal_learning", {}).get("durable_memory", {}).get("categories_forbidden", [])
    text = text.lower()
    return await _llm_classify(text, forbidden)

def get_spam_protection_config():
    """Retrieves spam protection thresholds from the configuration."""
    config = _load_config()
    spam_config = config.get("spam_protection", {})
    return {
        "time_window": spam_config.get("time_window", 10),
        "message_limit": spam_config.get("message_limit", 5),
        "cooldown_duration": spam_config.get("cooldown_duration", 120),
        "admin_alert_threshold": spam_config.get("admin_alert_threshold", 3)
    }
