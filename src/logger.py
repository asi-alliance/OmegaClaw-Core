import logging
import logging.config
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_CONFIG = REPO_ROOT / "config" / "logging.conf"

DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _normalize_msg(msg: Any) -> str:
    if isinstance(msg, (list, tuple)):
        return " ".join(map(str, msg))
    return str(msg)


def _is_empty_config_path(config_path: Any) -> bool:
    if config_path is None:
        return True

    text = str(config_path).strip()
    return text in {"", "()", "(empty)", "empty", "None"}


def setup_logging(config_path: str | None = None) -> None:
    """
    Configure Python logging from an INI logging config file.

    If config_path is empty, use config/logging.conf.
    If the selected config file does not exist, fall back to basic stderr logging.
    """

    if _is_empty_config_path(config_path):
        path = DEFAULT_LOG_CONFIG
    else:
        path = Path(str(config_path))
        if not path.exists():
            path = DEFAULT_LOG_CONFIG

    if path.exists():
        logging.config.fileConfig(
            path,
            disable_existing_loggers=False,
        )
        return

    logging.basicConfig(
        level=logging.INFO,
        format=DEFAULT_LOG_FORMAT,
        datefmt=DEFAULT_DATE_FORMAT,
    )

    logging.getLogger(__name__).warning(
        "Logging config file %s not found; using basic logging fallback.",
        path,
    )

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

def log_debug(msg: str, module: str = "metta") -> None:
    logging.getLogger(module).debug(_normalize_msg(msg))


def log_info(msg: str, module: str = "metta") -> None:
    logging.getLogger(module).info(_normalize_msg(msg))


def log_warning(msg: str, module: str = "metta") -> None:
    logging.getLogger(module).warning(_normalize_msg(msg))


def log_error(msg: str, module: str = "metta") -> None:
    logging.getLogger(module).error(_normalize_msg(msg))


def log_exception(msg: str, module: str = "metta") -> None:
    logging.getLogger(module).exception(_normalize_msg(msg))