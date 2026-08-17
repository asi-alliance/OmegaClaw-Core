import importlib
import threading

import pytest

EMBEDDING = [0.1, 0.2, 0.3]


@pytest.fixture(autouse=True)
def isolated_gateway(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_DIR", str(tmp_path))
    import src.memory_layout as layout
    importlib.reload(layout)
    import src.memory_gateway as gateway
    importlib.reload(gateway)
    return gateway


def test_history_append_and_ltm_query(isolated_gateway, tmp_path):
    isolated_gateway.append_history("first")
    isolated_gateway.append_history("second")
    isolated_gateway.remember("portable fact", EMBEDDING, "2026-01-01")

    assert (tmp_path / "history.metta").read_text() == "first\nsecond\n"
    assert isolated_gateway.query(EMBEDDING, 1) == [["2026-01-01", "portable fact"]]
    metadata = isolated_gateway._get_collection().get(include=["metadatas"])["metadatas"]
    assert metadata[0]["record_kind"] == "user_memory"


def test_export_lock_blocks_history_write(isolated_gateway, tmp_path):
    finished = threading.Event()
    thread = threading.Thread(
        target=lambda: (isolated_gateway.append_history("concurrent"), finished.set())
    )

    with isolated_gateway._write_lock:
        thread.start()
        assert not finished.wait(0.05)
    thread.join(timeout=2)

    assert finished.is_set()
    assert (tmp_path / "history.metta").read_text() == "concurrent\n"
