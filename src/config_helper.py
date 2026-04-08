import yaml
import os
import logging

_config_cache = None
_config_mtime = 0
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "memory", "telegram_profile.yaml")

def _load_config():
    global _config_cache, _config_mtime
    if not os.path.exists(CONFIG_PATH):
        return {}
    
    mtime = os.path.getmtime(CONFIG_PATH)
    if _config_cache is None or mtime > _config_mtime:
        try:
            with open(CONFIG_PATH, "r") as f:
                _config_cache = yaml.safe_load(f)
            _config_mtime = mtime
        except Exception as e:
            logging.error(f"Error loading {CONFIG_PATH}: {e}")
            return _config_cache or {}
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

def is_category_blocked(text):
    config = _load_config()
    blocked = config.get("ethics_pass", {}).get("blocked_categories", [])
    text = text.lower()
    for cat in blocked:
        if cat.lower() in text:
            return True
    return False

def is_memory_forbidden(text):
    config = _load_config()
    forbidden = config.get("internal_learning", {}).get("durable_memory", {}).get("categories_forbidden", [])
    text = text.lower()
    for cat in forbidden:
        if cat.lower() in text:
            return True
    return False

def get_allowed_skills():
    config = _load_config()
    # If in telegram mode, filter allowed skills
    # This can be used to construct the getSkills return in MeTTa
    return config.get("internal_learning", {}).get("learned_skills", {}).get("classes_allowed", [])
