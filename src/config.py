import os
import logging
import pathlib
import yaml

logger = logging.getLogger(__name__)

_REPO = pathlib.Path(__file__).parent.parent.resolve()
_CONFIG = {}
_COMMAND_LINE = {}
_CONFIG_FILE = {}

def init_config(command_line):
    """Initialize configuration: drop configuration cache and load
    configuration file"""
    global _CONFIG, _COMMAND_LINE, _CONFIG_FILE
    _CONFIG = {}
    _COMMAND_LINE = command_line_to_dict(command_line)
    _CONFIG_FILE = {}
    default_config_path = _REPO.joinpath("config", "config.yaml")
    config_path = config_get_by_key("config", default_config_path)
    try:
        logger.info(f"Loading configuration from {config_path}")
        with open(config_path, "r") as f:
            _CONFIG_FILE = yaml.safe_load(f)
        if not _CONFIG_FILE:
            _CONFIG_FILE = {}
    except:
        logger.exception(f"Could not load configuration file {config_path}")

def config_get_by_key(key, default=None):
    """Get configuration parameter from the list of sources: (1) command line
    parameters, (2) environment variable with OMEGACLAW_$key name, (3)
    configuration file, (4) use $default value."""
    global _CONFIG, _COMMAND_LINE, _CONFIG_FILE
    if key in _CONFIG:
        return _CONFIG.get(key)
    if key in _COMMAND_LINE:
        return _cache_config(key, _COMMAND_LINE.get(key), "command line")
    envkey = f"OMEGACLAW_{key}"
    if envkey in os.environ:
        return _cache_config(key, os.environ.get(envkey), "environment variable")
    if key in _CONFIG_FILE:
        return _cache_config(key, _CONFIG_FILE.get(key), "config file")
    return _cache_config(key, default, "defaults")

def _cache_config(key, value, source):
    global _CONFIG
    _CONFIG[key] = value
    logger.info(f"Configuration item resolved using {source}: {key}={value}")
    return value

def command_line_to_dict(list):
    """Converts list of <key>=<value> pairs into Python dictionary. If
    parameter doesn't include "=" it is added as a boolean value
    <parameter>=True"""
    dict = {}
    for arg in list:
        kv = arg.split("=", 1)
        if len(kv) == 2:
            dict[kv[0]] = kv[1]
        else:
            dict[kv[0]] = True
    return dict
