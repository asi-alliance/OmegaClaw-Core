"""Contract test for provider prompts that govern diagnostic claims."""

from pathlib import Path


PROMPT = Path(__file__).parents[1] / "memory" / "prompt_ASICloud.txt"


def test_asicloud_prompt_requires_verified_diagnostics():
    prompt = PROMPT.read_text(encoding="utf-8")

    required_rules = (
        "- a real error that has been verified with a tool result and has not yet been reported",
        "Do not report a file, syntax, or configuration error based on visual inspection or guesswork.",
        "Before reporting an error, verify it with a tool result such as read-file, shell, or metta.",
        "Do not perform unsolicited code reviews or invent errors during idle cycles.",
    )

    for rule in required_rules:
        assert rule in prompt
