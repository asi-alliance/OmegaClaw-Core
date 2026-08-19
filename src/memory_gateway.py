"""Thread-safe access to persistent history and vector memory."""

import os
import threading
import uuid
from pathlib import Path

import chromadb

from src.logger import get_logger

logger = get_logger(__name__)

_write_lock = threading.Lock()
_RECORD_KIND = "user_memory"
_client: chromadb.ClientAPI | None = None
_collection = None
_REPO_ROOT = Path(__file__).parent.parent.resolve()

def memory_dir_path() -> Path:
    return Path(os.environ.get("MEMORY_DIR", _REPO_ROOT / "memory")).resolve()

def history_path() -> Path:
    return memory_dir_path() / "history.metta"

def chroma_db_path() -> Path:
    return memory_dir_path() / "chroma_db"

def _get_collection():
    global _client, _collection
    if _collection is None:
        db_path = str(chroma_db_path())
        logger.info(f"memory_gateway: opening ChromaDB at {db_path}")
        _client = chromadb.PersistentClient(path=db_path)
        _collection = _client.get_or_create_collection(
            name="memories", embedding_function=None
        )
    return _collection

def append_history(text: str) -> None:
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        with path.open("a", encoding="utf-8") as history:
            history.write(text)
            history.write("\n")

def history_tail(max_chars: int) -> str:
    path = history_path()
    if not path.exists():
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as history:
        return history.read()[-max_chars:]

def remember(content: str, embedding: list[float], time: str) -> str:
    item_id = str(uuid.uuid4())
    with _write_lock:
        _get_collection().add(
            ids=[item_id],
            documents=[content],
            embeddings=[embedding],
            metadatas=[{"time": time, "record_kind": _RECORD_KIND}],
        )
    logger.debug(f"memory_gateway: remembered record {item_id}")
    return item_id

def query(query_embedding: list[float], k: int) -> list[list]:
    return [[time, content] for _, time, content in query_with_ids(query_embedding, k)]

def query_with_ids(query_embedding: list[float], k: int) -> list[list]:
    result = _get_collection().query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    ids = result["ids"][0]
    documents = result.get("documents", [[]])[0]
    metadata = result.get("metadatas", [[]])[0]
    return [
        [ids[index], metadata[index].get("time") if metadata[index] else None, documents[index]]
        for index in range(len(ids))
    ]
