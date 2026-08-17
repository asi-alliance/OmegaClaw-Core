"""Thread-safe access to persistent history and vector memory."""

import threading
import uuid
import chromadb

from src.memory_layout import history_path, chroma_db_path
from src.logger import get_logger

logger = get_logger(__name__)

_write_lock = threading.Lock()

_RECORD_KIND = "user_memory"

_client: chromadb.ClientAPI | None = None
_collection = None

def _get_collection():
    """Lazy-initialise the ChromaDB client and collection."""
    global _client, _collection
    if _collection is None:
        db_path = str(chroma_db_path())
        logger.info(f"memory_gateway: opening ChromaDB at {db_path}")
        _client = chromadb.PersistentClient(path=db_path)
        _collection = _client.get_or_create_collection(
            name="memories",
            embedding_function=None,
        )
    return _collection

def append_history(text: str) -> None:
    """Append a history entry and its trailing newline, creating the file."""
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(text)
            f.write("\n")

def history_tail(max_chars: int) -> str:
    """Return the trailing character window of history, or an empty string."""
    path = history_path()
    if not path.exists():
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return f.read()[-max_chars:]

def remember(content: str, embedding: list[float], time: str) -> str:
    """Store a user memory record and return its ID."""
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
    """Return the k most similar records as [time, content]."""
    results = query_with_ids(query_embedding, k)
    return [[time, content] for _, time, content in results]

def query_with_ids(query_embedding: list[float], k: int) -> list[list]:
    """Return the k most similar records as [id, time, content]."""
    res = _get_collection().query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    ids   = res["ids"][0]
    docs  = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    return [
        [ids[i], metas[i].get("time") if metas[i] else None, docs[i]]
        for i in range(len(ids))
    ]
