"""
One-shot cleanup for legacy test garbage left in history.metta and chromadb
from earlier smoke-test runs (before automatic teardown was added).

Safe to re-run. Only removes entries matching well-known test markers.

Run:
    pytest cleanup_legacy.py -s
"""
from helpers import (
    chromadb_cleanup_by_markers, history_cleanup_by_markers,
)


LEGACY_MARKERS = [
    "CI smoke test run-id",
    "CI-SMOKE-",
    "TOOTH-",
    "dog just lost a tooth",
    "dog lost a tooth",
    "Unique smoke marker",
    "CI smoke",
    "CI smokes",
    "smoke test marker",
    "OmegaClaw CI smoke",
    "OmegaClaw smoke",
    "/root/testcat",
    "testcat/",
    "IDLE SPIN PATTERN NOTE 2026-04-14",
    "SESSION SUMMARY 2026-04-14",
    "SKILL LEARNED 2026-04-14: File operations",
    "WRITE-FILE BUG 2026-04-14",
    "SECURITY NOTE 2026-04-14",
    "STAND DOWN ORDER 2026-04-14",
]


def test_cleanup_legacy():
    print("\n=== OmegaClaw: legacy cleanup ===", flush=True)

    print(f">> history.metta: searching for {len(LEGACY_MARKERS)} markers", flush=True)
    removed_blocks = history_cleanup_by_markers(LEGACY_MARKERS)
    print(f"[ OK ] history: removed {removed_blocks} HUMAN_MESSAGE blocks", flush=True)

    print(f">> chromadb: searching for {len(LEGACY_MARKERS)} markers", flush=True)
    removed_vectors = chromadb_cleanup_by_markers(LEGACY_MARKERS)
    print(f"[ OK ] chromadb: removed {removed_vectors} vectors", flush=True)

    print(f"\n[PASS] legacy cleanup done (blocks={removed_blocks}, "
          f"vectors={removed_vectors})\n", flush=True)
