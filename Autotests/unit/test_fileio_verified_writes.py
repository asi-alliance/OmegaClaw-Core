"""In-process unit tests for src/fileio.py (verified file writes).

The write-file / append-file / write-file-b64 skills return a result string
built from a read-back of the file on disk (size, sha256, head/tail) — ground
truth the agent relays instead of a static success atom it could confabulate
around. Failures return explicit *-FAILED strings instead of raising.

No container, no network, no token — same pattern as
mock_websocket/test_wschat_unit.py: the module is loaded by file path.
"""
import base64
import hashlib
import importlib.util
import logging
import os
import sys

import pytest

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_FILEIO_PATH = os.path.join(_REPO_ROOT, "src", "fileio.py")

# fileio.py does `from src.logger import get_logger` (repo-root package) at import time.
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _load_fileio():
    spec = importlib.util.spec_from_file_location("fileio_under_test", _FILEIO_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fileio():
    return _load_fileio()


def _sha16(data):
    return hashlib.sha256(data).hexdigest()[:16]


def test_write_result_is_read_back_from_disk(fileio, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    target = tmp_path / "out.txt"
    content = "hello world"

    result = fileio.write_file(str(target), content)

    assert target.read_bytes() == b"hello world"
    assert result == (
        f"WRITE-VERIFIED file={target} bytes=11 sha256={_sha16(b'hello world')} "
        "head='hello world' tail=''"
    )
    assert "[FILE_IO] write ok" in caplog.text


def test_quotes_and_backslashes_land_byte_exact(fileio, tmp_path):
    target = tmp_path / "tricky.txt"
    content = 'he said "hi\\n" then C:\\path\\to \'quoted\''

    result = fileio.write_file(str(target), content)

    assert target.read_bytes() == content.encode("utf-8")
    assert f"sha256={_sha16(content.encode('utf-8'))}" in result
    assert result.startswith("WRITE-VERIFIED")


def test_bytes_count_utf8_bytes_not_chars(fileio, tmp_path):
    target = tmp_path / "unicode.txt"
    content = "größe €100 ✓"

    result = fileio.write_file(str(target), content)

    assert f"bytes={len(content.encode('utf-8'))}" in result
    assert target.read_text(encoding="utf-8") == content


def test_long_content_reports_head_and_tail_snippets(fileio, tmp_path):
    target = tmp_path / "long.txt"
    content = "A" * 100 + "\n" + "B" * 100

    result = fileio.write_file(str(target), content)

    assert "head='" + "A" * 80 + "'" in result
    assert "tail='" + "B" * 80 + "'" in result
    assert "bytes=201" in result


def test_snippet_distinguishes_literal_backslash_n_from_newline(fileio, tmp_path):
    literal = fileio.write_file(str(tmp_path / "a.txt"), "x\\ny")  # backslash + n + y
    real = fileio.write_file(str(tmp_path / "b.txt"), "x\ny")  # real newline

    assert "head='x\\\\ny'" in literal
    assert "head='x\\ny'" in real
    assert literal.split("head=")[1] != real.split("head=")[1]


def test_write_failure_returns_failed_string_not_exception(fileio, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    target = tmp_path / "no_such_dir" / "out.txt"

    result = fileio.write_file(str(target), "content")

    assert result.startswith(f"WRITE-FAILED file={target}:")
    assert "[FILE_IO] write failed" in caplog.text


def test_append_adds_newline_and_verifies_whole_file(fileio, tmp_path):
    target = tmp_path / "log.txt"
    target.write_bytes(b"line1\n")

    result = fileio.append_file(str(target), "line2")

    expected = b"line1\nline2\n"  # no f-string expression backslashes: PEP 701 is 3.12+
    assert target.read_bytes() == expected
    assert result.startswith("APPEND-VERIFIED")
    assert "bytes=12" in result
    assert f"sha256={_sha16(expected)}" in result


def test_append_to_missing_file_fails_without_creating_it(fileio, tmp_path):
    target = tmp_path / "absent.txt"

    result = fileio.append_file(str(target), "line")

    assert result == f"APPEND-FAILED file={target}: file does not exist"
    assert not target.exists()


def test_b64_roundtrips_hostile_content_byte_exact(fileio, tmp_path):
    target = tmp_path / "script.sh"
    content = '#!/bin/bash\necho "a\\"b" \'c\'\nprintf \'%s\\n\' "$1"\n'
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

    result = fileio.write_file_b64(str(target), encoded)

    assert target.read_bytes() == content.encode("utf-8")
    assert result.startswith("WRITE-VERIFIED")
    assert f"sha256={_sha16(content.encode('utf-8'))}" in result


def test_b64_accepts_line_wrapped_input(fileio, tmp_path):
    target = tmp_path / "wrapped.txt"
    content = "x" * 200
    encoded = base64.encodebytes(content.encode("utf-8")).decode("ascii")
    assert "\n" in encoded.strip()  # MIME-style 76-char wrapping

    result = fileio.write_file_b64(str(target), encoded)

    assert target.read_bytes() == content.encode("utf-8")
    assert result.startswith("WRITE-VERIFIED")


def test_b64_invalid_input_fails_without_writing(fileio, tmp_path):
    target = tmp_path / "never.txt"

    result = fileio.write_file_b64(str(target), "this is !!! not base64")

    assert result.startswith(f"WRITE-FAILED file={target}: invalid base64")
    assert not target.exists()
