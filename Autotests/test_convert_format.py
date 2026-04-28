"""
Test: OmegaClaw converts a .md file to .txt preserving content.

Run:
    pytest test_convert_format.py -s
"""
import time

from helpers import (
    Checker, dexec, dexec_root, make_prompt, send_prompt, wait_for_file,
)

TARGET_DIR = "/tmp/test_convert"
SOURCE_FILE = "/tmp/test_convert/document.md"
DEST_FILE = "/tmp/test_convert/document.txt"
FILE_CONTENT = "# My Title\n\nSome paragraph text.\n\n- item one\n- item two\n"


def test_convert_md_to_txt():
    with Checker("convert .md to .txt", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== OmegaClaw: convert format (run-id {c.run_id}) ===", flush=True)

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
            "Preserve the original text content.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step(f"wait for {DEST_FILE}")
        mtime = wait_for_file(DEST_FILE, start_ts)
        if mtime is None:
            c.fail("file created", f"{DEST_FILE} not created within timeout")
        c.ok("file created", f"after {mtime - start_ts}s")

        c.step("check .txt file exists")
        if dexec("test", "-f", DEST_FILE).returncode != 0:
            c.fail("file exists", f"{DEST_FILE} missing")
        c.ok("file exists")

        c.step("check content preserved")
        converted = dexec("cat", DEST_FILE).stdout
        for key_phrase in ["My Title", "Some paragraph text", "item one", "item two"]:
            if key_phrase not in converted:
                c.fail("content", f"missing {repr(key_phrase)} in converted file: {repr(converted)}")
        c.ok("content", f"{len(converted)} bytes")

        c.done()
