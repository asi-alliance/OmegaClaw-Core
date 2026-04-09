import yaml
import os
import logging
import openai

_config_cache = None
_config_mtime = 0
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "memory", "telegram_profile.yaml")

def _load_config():
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
    config = _load_config()
    return config.get("disabled_tools", {}).get(tool_name, False)

def get_blocked_ethics_categories():
    config = _load_config()
    categories = config.get("ethics_pass", {}).get("blocked_categories", [])
    return categories

def get_forbidden_memory_categories():
    config = _load_config()
    return config.get("internal_learning", {}).get("durable_memory", {}).get("categories_forbidden", [])

def _llm_classify(text, categories):
    if not categories or not text.strip():
        return False
        
    prompt = (
        f"Does the following expression fall into any of these strictly forbidden categories?\n\n"
        f"Forbidden Categories: {', '.join(categories)}\n\n"
        f"Expression: '{text}'\n\n"
        f"Answer ONLY 'YES' if it violates a category, or 'NO' if it is safe."
    )
    
    try:
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.0
        )
        answer = response.choices[0].message.content.strip().upper()
        return "YES" in answer
    except Exception as e:
        logging.error(f"LLM Ethics Classification failed (Failing closed): {e}")
        return True


def is_category_blocked(text):
    config = _load_config()
    blocked = config.get("ethics_pass", {}).get("blocked_categories", [])
    return _llm_classify(text, blocked)

def is_memory_forbidden(text):
    config = _load_config()
    forbidden = config.get("internal_learning", {}).get("durable_memory", {}).get("categories_forbidden", [])
    text = text.lower()
    return _llm_classify(text, forbidden)

def get_allowed_skills():
    config = _load_config()
    return config.get("internal_learning", {}).get("learned_skills", {}).get("classes_allowed", [])
