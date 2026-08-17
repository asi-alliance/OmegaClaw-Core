"""Export and import persistent user memory."""

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import chromadb

import src.memory_gateway as gateway
from src.memory_layout import chroma_db_path, history_path, memory_dir_path
from src.logger import get_logger
from src.config import config_get_by_key

logger = get_logger(__name__)

TRANSFER_DIR           = Path("/memory-transfer")
ARCHIVE_FORMAT_VERSION = 1

_ALLOWLIST = frozenset([
    "manifest.json",
    "history/history.metta",
    "vector/collections.json",
    "vector/records.jsonl",
])

_COMPONENT_FILES = {
    "history": {"history/history.metta"},
    "ltm": {"vector/collections.json", "vector/records.jsonl"},
}

_MAX_COMPRESSED_BYTES = 500 * 1024 * 1024        # 500 MB
_MAX_EXTRACTED_BYTES  = 2   * 1024 * 1024 * 1024 # 2 GB

_TX_MARKER_NAME = ".import_in_progress"
_RECEIPT_DIR_NAME = ".memory_import_receipts"
_ROLLBACK_STATE_NAME = "state.json"

_REEMBED_BATCH = 64
_VECTOR_BATCH = 500

def is_export_enabled() -> bool:
    """Return whether an administrator enabled memory export."""
    env_val = os.environ.get("OMEGACLAW_memoryExportEnabled")
    if env_val is not None:
        return env_val.strip().lower() == "true"

    value = config_get_by_key("memoryExportEnabled", False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return value is True

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _archive_name() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"omegaclaw-memory-{timestamp}.tar.gz"

def _embedding_profile() -> dict:
    """Return the active embedding profile used to assess archive compatibility."""
    provider = os.environ.get("EMBEDDING_PROVIDER", "Local")
    default_model = "text-embedding-3-large" if provider == "OpenAI" else "intfloat/e5-large-v2"
    return {
        "provider": provider,
        "model": os.environ.get("SENTENCE_TRANSFORMERS_MODEL", default_model),
    }

def _reembed_records(records: list[dict], manifest: dict,
                     target_dimension: int | None) -> None:
    """Regenerate embeddings in bounded batches when archive and runtime differ."""
    source = manifest.get("embedding_info", {})
    active = _embedding_profile()
    source_dimension = source.get("vector_dimension")
    embeddings_present = all(
        record.get("embedding") and len(record["embedding"]) == source_dimension
        for record in records
    )
    if (source.get("provider") == active["provider"] and
            source.get("model") == active["model"] and embeddings_present and
            target_dimension in (None, source_dimension)):
        return

    logger.warning("memory_transfer: embedding profile mismatch — re-embedding in batches")
    from src.rag import local_embed_batch, openai_embed_batch

    embed_fn = openai_embed_batch if active["provider"] == "OpenAI" else local_embed_batch
    for i in range(0, len(records), _REEMBED_BATCH):
        batch = records[i : i + _REEMBED_BATCH]
        embeddings = embed_fn([record["document"] for record in batch])
        for record, embedding in zip(batch, embeddings):
            record["embedding"] = embedding

def _normalise_metadata(metadata: object) -> dict:
    """Convert archive metadata into ChromaDB's scalar-only metadata format."""
    if not isinstance(metadata, dict):
        raise ValueError("Archive record metadata must be an object")

    normalised = {}
    for key, value in metadata.items():
        if not isinstance(key, str) or not key:
            raise ValueError("Archive metadata keys must be non-empty strings")
        if isinstance(value, (str, int, float, bool)):
            normalised[key] = value
        elif value is None:
            normalised[key] = "null"
        elif isinstance(value, (list, dict)):
            normalised[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            normalised[key] = str(value)
    return normalised

def _normalise_record(record: object, line_number: int) -> dict:
    """Validate one archive JSONL record and return a Chroma-ready mapping."""
    if not isinstance(record, dict):
        raise ValueError(f"Archive record on line {line_number} must be an object")

    record_id = record.get("id")
    document = record.get("document")
    embedding = record.get("embedding", [])
    if not isinstance(record_id, str) or not record_id:
        raise ValueError(f"Archive record on line {line_number} has an invalid id")
    if not isinstance(document, str):
        raise ValueError(f"Archive record {record_id!r} has a non-string document")
    if not isinstance(embedding, list) or not all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in embedding):
        raise ValueError(f"Archive record {record_id!r} has an invalid embedding")

    return {
        "id": record_id,
        "document": document,
        "embedding": embedding,
        "metadata": _normalise_metadata(record.get("metadata", {})),
    }

def _record_batches(records_path: Path):
    """Yield validated archive records in bounded JSONL batches."""
    batch = []
    with records_path.open("r", encoding="utf-8") as records_file:
        for line_number, line in enumerate(records_file, 1):
            if not line.strip():
                continue
            try:
                raw_record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSONL record on line {line_number}: {exc.msg}"
                ) from exc
            batch.append(_normalise_record(raw_record, line_number))
            if len(batch) == _VECTOR_BATCH:
                yield batch
                batch = []
    if batch:
        yield batch

def _validate_manifest(manifest: object) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("Archive manifest must be an object")
    if type(manifest.get("format_version")) is not int:
        raise ValueError("Archive manifest has invalid format_version")
    for field in ("omegaclaw_version", "chromadb_version", "created_at"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise ValueError(f"Archive manifest has invalid {field}")
    try:
        created_at = datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Archive manifest has invalid created_at") from exc
    if created_at.tzinfo is None or created_at.utcoffset() != timezone.utc.utcoffset(created_at):
        raise ValueError("Archive manifest created_at must be UTC")
    components = manifest.get("components")
    if (not isinstance(components, list)
            or any(component not in ("history", "ltm") for component in components)
            or len(components) != len(set(components))):
        raise ValueError("Archive manifest has invalid components")
    if not isinstance(manifest.get("record_count"), int) or isinstance(
            manifest["record_count"], bool) or manifest["record_count"] < 0:
        raise ValueError("Archive manifest has invalid record_count")
    if not isinstance(manifest.get("history_bytes"), int) or isinstance(
            manifest["history_bytes"], bool) or manifest["history_bytes"] < 0:
        raise ValueError("Archive manifest has invalid history_bytes")
    if "ltm" not in components and manifest["record_count"]:
        raise ValueError("Archive manifest has records without the ltm component")
    if "history" not in components and manifest["history_bytes"]:
        raise ValueError("Archive manifest has history bytes without the history component")
    checksums = manifest.get("checksums")
    if not isinstance(checksums, dict) or not all(
            isinstance(name, str) and isinstance(value, str)
            and len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())
            for name, value in checksums.items()):
        raise ValueError("Archive manifest has invalid checksums")
    expected_files = set().union(*(_COMPONENT_FILES[component] for component in components))
    if set(checksums) != expected_files:
        raise ValueError("Archive manifest checksums do not match its components")
    if "ltm" in components:
        _validate_embedding_info(manifest)
    elif manifest.get("embedding_info") != {}:
        raise ValueError("Archive manifest has embedding_info without the ltm component")
    return manifest

def _validate_embedding_info(manifest: dict) -> None:
    embedding_info = manifest.get("embedding_info")
    if (not isinstance(embedding_info, dict)
            or not isinstance(embedding_info.get("provider"), str)
            or not isinstance(embedding_info.get("model"), str)
            or not isinstance(embedding_info.get("vector_dimension"), int)
            or isinstance(embedding_info["vector_dimension"], bool)
            or embedding_info["vector_dimension"] < 0):
        raise ValueError("Archive manifest has invalid embedding_info")

def _validate_records(records_path: Path, manifest: dict) -> None:
    expected_count = manifest["record_count"]
    dimension = manifest["embedding_info"]["vector_dimension"]
    count = 0
    for records in _record_batches(records_path):
        for record in records:
            if record["embedding"] and len(record["embedding"]) != dimension:
                raise ValueError("Archive record embedding dimension does not match manifest")
            count += 1
    if count != expected_count:
        raise ValueError("Archive record count does not match manifest")

def _validate_extracted_archive(staging: Path, manifest: dict) -> None:
    """Validate extracted content before import can modify live memory."""
    for member_name, expected in manifest["checksums"].items():
        actual = _sha256(staging / member_name)
        if actual != expected:
            raise ValueError(f"Checksum mismatch for {member_name!r}")

    components = manifest["components"]
    if "history" in components:
        history = staging / "history" / "history.metta"
        if history.stat().st_size != manifest["history_bytes"]:
            raise ValueError("Archive history size does not match manifest")
    if "ltm" in components:
        collections = json.loads(
            (staging / "vector" / "collections.json").read_text(encoding="utf-8")
        )
        if (not isinstance(collections, dict)
                or collections.get("name") != "memories"
                or collections.get("embedding_info") != manifest["embedding_info"]):
            raise ValueError("Archive collections metadata does not match manifest")
        _validate_records(staging / "vector" / "records.jsonl", manifest)

def _collection_dimension(collection) -> int | None:
    result = collection.get(limit=1, include=["embeddings"])
    embeddings = result.get("embeddings")
    return len(embeddings[0]) if embeddings is not None and len(embeddings) else None

def _staging_dir() -> Path:
    """Return same-filesystem staging for atomic archive publication."""
    staging = TRANSFER_DIR / ".staging"
    staging.mkdir(parents=True, exist_ok=True)
    return staging

def _is_user_memory_record(metadata: object) -> bool:
    """Return whether a collection record belongs to portable user memory."""
    if not isinstance(metadata, dict):
        return False
    return (
        metadata.get("record_kind") == gateway._RECORD_KIND
        or ("record_kind" not in metadata and "type" not in metadata)
    )

def _export_history(staging: Path) -> int:
    """Copy history.metta into staging. Returns byte size."""
    src = history_path()
    dst = staging / "history" / "history.metta"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.copy2(src, dst)
        return dst.stat().st_size
    dst.touch()
    return 0

def _export_vectors(staging: Path) -> tuple[int, dict]:
    """Export marked and legacy user records into staging."""
    vector_dir = staging / "vector"
    vector_dir.mkdir(parents=True, exist_ok=True)
    records_path = vector_dir / "records.jsonl"
    col = gateway._get_collection()
    record_count = 0
    dimension = 0

    with records_path.open("w", encoding="utf-8") as records_file:
        for offset in range(0, col.count(), _VECTOR_BATCH):
            result = col.get(
                limit=_VECTOR_BATCH,
                offset=offset,
                include=["documents", "metadatas", "embeddings"],
            )
            ids = result.get("ids", [])
            docs = result.get("documents") or []
            metas = result.get("metadatas") or []
            raw_embeddings = result.get("embeddings")
            embeddings = list(raw_embeddings) if raw_embeddings is not None else []
            for index, record_id in enumerate(ids):
                metadata = metas[index] if index < len(metas) else {}
                if not _is_user_memory_record(metadata):
                    continue
                embedding = embeddings[index] if index < len(embeddings) else []
                embedding = list(embedding) if hasattr(embedding, "__iter__") else embedding
                if not dimension and embedding:
                    dimension = len(embedding)
                records_file.write(json.dumps({
                    "id": record_id,
                    "document": docs[index] if index < len(docs) else "",
                    "metadata": _normalise_metadata(metadata),
                    "embedding": embedding,
                }, ensure_ascii=False) + "\n")
                record_count += 1

    active_profile = _embedding_profile()
    embedding_info = {
        "provider":         active_profile["provider"],
        "model":            active_profile["model"],
        "vector_dimension": dimension,
    }

    (vector_dir / "collections.json").write_text(
        json.dumps({"name": "memories", "embedding_info": embedding_info}, indent=2),
        encoding="utf-8",
    )

    return record_count, embedding_info

def _build_manifest(staging: Path, components: list[str],
                    record_count: int, embedding_info: dict) -> None:
    """Write manifest.json into staging."""
    from src.helper import omegaclaw_version

    checksums: dict[str, str] = {}
    for member in _ALLOWLIST:
        p = staging / member
        if p.exists():
            checksums[member] = _sha256(p)

    manifest = {
        "format_version":    ARCHIVE_FORMAT_VERSION,
        "omegaclaw_version": omegaclaw_version(),
        "chromadb_version":  chromadb.__version__,
        "components":        components,
        "embedding_info":    embedding_info,
        "record_count":      record_count,
        "history_bytes":     (staging / "history" / "history.metta").stat().st_size
                             if (staging / "history" / "history.metta").exists() else 0,
        "created_at":        _utc_now(),
        "checksums":         checksums,
    }
    (staging / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

def _pack_archive(staging: Path, dest: Path) -> None:
    """Pack staging directory into a .tar.gz at dest."""
    with tarfile.open(dest, "w:gz") as tar:
        for member in sorted(_ALLOWLIST):
            p = staging / member
            if p.exists():
                tar.add(p, arcname=member)

def start_export_job(
    component: str, on_complete: Callable[[str, dict], None] | None = None
) -> str:
    """Start an asynchronous export and return its job ID."""
    if component not in ("history", "ltm", "both"):
        raise ValueError(f"Invalid component: {component!r}. Use history, ltm, or both.")

    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {"status": "running"}
    threading.Thread(
        target=_run_export, args=(job_id, component, on_complete), daemon=True
    ).start()
    logger.info(f"memory_transfer: export job {job_id} started (component={component})")
    return job_id

def _run_export(
    job_id: str, component: str, on_complete: Callable[[str, dict], None] | None
) -> None:
    try:
        result = export(component)
        status = {"status": "done", **result}
    except Exception as exc:
        logger.exception(f"memory_transfer: export job {job_id} failed: {exc}")
        status = {"status": "failed", "error": str(exc)}

    with _jobs_lock:
        _jobs[job_id] = status

    if on_complete is not None:
        try:
            on_complete(job_id, status.copy())
        except Exception as exc:
            logger.exception(
                f"memory_transfer: completion callback for export job {job_id} failed: {exc}"
            )

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

def get_export_status(job_id: str) -> dict:
    with _jobs_lock:
        return _jobs.get(job_id, {"status": "unknown"}).copy()

def export(component: str) -> dict:
    """Export selected memory components and publish an archive atomically."""
    include_history = component in ("history", "both")
    include_vectors = component in ("ltm", "both")

    archive_name = _archive_name()
    work_dir     = _staging_dir() / archive_name
    work_dir.mkdir(parents=True, exist_ok=True)
    staging      = work_dir / "staging"
    staging.mkdir()
    # Landlock permits atomic rename within a directory, but can reject a
    # rename between .staging and its parent as a cross-directory operation.
    tmp_archive  = TRANSFER_DIR / f".{archive_name}.tmp"

    try:
        record_count   = 0
        embedding_info: dict = {}
        components: list[str] = []

        with gateway._write_lock:
            if include_history:
                _export_history(staging)
                components.append("history")
            if include_vectors:
                record_count, embedding_info = _export_vectors(staging)
                components.append("ltm")

        _build_manifest(staging, components, record_count, embedding_info)
        _pack_archive(staging, tmp_archive)
        _verify_archive(tmp_archive)

        TRANSFER_DIR.mkdir(parents=True, exist_ok=True)
        dest = TRANSFER_DIR / archive_name
        os.replace(tmp_archive, dest)

    finally:
        tmp_archive.unlink(missing_ok=True)
        shutil.rmtree(work_dir, ignore_errors=True)

    size     = dest.stat().st_size
    checksum = _sha256(dest)
    logger.info(f"memory_transfer: exported {dest} ({size} bytes, sha256={checksum})")
    return {
        "filename":     archive_name,
        "size":         size,
        "checksum":     checksum,
        "record_count": record_count,
        "components":   components,
    }

def _verify_archive(path: Path, extract_to: Path | None = None) -> dict:
    """Validate archive members and extract once for checksum verification."""
    if path.stat().st_size > _MAX_COMPRESSED_BYTES:
        raise ValueError(f"Archive too large: {path.stat().st_size} bytes")

    seen_names: set[str] = set()
    total_extracted = 0

    with tarfile.open(path, "r:gz") as tar:
        for member in tar.getmembers():
            name = member.name
            if name not in _ALLOWLIST:
                raise ValueError(f"Unexpected archive member: {name!r}")
            if name in seen_names:
                raise ValueError(f"Duplicate archive member: {name!r}")
            seen_names.add(name)
            if not member.isfile():
                raise ValueError(f"Non-regular member: {name!r}")
            if ".." in Path(name).parts or Path(name).is_absolute():
                raise ValueError(f"Path traversal in member: {name!r}")
            total_extracted += member.size
            if total_extracted > _MAX_EXTRACTED_BYTES:
                raise ValueError("Archive extracted size exceeds limit")

        manifest_file = tar.extractfile("manifest.json")
        if manifest_file is None:
            raise ValueError("manifest.json missing from archive")
        manifest = _validate_manifest(json.loads(manifest_file.read()))

        if manifest["format_version"] != ARCHIVE_FORMAT_VERSION:
            raise ValueError(f"Unsupported format_version: {manifest.get('format_version')}")

        components = manifest.get("components", [])
        expected_members = {"manifest.json"}
        expected_members.update(*(_COMPONENT_FILES[component] for component in components))
        if seen_names != expected_members:
            raise ValueError("Archive members do not match manifest components")

        if extract_to is not None:
            extract_to.mkdir(parents=True, exist_ok=True)
            _safe_extract(tar, extract_to)
            _validate_extracted_archive(extract_to, manifest)
        else:
            with tempfile.TemporaryDirectory() as tmp:
                staging = Path(tmp)
                _safe_extract(tar, staging)
                _validate_extracted_archive(staging, manifest)

    return manifest

def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract only regular, allowlisted archive members without tarfile filters.

    Python 3.11 does not support TarFile.extractall(filter=...), so extraction
    is performed explicitly after validating each member's fixed archive path.
    """
    base = dest.resolve()
    for member in tar.getmembers():
        name = member.name
        if name not in _ALLOWLIST or not member.isfile():
            raise ValueError(f"Unsafe archive member: {name!r}")
        target = (base / name).resolve()
        if base not in target.parents:
            raise ValueError(f"Path traversal in member: {name!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        source = tar.extractfile(member)
        if source is None:
            raise ValueError(f"Could not read archive member: {name!r}")
        with source, target.open("wb") as output:
            shutil.copyfileobj(source, output)

def _parse_component_flags(args: argparse.Namespace) -> tuple[bool, bool]:
    no_history = getattr(args, "no_history", False)
    no_vector  = getattr(args, "no_vector", False) or getattr(args, "only_history", False)
    if no_history and no_vector:
        raise ValueError("--no-history and --no-vector together import nothing. Aborting.")
    return not no_history, not no_vector

def _tx_marker(memory_base: Path) -> Path:
    return memory_base / _TX_MARKER_NAME

def _receipt_path(memory_base: Path, digest: str, mode: str,
                  include_history: bool, include_vectors: bool) -> Path:
    components = "-".join(component for component, included in (
        ("history", include_history), ("ltm", include_vectors)
    ) if included)
    return memory_base / _RECEIPT_DIR_NAME / f"{digest}-{mode}-{components}.json"

def _write_receipt(path: Path, digest: str, mode: str,
                   include_history: bool, include_vectors: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "archive_sha256": digest,
        "mode": mode,
        "include_history": include_history,
        "include_vectors": include_vectors,
        "imported_at": _utc_now(),
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)

def _marker_has_receipt(marker: Path, memory_base: Path) -> bool:
    try:
        receipt_name = json.loads(marker.read_text(encoding="utf-8")).get("receipt")
    except (json.JSONDecodeError, OSError):
        return False
    return (
        isinstance(receipt_name, str)
        and Path(receipt_name).name == receipt_name
        and (memory_base / _RECEIPT_DIR_NAME / receipt_name).is_file()
    )

def _append_state(include_history: bool, include_vectors: bool) -> dict:
    history = history_path()
    return {
        "history": {
            "existed": history.exists(),
            "size": history.stat().st_size if history.exists() else 0,
        } if include_history else None,
        "import_id": uuid.uuid4().hex if include_vectors else None,
    }

def _rollback_append(state: dict) -> None:
    history = state.get("history")
    if isinstance(history, dict):
        path = history_path()
        if history.get("existed"):
            if path.exists():
                with path.open("rb+") as output:
                    output.truncate(history["size"])
        else:
            path.unlink(missing_ok=True)

    import_id = state.get("import_id")
    if isinstance(import_id, str):
        col = gateway._get_collection()
        imported = col.get(where={"import_id": import_id}, include=[])
        if imported["ids"]:
            col.delete(ids=imported["ids"])

def recover(memory_base: Path | None = None) -> None:
    """Restore an interrupted import or fail when its rollback is unavailable."""
    base     = memory_base or memory_dir_path()
    marker   = _tx_marker(base)
    rollback = base / ".import_rollback"

    if not marker.exists():
        return

    if _marker_has_receipt(marker, base):
        marker.unlink(missing_ok=True)
        shutil.rmtree(rollback, ignore_errors=True)
        logger.info("memory_transfer: completed import transaction recovered")
        return

    try:
        transaction = json.loads(marker.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        transaction = {}
    append = transaction.get("append") if isinstance(transaction, dict) else None
    if isinstance(append, dict):
        logger.warning("memory_transfer: unfinished append import detected — removing partial import")
        _rollback_append(append)
        marker.unlink(missing_ok=True)
        logger.info("memory_transfer: append transaction recovery complete")
        return

    logger.warning("memory_transfer: unfinished import transaction detected — restoring rollback")

    if not rollback.exists():
        raise RuntimeError(
            "Import transaction marker found but no rollback copy exists. "
            "Cannot recover safely — operator intervention required."
        )

    _restore_rollback(rollback)
    marker.unlink(missing_ok=True)
    shutil.rmtree(rollback, ignore_errors=True)
    logger.info("memory_transfer: transaction recovery complete")

def _restore_rollback(rollback: Path) -> None:
    hist_rb   = rollback / "history.metta"
    chroma_rb = rollback / "chroma_db"
    state_path = rollback / _ROLLBACK_STATE_NAME
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        state = {}

    if state.get("history") is False:
        history_path().unlink(missing_ok=True)
    elif hist_rb.exists():
        history_path().parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(hist_rb, history_path())

    live_chroma = chroma_db_path()
    if state.get("vectors") is False:
        shutil.rmtree(live_chroma, ignore_errors=True)
    elif chroma_rb.exists():
        if live_chroma.exists():
            shutil.rmtree(live_chroma)
        shutil.copytree(chroma_rb, live_chroma)
    if "vectors" in state:
        gateway._client = None
        gateway._collection = None

def import_archive(archive_path: Path, mode: str = "overwrite",
                   include_history: bool = True,
                   include_vectors: bool = True) -> None:
    """Validate and restore a memory archive before the agent loop starts."""
    if mode not in ("overwrite", "append"):
        raise ValueError(f"Invalid mode: {mode!r}. Use overwrite or append.")
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    logger.info(f"memory_transfer: importing {archive_path} (mode={mode})")

    base    = memory_dir_path()
    digest  = _sha256(archive_path)
    receipt = _receipt_path(base, digest, mode, include_history, include_vectors)
    if receipt.exists():
        logger.info("memory_transfer: archive already imported; skipping")
        return
    staging = base / ".import_staging"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        manifest = _verify_archive(archive_path, staging)
        import_history = (
            include_history
            and "history" in manifest.get("components", [])
            and (staging / "history" / "history.metta").is_file()
        )
        import_vectors = (
            include_vectors
            and "ltm" in manifest.get("components", [])
            and (staging / "vector" / "records.jsonl").is_file()
        )
        if mode == "overwrite":
            _import_overwrite(
                staging, manifest, import_history, import_vectors, receipt, digest
            )
        else:
            _import_append(
                staging, manifest, import_history, import_vectors, receipt, digest
            )
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    logger.info("memory_transfer: import complete")

def _import_overwrite(staging: Path, manifest: dict,
                      include_history: bool, include_vectors: bool,
                      receipt: Path, digest: str) -> None:
    """Overwrite live memory with rollback and crash-recovery protection."""
    base     = memory_dir_path()
    rollback = base / ".import_rollback"
    marker   = _tx_marker(base)

    shutil.rmtree(rollback, ignore_errors=True)
    rollback.mkdir(parents=True)
    state = {"history": history_path().exists() if include_history else None,
             "vectors": chroma_db_path().exists() if include_vectors else None}
    (rollback / _ROLLBACK_STATE_NAME).write_text(
        json.dumps(state), encoding="utf-8"
    )
    if include_history and state["history"]:
        shutil.copy2(history_path(), rollback / "history.metta")
    if include_vectors and state["vectors"]:
        rb_chroma = rollback / "chroma_db"
        shutil.copytree(chroma_db_path(), rb_chroma)

    marker.write_text(json.dumps({"receipt": receipt.name}), encoding="utf-8")
    try:
        if include_history:
            src = staging / "history" / "history.metta"
            history_path().parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, history_path())

        if include_vectors:
            _restore_vectors(staging, manifest)

        _smoke_test(include_history, include_vectors)

    except Exception:
        logger.exception("memory_transfer: overwrite failed — restoring rollback")
        try:
            _restore_rollback(rollback)
        except Exception:
            logger.exception("memory_transfer: rollback itself failed — preserving marker and rollback for manual recovery")
            raise
        marker.unlink(missing_ok=True)
        shutil.rmtree(rollback, ignore_errors=True)
        raise
    else:
        _write_receipt(receipt, digest, "overwrite", include_history, include_vectors)
        marker.unlink(missing_ok=True)
        shutil.rmtree(rollback, ignore_errors=True)

def _restore_vectors(staging: Path, manifest: dict) -> None:
    """Restore user-memory vectors while preserving non-user records."""
    records_path = staging / "vector" / "records.jsonl"
    if not records_path.exists():
        return

    col = gateway._get_collection()
    target_dimension = _collection_dimension(col)

    existing = col.get(include=["metadatas"])
    user_ids = [
        eid for eid, meta in zip(existing["ids"], existing.get("metadatas") or [])
        if _is_user_memory_record(meta)
    ]
    if user_ids:
        col.delete(ids=user_ids)

    gateway._client     = None
    gateway._collection = None
    col = gateway._get_collection()

    for records in _record_batches(records_path):
        _reembed_records(records, manifest, target_dimension)
        col.add(
            ids        =[record["id"] for record in records],
            documents  =[record["document"] for record in records],
            embeddings =[record["embedding"] for record in records],
            metadatas  =[record["metadata"] for record in records],
        )

def _import_append(staging: Path, manifest: dict,
                   include_history: bool, include_vectors: bool,
                   receipt: Path, digest: str) -> None:
    """Append imported memory to existing live memory."""
    base = memory_dir_path()
    marker = _tx_marker(base)
    state = _append_state(include_history, include_vectors)
    marker.write_text(
        json.dumps({"receipt": receipt.name, "append": state}), encoding="utf-8"
    )
    try:
        if include_history:
            src = staging / "history" / "history.metta"
            gateway.append_history("\n" + src.read_text(encoding="utf-8"))

        if include_vectors:
            records_path = staging / "vector" / "records.jsonl"
            col = gateway._get_collection()
            target_dimension = _collection_dimension(col)
            import_id = state["import_id"]
            for records in _record_batches(records_path):
                _reembed_records(records, manifest, target_dimension)
                col.upsert(
                    ids       =[f"import-{import_id}-{record['id']}" for record in records],
                    documents =[record["document"] for record in records],
                    embeddings=[record["embedding"] for record in records],
                    metadatas=[{**record["metadata"], "import_id": import_id}
                               for record in records],
                )
        _smoke_test(include_history, include_vectors)
    except Exception:
        logger.exception("memory_transfer: append failed — removing partial import")
        try:
            _rollback_append(state)
        except Exception:
            logger.exception("memory_transfer: append cleanup failed — preserving marker for recovery")
            raise
        marker.unlink(missing_ok=True)
        raise
    else:
        _write_receipt(receipt, digest, "append", include_history, include_vectors)
        marker.unlink(missing_ok=True)

def _smoke_test(include_history: bool, include_vectors: bool) -> None:
    if include_history:
        history_path().read_text(encoding="utf-8")[:1]
    if include_vectors:
        gateway._get_collection().get(limit=1)

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memory_transfer")
    sub    = parser.add_subparsers(dest="command", required=True)

    imp = sub.add_parser("import", help="Restore a memory archive (pre-start)")
    imp.add_argument("archive", type=Path)
    imp.add_argument("--mode", choices=["overwrite", "append"], default="overwrite")
    imp.add_argument("--no-history",   action="store_true")
    imp.add_argument("--no-vector",    action="store_true")
    imp.add_argument("--only-history", action="store_true")

    sub.add_parser("recover", help="Recover from an interrupted import transaction")
    return parser

if __name__ == "__main__":
    import sys
    args = _build_parser().parse_args()

    if args.command == "recover":
        recover()
        sys.exit(0)
    try:
        inc_hist, inc_vec = _parse_component_flags(args)
        import_archive(args.archive, mode=args.mode,
                       include_history=inc_hist, include_vectors=inc_vec)
    except Exception as exc:
        logger.error(f"memory_transfer import failed: {exc}")
        sys.exit(1)
