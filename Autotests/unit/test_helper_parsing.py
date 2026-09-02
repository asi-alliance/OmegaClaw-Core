"""In-process unit tests for the parsing helpers in src/helper.py.

quote_arg / split_command_blocks / balance_parentheses turn the model's
loosely-structured reply into the s-expression the agent actually runs, so a
regression here silently corrupts every skill call. The module ships one inline
test_balance_parenthesis(), but it never exercises backslashes, embedded quotes
or quote_arg directly — the exact paths behind the escaping (#262) and command
parsing (#209) bugs. These cover them.

No container, no network, no token — same pattern as
test_fileio_verified_writes.py: the module is loaded by file path.
"""
import datetime
import importlib.util
import os
import sys

import pytest

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HELPER_PATH = os.path.join(_REPO_ROOT, "src", "helper.py")

# helper.py does `from src.logger import get_logger` (repo-root package) at import time.
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _load_helper():
    spec = importlib.util.spec_from_file_location("helper_under_test", _HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def helper():
    return _load_helper()


# --- quote_arg ------------------------------------------------------------

def test_quote_arg_wraps_plain_token(helper):
    assert helper.quote_arg("hello") == '"hello"'


def test_quote_arg_passes_through_already_quoted_single_line(helper):
    assert helper.quote_arg('"hello"') == '"hello"'


def test_quote_arg_requotes_when_quoted_value_contains_newline(helper):
    # the pass-through guard excludes newlines, so this goes through json.dumps
    assert helper.quote_arg('"a\nb"') == '"\\"a\\nb\\""'


def test_quote_arg_escapes_backslash(helper):
    assert helper.quote_arg("a\\b") == '"a\\\\b"'


def test_quote_arg_escapes_trailing_backslash_windows_path(helper):
    # #262: a trailing backslash must not escape the closing quote
    assert helper.quote_arg("C:\\path\\to\\") == '"C:\\\\path\\\\to\\\\"'


def test_quote_arg_escapes_embedded_double_quote(helper):
    assert helper.quote_arg('say "hi"') == '"say \\"hi\\""'


def test_quote_arg_escapes_real_newline(helper):
    assert helper.quote_arg("a\nb") == '"a\\nb"'


def test_quote_arg_keeps_non_ascii_unescaped(helper):
    # ensure_ascii=False keeps UTF-8 readable instead of \uXXXX
    assert helper.quote_arg("café €") == '"café €"'


# --- starts_command_line --------------------------------------------------

def test_starts_command_line_recognizes_known_commands(helper):
    assert helper.starts_command_line("send hi") is True
    assert helper.starts_command_line("(send hi)") is True
    assert helper.starts_command_line("  shell ls") is True
    assert helper.starts_command_line("write-file a b") is True


def test_starts_command_line_rejects_prose_and_blanks(helper):
    assert helper.starts_command_line("hello there") is False
    assert helper.starts_command_line("") is False
    assert helper.starts_command_line("(") is False


# --- split_command_blocks -------------------------------------------------

def test_split_attaches_continuation_lines_to_the_current_command(helper):
    assert helper.split_command_blocks("send hello\nmore text\npin done") == [
        "send hello\nmore text",
        "pin done",
    ]


def test_split_single_command_is_one_block(helper):
    assert helper.split_command_blocks("shell ls -la") == ["shell ls -la"]


def test_split_drops_blank_lines_between_commands(helper):
    assert helper.split_command_blocks("send a\n\n\npin b") == ["send a", "pin b"]


# --- balance_parentheses (escaping paths the inline test misses) ----------

def test_balance_escapes_backslashes_in_send_content(helper):
    assert helper.balance_parentheses("send C:\\path\\to") == '((send "C:\\\\path\\\\to"))'


def test_balance_escapes_backslashes_in_write_file_content(helper):
    assert helper.balance_parentheses("write-file a.txt C:\\x\\y") == (
        '((write-file "a.txt" "C:\\\\x\\\\y"))'
    )


def test_balance_escapes_embedded_quotes_in_content(helper):
    assert helper.balance_parentheses('send say "hi" ok') == '((send "say \\"hi\\" ok"))'


def test_balance_escapes_backslash_in_shell_command(helper):
    assert helper.balance_parentheses("shell echo a\\b") == '((shell "echo a\\\\b"))'


# --- normalize_string -----------------------------------------------------

def test_normalize_string_decodes_bytes(helper):
    assert helper.normalize_string(b"abc") == "abc"


def test_normalize_string_passes_through_str(helper):
    assert helper.normalize_string("abc") == "abc"


def test_normalize_string_drops_invalid_utf8_instead_of_raising(helper):
    assert helper.normalize_string(b"a\xffb") == "ab"


def test_normalize_string_stringifies_non_text(helper):
    assert helper.normalize_string(123) == "123"


# --- extract_timestamp ----------------------------------------------------

def test_extract_timestamp_parses_leading_history_stamp(helper):
    assert helper.extract_timestamp('("2026-07-30 12:00:00" foo)') == datetime.datetime(
        2026, 7, 30, 12, 0, 0
    )


def test_extract_timestamp_returns_none_when_absent(helper):
    assert helper.extract_timestamp("no timestamp here") is None
