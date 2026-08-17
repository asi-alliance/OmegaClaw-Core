import importlib
import io
import json
import tarfile
import threading
import types
from pathlib import Path

import pytest
import yaml

EMBEDDING = [0.1, 0.2, 0.3]
REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    monkeypatch.setenv("MEMORY_DIR", str(memory_dir))

    import src.memory_layout as layout
    importlib.reload(layout)
    import src.memory_gateway as gateway
    importlib.reload(gateway)
    import src.memory_transfer as transfer
    importlib.reload(transfer)
    transfer.TRANSFER_DIR = tmp_path / "transfer"
    transfer.TRANSFER_DIR.mkdir()
    return transfer, gateway, memory_dir


def test_launcher_and_policy_wiring():
    launcher = (REPO_ROOT / "scripts" / "omegaclaw").read_text()
    entrypoint = (REPO_ROOT / "entrypoint.sh").read_text()
    config = (REPO_ROOT / "config" / "config.yaml").read_text()
    dockerfile = (REPO_ROOT / "Dockerfile").read_text()
    policy = yaml.safe_load((REPO_ROOT / "profile" / "policy.yaml").read_text())

    assert "memoryExportEnabled: false" in config
    assert "--enable-memory-export" in launcher
    assert "MEMORY_IMPORT_ONLY_HISTORY" in launcher
    assert '    -- sh "$OMEGACLAW_DIR" "${import_args[@]}"' in entrypoint
    assert 'echo "memory_transfer: import complete"' in entrypoint
    assert "mkdir -p /memory-transfer" in dockerfile
    assert "/memory-transfer" in policy["filesystem_policy"]["read_write"]


def test_export_both_contains_only_portable_user_memory(isolated_memory):
    transfer, gateway, memory_dir = isolated_memory
    (memory_dir / "history.metta").write_text("portable history\n")
    gateway.remember("portable fact", EMBEDDING, "2026-01-01")
    gateway._get_collection().add(
        ids=["knowledge"], documents=["non-user data"], embeddings=[EMBEDDING],
        metadatas=[{"type": "chunk"}],
    )

    result = transfer.export("both")
    with tarfile.open(transfer.TRANSFER_DIR / result["filename"], "r:gz") as archive:
        assert set(archive.getnames()) == {
            "manifest.json", "history/history.metta", "vector/collections.json", "vector/records.jsonl"
        }
        records = [json.loads(line) for line in archive.extractfile("vector/records.jsonl")]

    assert result["record_count"] == 1
    assert [record["document"] for record in records] == ["portable fact"]


def test_concurrent_exports_publish_distinct_archives(isolated_memory):
    transfer, _, _ = isolated_memory
    results = []
    threads = [threading.Thread(target=lambda: results.append(transfer.export("history"))) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert len({result["filename"] for result in results}) == 2


def test_malformed_archive_is_rejected_before_mutating_memory(isolated_memory, tmp_path):
    transfer, _, memory_dir = isolated_memory
    history = memory_dir / "history.metta"
    history.write_text("original\n")
    valid = transfer.TRANSFER_DIR / transfer.export("history")["filename"]
    invalid = tmp_path / "invalid.tar.gz"
    with tarfile.open(valid, "r:gz") as source, tarfile.open(invalid, "w:gz") as output:
        for member in source.getmembers():
            output.addfile(member, source.extractfile(member))
        extra = tarfile.TarInfo("unexpected.txt")
        extra.size = 1
        output.addfile(extra, io.BytesIO(b"x"))

    history.write_text("live\n")
    with pytest.raises(ValueError, match="Unexpected archive member"):
        transfer.import_archive(invalid)
    assert history.read_text() == "live\n"


def test_invalid_record_count_is_rejected_before_mutating_vectors(isolated_memory, tmp_path):
    transfer, gateway, _ = isolated_memory
    gateway.remember("source fact", EMBEDDING, "2026-01-01")
    valid = transfer.TRANSFER_DIR / transfer.export("ltm")["filename"]
    invalid = tmp_path / "invalid-count.tar.gz"
    with tarfile.open(valid, "r:gz") as source, tarfile.open(invalid, "w:gz") as output:
        for member in source.getmembers():
            if member.name == "manifest.json":
                manifest = json.loads(source.extractfile(member).read())
                manifest["record_count"] = 2
                data = json.dumps(manifest).encode()
                member.size = len(data)
                output.addfile(member, io.BytesIO(data))
            else:
                output.addfile(member, source.extractfile(member))

    with pytest.raises(ValueError, match="record count"):
        transfer.import_archive(invalid, include_history=False, include_vectors=True)
    assert gateway._get_collection().count() == 1


def test_invalid_manifest_schema_is_rejected_before_mutating_memory(isolated_memory, tmp_path):
    transfer, _, memory_dir = isolated_memory
    (memory_dir / "history.metta").write_text("archive history\n")
    valid = transfer.TRANSFER_DIR / transfer.export("history")["filename"]
    invalid = tmp_path / "invalid-manifest.tar.gz"
    with tarfile.open(valid, "r:gz") as source, tarfile.open(invalid, "w:gz") as output:
        for member in source.getmembers():
            if member.name == "manifest.json":
                manifest = json.loads(source.extractfile(member).read())
                manifest["created_at"] = 1
                data = json.dumps(manifest).encode()
                member.size = len(data)
                output.addfile(member, io.BytesIO(data))
            else:
                output.addfile(member, source.extractfile(member))

    (memory_dir / "history.metta").write_text("live history\n")
    with pytest.raises(ValueError, match="created_at"):
        transfer.import_archive(invalid)
    assert (memory_dir / "history.metta").read_text() == "live history\n"


def test_import_extracts_archive_once(isolated_memory, monkeypatch):
    transfer, _, memory_dir = isolated_memory
    (memory_dir / "history.metta").write_text("archive history\n")
    archive = transfer.TRANSFER_DIR / transfer.export("history")["filename"]
    extractions = []
    original_extract = transfer._safe_extract

    def track_extract(tar, dest):
        extractions.append(dest)
        original_extract(tar, dest)

    monkeypatch.setattr(transfer, "_safe_extract", track_extract)
    transfer.import_archive(archive)

    assert len(extractions) == 1


def test_overwrite_round_trip_restores_history_and_ltm(isolated_memory):
    transfer, gateway, memory_dir = isolated_memory
    (memory_dir / "history.metta").write_text("archived history\n")
    gateway.remember("archived fact", EMBEDDING, "2026-01-01")
    collection = gateway._get_collection()
    collection.add(
        ids=["knowledge"], documents=["retain this"], embeddings=[EMBEDDING], metadatas=[{"type": "chunk"}]
    )
    archive = transfer.TRANSFER_DIR / transfer.export("both")["filename"]

    (memory_dir / "history.metta").write_text("live history\n")
    collection.delete(ids=[record_id for record_id in collection.get(include=[])["ids"] if record_id != "knowledge"])
    transfer.import_archive(archive, mode="overwrite")

    documents = gateway._get_collection().get(include=["documents"])["documents"]
    assert (memory_dir / "history.metta").read_text() == "archived history\n"
    assert set(documents) == {"archived fact", "retain this"}


def test_history_only_import_does_not_open_chromadb(isolated_memory, monkeypatch):
    transfer, gateway, memory_dir = isolated_memory
    (memory_dir / "history.metta").write_text("archived history\n")
    archive = transfer.TRANSFER_DIR / transfer.export("history")["filename"]
    monkeypatch.setattr(gateway, "_get_collection", lambda: pytest.fail("opened ChromaDB"))

    transfer.import_archive(archive, include_history=True, include_vectors=False)

    assert (memory_dir / "history.metta").read_text() == "archived history\n"


def test_reembedding_runs_for_changed_embedding_profile(isolated_memory, monkeypatch):
    transfer, gateway, _ = isolated_memory
    gateway.remember("portable fact", EMBEDDING, "2026-01-01")
    archive = transfer.TRANSFER_DIR / transfer.export("ltm")["filename"]
    monkeypatch.setattr(transfer, "_embedding_profile", lambda: {"provider": "Local", "model": "new"})
    rag = types.ModuleType("src.rag")
    rag.local_embed_batch = lambda documents: [[0.4, 0.5, 0.6] for _ in documents]
    rag.openai_embed_batch = rag.local_embed_batch
    monkeypatch.setitem(__import__("sys").modules, "src.rag", rag)

    transfer.import_archive(archive, include_history=False, include_vectors=True)

    embedding = gateway._get_collection().get(include=["embeddings"])["embeddings"][0]
    assert list(embedding) == pytest.approx([0.4, 0.5, 0.6])


def test_overwrite_failure_restores_absent_history_state(isolated_memory, monkeypatch):
    transfer, _, memory_dir = isolated_memory
    (memory_dir / "history.metta").write_text("archive history\n")
    archive = transfer.TRANSFER_DIR / transfer.export("history")["filename"]
    (memory_dir / "history.metta").unlink()
    monkeypatch.setattr(transfer, "_smoke_test", lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        transfer.import_archive(archive)
    assert not (memory_dir / "history.metta").exists()


def test_receipt_prevents_repeat_overwrite(isolated_memory):
    transfer, _, memory_dir = isolated_memory
    (memory_dir / "history.metta").write_text("archive history\n")
    archive = transfer.TRANSFER_DIR / transfer.export("history")["filename"]
    (memory_dir / "history.metta").write_text("before import\n")
    transfer.import_archive(archive)
    (memory_dir / "history.metta").write_text("new memory\n")

    transfer.import_archive(archive)

    assert (memory_dir / "history.metta").read_text() == "new memory\n"


def test_append_failure_removes_partial_history_and_vectors(isolated_memory, monkeypatch):
    transfer, gateway, memory_dir = isolated_memory
    (memory_dir / "history.metta").write_text("archive history\n")
    gateway.remember("archive fact", EMBEDDING, "2026-01-01")
    archive = transfer.TRANSFER_DIR / transfer.export("both")["filename"]
    (memory_dir / "history.metta").write_text("live history\n")
    gateway.remember("live fact", EMBEDDING, "2026-01-02")
    original_count = gateway._get_collection().count()
    monkeypatch.setattr(transfer, "_smoke_test", lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        transfer.import_archive(archive, mode="append")

    assert (memory_dir / "history.metta").read_text() == "live history\n"
    assert gateway._get_collection().count() == original_count


def test_recovery_removes_interrupted_append(isolated_memory):
    transfer, gateway, memory_dir = isolated_memory
    history = memory_dir / "history.metta"
    history.write_text("original\npartial\n")
    import_id = "interrupted"
    gateway._get_collection().add(
        ids=["partial"], documents=["partial fact"], embeddings=[EMBEDDING],
        metadatas=[{"import_id": import_id}],
    )
    (memory_dir / transfer._TX_MARKER_NAME).write_text(json.dumps({"append": {
        "history": {"existed": True, "size": len("original\n")}, "import_id": import_id,
    }}))

    transfer.recover(memory_dir)

    assert history.read_text() == "original\n"
    assert gateway._get_collection().get(where={"import_id": import_id}, include=[])["ids"] == []


def test_export_is_disabled_until_explicitly_enabled(isolated_memory, monkeypatch):
    transfer, _, _ = isolated_memory
    monkeypatch.delenv("OMEGACLAW_memoryExportEnabled", raising=False)
    assert transfer.is_export_enabled() is False
    monkeypatch.setenv("OMEGACLAW_memoryExportEnabled", "true")
    assert transfer.is_export_enabled() is True
