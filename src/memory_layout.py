import os
import pathlib

_REPO_ROOT = pathlib.Path(__file__).parent.parent.resolve()

def memory_dir_path() -> pathlib.Path:
    """Return MEMORY_DIR or the repository's memory directory."""
    memory_dir = os.environ.get("MEMORY_DIR")
    if memory_dir:
        return pathlib.Path(memory_dir).resolve()
    return _REPO_ROOT / "memory"

def history_path() -> pathlib.Path:
    """Return the history file path."""
    return memory_dir_path() / "history.metta"

def chroma_db_path() -> pathlib.Path:
    """Return the ChromaDB directory path."""
    return memory_dir_path() / "chroma_db"
