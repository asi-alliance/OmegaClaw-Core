import importlib

import src.memory_layout as memory_layout


def test_memory_dir_controls_both_persistent_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_DIR", str(tmp_path))
    layout = importlib.reload(memory_layout)

    assert layout.history_path() == tmp_path.resolve() / "history.metta"
    assert layout.chroma_db_path() == tmp_path.resolve() / "chroma_db"


def test_default_paths_are_absolute(monkeypatch):
    monkeypatch.delenv("MEMORY_DIR", raising=False)
    layout = importlib.reload(memory_layout)

    assert layout.history_path().is_absolute()
    assert layout.chroma_db_path().is_absolute()
