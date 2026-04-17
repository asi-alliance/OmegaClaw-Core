import os
import re
import glob
import hashlib
import logging
import traceback

import chromadb
import openai

logger = logging.getLogger(__name__)

# --- Constants -----------------------------------------------------------

EMBEDDING_MODEL = "text-embedding-3-large"
COLLECTION_NAME = "memories"
TOP_K = 5
MIN_CHUNK_CHARS = 100
MAX_CHUNK_CHARS = 6000

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.environ.get(
    "CHROMA_DB_PATH",
    "/PeTTa/chroma_db" if os.path.isdir("/PeTTa/chroma_db") else
    os.path.join(_PROJECT_ROOT, "chroma_db")
)

# --- Lazy ChromaDB client ------------------------------------------------

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        os.makedirs(DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=DB_PATH)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=None,
        )
    return _collection


# --- Helpers -------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)


def _resolve_knowledge_dir():
    return os.path.join(_PROJECT_ROOT, "knowledge-priors")


def _file_hash(filepath):
    return hashlib.md5(open(filepath, "rb").read()).hexdigest()


def _decode_metta(s):
    return (s.replace("_quote_", '"')
             .replace("_newline_", "\n")
             .replace("_apostrophe_", "'"))


# --- Chunking ------------------------------------------------------------

def _chunk_markdown(text, filename):
    """Heading-aware markdown chunking with breadcrumb tracking."""
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        return [{"text": text.strip(), "breadcrumb": filename}]

    sections = []
    stack = {}  # level -> heading text

    for i, m in enumerate(matches):
        level = len(m.group(1))
        heading = m.group(2).strip()

        # Clear deeper headings from stack
        for lvl in list(stack):
            if lvl >= level:
                del stack[lvl]
        stack[level] = heading

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        breadcrumb = filename + " > " + " > ".join(
            stack[k] for k in sorted(stack)
        )
        sections.append({"text": body, "breadcrumb": breadcrumb, "heading": heading})

    # Skip Table of Contents section
    sections = [s for s in sections if "table of contents" not in s["heading"].lower()]

    # Merge small sections into next sibling
    merged = []
    carry = ""
    carry_bc = ""
    for s in sections:
        combined = (carry + "\n\n" + s["text"]).strip() if carry else s["text"]
        bc = carry_bc or s["breadcrumb"]
        if len(combined) < MIN_CHUNK_CHARS and s is not sections[-1]:
            carry = combined
            carry_bc = bc
        else:
            merged.append({"text": combined, "breadcrumb": bc})
            carry = ""
            carry_bc = ""
    if carry:
        if merged:
            merged[-1]["text"] += "\n\n" + carry
        else:
            merged.append({"text": carry, "breadcrumb": carry_bc})

    # Split large sections on paragraph boundaries
    final = []
    for s in merged:
        if len(s["text"]) <= MAX_CHUNK_CHARS:
            final.append(s)
            continue
        paragraphs = s["text"].split("\n\n")
        chunk_text = ""
        for p in paragraphs:
            if chunk_text and len(chunk_text) + len(p) > MAX_CHUNK_CHARS:
                final.append({"text": chunk_text.strip(), "breadcrumb": s["breadcrumb"]})
                chunk_text = p
            else:
                chunk_text = (chunk_text + "\n\n" + p).strip()
        if chunk_text.strip():
            final.append({"text": chunk_text.strip(), "breadcrumb": s["breadcrumb"]})

    return final


# --- Embedding -----------------------------------------------------------

def _embed_batch(texts):
    """Embed a list of texts via OpenAI. Returns list of float vectors."""
    client = openai.OpenAI()
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in resp.data]


# --- Hash sentinel docs --------------------------------------------------

def _hash_id(filename):
    return f"hash_{filename}"


def _get_stored_hash(collection, filename):
    try:
        result = collection.get(ids=[_hash_id(filename)], include=["metadatas"])
        if result["ids"]:
            return result["metadatas"][0].get("hash")
    except Exception:
        pass
    return None


def _store_hash(collection, filename, hash_val, embedding_dim):
    """Store a hash sentinel doc. Uses a zero-vector as dummy embedding."""
    collection.upsert(
        ids=[_hash_id(filename)],
        embeddings=[[0.0] * embedding_dim],
        documents=[f"hash sentinel for {filename}"],
        metadatas=[{"type": "hash", "hash": hash_val, "source": filename}],
    )


# --- Init & Query --------------------------------------------------------

_embedding_dim = None
_last_query = None
_last_result = None


def init_knowledge():
    """Chunk, embed, and store knowledge files. Skips unchanged files."""
    global _embedding_dim, _last_query, _last_result
    _last_query = None
    _last_result = None

    try:
        collection = _get_collection()
        knowledge_dir = _resolve_knowledge_dir()

        if not os.path.isdir(knowledge_dir):
            return f"Knowledge dir not found: {knowledge_dir}"

        md_files = sorted(glob.glob(os.path.join(knowledge_dir, "*.md")))
        if not md_files:
            return "No .md files found in knowledge-priors/"

        unchanged = 0
        reindexed = 0

        for filepath in md_files:
            filename = os.path.basename(filepath)
            current_hash = _file_hash(filepath)
            stored_hash = _get_stored_hash(collection, filename)

            if stored_hash == current_hash:
                print(f"  {filename}: unchanged (skipped)")
                unchanged += 1
                continue

            # Delete old chunks for this file
            try:
                old = collection.get(where={"source": filename}, include=[])
                if old["ids"]:
                    collection.delete(ids=old["ids"])
            except Exception:
                pass

            # Chunk and embed
            text = open(filepath, "r", encoding="utf-8").read()
            chunks = _chunk_markdown(text, filename)
            if not chunks:
                continue

            texts = [c["text"] for c in chunks]
            embeddings = _embed_batch(texts)
            if not embeddings:
                print(f"  {filename}: embedding failed, skipping")
                continue

            if _embedding_dim is None:
                _embedding_dim = len(embeddings[0])

            # Store chunks
            ids = [f"{filename}_chunk_{i}" for i in range(len(chunks))]
            metadatas = [
                {
                    "source": filename,
                    "breadcrumb": c["breadcrumb"],
                    "type": "chunk",
                    "time": "knowledge_prior"
                }
                for c in chunks
            ]
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )

            # Store hash sentinel
            _store_hash(collection, filename, current_hash, _embedding_dim)

            print(f"  {filename}: indexed {len(chunks)} chunks")
            reindexed += 1

        total = unchanged + reindexed
        return f"Knowledge: {total} files ({unchanged} unchanged, {reindexed} re-indexed)"

    except Exception as e:
        traceback.print_exc()
        return f"Knowledge init failed: {e}"


def query_knowledge(query_str, k=TOP_K):
    """Retrieve top-k relevant knowledge chunks for a query string."""
    global _last_query, _last_result

    if not query_str or query_str in ("", "(@ none)"):
        return ""

    if query_str == _last_query and _last_result is not None:
        return _last_result

    try:
        collection = _get_collection()
        if collection.count() == 0:
            return ""

        decoded = _decode_metta(query_str)
        query_vec = _embed_batch([decoded])[0]

        results = collection.query(
            query_embeddings=[query_vec],
            n_results=k,
            where={"type": "chunk"},
            include=["documents", "metadatas"],
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        parts = []
        for doc, meta in zip(docs, metas):
            bc = meta.get("breadcrumb", "")
            text = doc[:2000] if len(doc) > 2000 else doc
            parts.append(f"[{bc}] {text}")

        result = "\n---\n".join(parts)

        _last_query = query_str
        _last_result = result
        return result

    except Exception as e:
        logger.warning(f"Knowledge query failed: {e}")
        return ""
