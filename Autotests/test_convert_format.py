"""
Test: Omega converts a .md file to .txt preserving content.

Run:
    pytest test_convert_format.py -s
"""
import time

from helpers import (
    Checker, dexec, dexec_root, make_prompt, send_prompt,
    try_with_clarification,
)

TARGET_DIR = "/tmp/test_convert"
SOURCE_FILE = "/tmp/test_convert/document.md"
DEST_FILE = "/tmp/test_convert/document.txt"
FILE_CONTENT = "# My Title\n\nSome paragraph text.\n\n- item one\n- item two\n"
KEY_PHRASES = ["My Title", "Some paragraph text", "item one", "item two"]


def test_convert_md_to_txt():
    with Checker("convert .md to .txt", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== Omega: convert format (run-id {c.run_id}) ===", flush=True)

        c.verify_clean()

        c.step("pre-create .md file")
        dexec_root("mkdir", "-p", TARGET_DIR)
        dexec_root("sh", "-c", f"cat > {SOURCE_FILE} << 'ENDOFFILE'\n{FILE_CONTENT}ENDOFFILE")
        dexec_root("chmod", "777", TARGET_DIR)
        dexec_root("chmod", "666", SOURCE_FILE)
        if dexec("cat", SOURCE_FILE).returncode != 0:
            c.fail("pre-create", "could not create .md file")
        c.ok("pre-create")

        start_ts = int(time.time()) - 1

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Convert the file {SOURCE_FILE} from .md format to .txt format. "
            f"The result should be saved as {DEST_FILE}. "
            "Preserve ALL of the original text content (title, paragraph, "
            "and bullet list). The simplest way is one shell call: "
            f"(shell cp {SOURCE_FILE} {DEST_FILE}).",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step(f"wait for {DEST_FILE} with all phrases (graded)")

        def dest_has_all_phrases():
            res = dexec("cat", DEST_FILE)
            if res.returncode != 0:
                return None
            converted = res.stdout
            if all(p in converted for p in KEY_PHRASES):
                return converted
            return None

        clarification = (
            f"The destination file {DEST_FILE} is missing some content. "
            f"The simplest correct approach is ONE shell call: "
            f"(shell cp {SOURCE_FILE} {DEST_FILE}). "
            f"This copies every line — title, paragraph, and bullet list — verbatim."
        )
        grade, converted = try_with_clarification(
            c, dest_has_all_phrases, clarification,
            timeout_first=120, timeout_second=180,
        )
        c.set_grade(grade)
        if grade == Checker.GRADE_FAIL:
            actual = dexec("cat", DEST_FILE).stdout if dexec("test", "-f", DEST_FILE).returncode == 0 else "<missing>"
            c.fail("content", f"final {DEST_FILE} content: {actual!r}")
        c.ok("content", f"{len(converted)} bytes (grade={grade})")

        c.step("check .txt file exists")
        if dexec("test", "-f", DEST_FILE).returncode != 0:
            c.fail("file exists", f"{DEST_FILE} missing")
        c.ok("file exists")

        c.step("check mtime fresh")
        mtime_res = dexec("stat", "-c", "%Y", DEST_FILE)
        mtime = int(mtime_res.stdout.strip()) if mtime_res.returncode == 0 else 0
        if mtime < start_ts:
            c.fail("file mtime", f"{mtime} < {start_ts}")
        c.ok("file mtime", f"{mtime} >= {start_ts}")

        c.done()
