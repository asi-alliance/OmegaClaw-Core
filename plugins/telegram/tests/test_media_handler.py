import io
import os, sys
import types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import media_handler as mh


def test_no_image_returns_marker():
    mh.clear_pending()
    mh.set_pending_media(None)
    assert mh.describe_image("anything") == "[NO_IMAGE: nothing is attached to describe]"


def test_describe_memoizes_per_turn():
    calls = {"n": 0}
    orig = mh._call_vision_model

    def fake(image_parts, prompt):
        calls["n"] += 1
        return "a red panda"

    mh._call_vision_model = fake
    try:
        mh.set_pending_media([{"type": "image_url",
                               "image_url": {"url": "data:image/jpeg;base64,AAAA"}}])
        r1 = mh.describe_image("")
        r2 = mh.describe_image("")
        assert r1 == r2 == "[IMAGE DESCRIPTION]\na red panda", r1
        assert calls["n"] == 1, calls["n"]

        # A reply's clear_pending() must NOT blind describe-image mid-turn.
        mh.clear_pending()
        assert mh.describe_image("") == "[IMAGE DESCRIPTION]\na red panda"
        # A new non-image message makes the prior image stale.
        mh.set_pending_media(None)
        assert mh.describe_image("") == "[NO_IMAGE: nothing is attached to describe]"
    finally:
        mh._call_vision_model = orig
        mh.clear_pending()
        mh.set_pending_media(None)


def test_describe_never_raises():
    def boom(image_parts, prompt):
        raise RuntimeError("network down")

    orig = mh._call_vision_model
    mh._call_vision_model = boom
    try:
        mh.set_pending_media([{"type": "image_url",
                               "image_url": {"url": "data:image/jpeg;base64,BBBB"}}])
        out = mh.describe_image("")
        assert out.startswith("[IMAGE_DESCRIPTION_FAILED:"), out
    finally:
        mh._call_vision_model = orig
        mh.clear_pending()
        mh.set_pending_media(None)


def test_describe_never_raises_on_malformed_media():
    # A producer could set a malformed value directly; describe_image must still
    # return a marker rather than propagate an exception.
    mh._pending_media = 12345          # not a list/None
    mh._describe_media = 12345
    try:
        out = mh.describe_image("")
        assert out.startswith("[IMAGE_DESCRIPTION_FAILED:"), out
    finally:
        mh.clear_pending()
        mh.set_pending_media(None)


def test_sanitize_image_roundtrips_to_jpeg():
    from PIL import Image

    src = io.BytesIO()
    Image.new("RGB", (1, 1)).save(src, format="PNG")
    out = mh.sanitize_image(src.getvalue())
    assert out and isinstance(out, bytes)
    reopened = Image.open(io.BytesIO(out))
    assert reopened.format == "JPEG"


def test_extract_pdf_text_success_with_stubbed_pypdf():
    class FakePage:
        def extract_text(self):
            return "known page text"

    class FakePdfReader:
        def __init__(self, buf):
            self.pages = [FakePage()]

    fake_pypdf = types.ModuleType("pypdf")
    fake_pypdf.PdfReader = FakePdfReader
    sys.modules["pypdf"] = fake_pypdf
    try:
        out = mh.extract_pdf_text(b"irrelevant bytes", "doc.pdf")
        assert "known page text" in out, out
        assert "[PDF: doc.pdf]" in out, out
    finally:
        del sys.modules["pypdf"]


def test_extract_pdf_text_failure_returns_marker_never_raises():
    # Deterministically exercise the failure path regardless of whether pypdf is
    # installed: stub PdfReader to raise. Must return a marker, never raise.
    class BoomReader:
        def __init__(self, buf):
            raise RuntimeError("corrupt pdf")

    fake_pypdf = types.ModuleType("pypdf")
    fake_pypdf.PdfReader = BoomReader
    saved = sys.modules.get("pypdf")
    sys.modules["pypdf"] = fake_pypdf
    try:
        out = mh.extract_pdf_text(b"irrelevant bytes", "doc.pdf")
        assert out.startswith("[PDF: doc.pdf]"), out
        assert "Could not extract text" in out, out
    finally:
        if saved is not None:
            sys.modules["pypdf"] = saved
        else:
            del sys.modules["pypdf"]


def test_transcribe_audio_success_with_stubbed_openai_client():
    import openai

    class FakeTranscriptions:
        def create(self, **kwargs):
            assert kwargs["model"] == "openai/whisper-large-v3"
            return types.SimpleNamespace(text="hello world")

    class FakeAudio:
        transcriptions = FakeTranscriptions()

    class FakeClient:
        audio = FakeAudio()

    orig_openai_cls = openai.OpenAI
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    openai.OpenAI = lambda *a, **kw: FakeClient()
    try:
        out = mh.transcribe_audio(b"fake audio bytes", "voice.ogg")
        assert "hello world" in out, out
        assert "[AUDIO TRANSCRIPT: voice.ogg]" in out, out
    finally:
        openai.OpenAI = orig_openai_cls
        os.environ.pop("OPENROUTER_API_KEY", None)


def test_transcribe_audio_missing_key_returns_marker_never_raises():
    os.environ.pop("OPENROUTER_API_KEY", None)
    out = mh.transcribe_audio(b"fake audio bytes", "voice.ogg")
    assert out.startswith("[AUDIO TRANSCRIPT: voice.ogg]"), out


def test_generate_and_send_disabled():
    orig = mh._image_generation_allowed
    mh._image_generation_allowed = lambda: False
    try:
        out = mh.generate_and_send("a cat")
        assert out.startswith("IMAGE_DISABLED"), out
    finally:
        mh._image_generation_allowed = orig


def test_generate_and_send_unsafe():
    orig_allowed = mh._image_generation_allowed
    orig_unsafe = mh._prompt_is_unsafe
    mh._image_generation_allowed = lambda: True
    mh._prompt_is_unsafe = lambda prompt: True
    try:
        out = mh.generate_and_send("a cat")
        assert out.startswith("Refused"), out
    finally:
        mh._image_generation_allowed = orig_allowed
        mh._prompt_is_unsafe = orig_unsafe


def test_generate_and_send_generation_failure():
    orig_allowed = mh._image_generation_allowed
    orig_unsafe = mh._prompt_is_unsafe
    orig_gen = mh._generate_image_bytes
    mh._image_generation_allowed = lambda: True
    mh._prompt_is_unsafe = lambda prompt: False
    mh._generate_image_bytes = lambda prompt: None
    try:
        out = mh.generate_and_send("a cat")
        assert out.startswith("IMAGE_FAILED"), out
    finally:
        mh._image_generation_allowed = orig_allowed
        mh._prompt_is_unsafe = orig_unsafe
        mh._generate_image_bytes = orig_gen


def test_generate_and_send_success():
    orig_allowed = mh._image_generation_allowed
    orig_unsafe = mh._prompt_is_unsafe
    orig_gen = mh._generate_image_bytes
    orig_send, orig_chan = mh._live_send_photo, mh._live_channel

    sent = {}
    mh._image_generation_allowed = lambda: True
    mh._prompt_is_unsafe = lambda prompt: False
    mh._generate_image_bytes = lambda prompt: b"img"
    mh.register_channel(lambda image_bytes, caption=None: sent.update(
        bytes=image_bytes, caption=caption), object())
    try:
        out = mh.generate_and_send("a cat")
        assert out.startswith("IMAGE_SENT"), out
        assert sent["bytes"] == b"img", sent
    finally:
        mh._image_generation_allowed = orig_allowed
        mh._prompt_is_unsafe = orig_unsafe
        mh._generate_image_bytes = orig_gen
        mh._live_send_photo, mh._live_channel = orig_send, orig_chan


def test_generate_and_send_without_registered_channel():
    # Regression: the image generated but no channel was registered to send it.
    # Live runs hit this because the plugin loader execs plugin modules without
    # adding them to sys.modules, so looking the channel up by name found a
    # second, never-started copy.
    orig_allowed = mh._image_generation_allowed
    orig_unsafe = mh._prompt_is_unsafe
    orig_gen = mh._generate_image_bytes
    orig_send = mh._live_send_photo

    mh._image_generation_allowed = lambda: True
    mh._prompt_is_unsafe = lambda prompt: False
    mh._generate_image_bytes = lambda prompt: b"img"
    mh._live_send_photo = None
    try:
        out = mh.generate_and_send("a cat")
        assert out == "IMAGE_FAILED: generated but no channel is registered to send it", out
    finally:
        mh._image_generation_allowed = orig_allowed
        mh._prompt_is_unsafe = orig_unsafe
        mh._generate_image_bytes = orig_gen
        mh._live_send_photo = orig_send


def test_register_channel_wires_gate_and_sender():
    orig_send, orig_chan = mh._live_send_photo, mh._live_channel
    try:
        class Chan:
            reply_constraints = {"allow_image_generation": True}
        mh.register_channel(lambda *a, **k: None, Chan())
        assert mh._image_generation_allowed() is True
        Chan.reply_constraints = {"allow_image_generation": False}
        assert mh._image_generation_allowed() is False
    finally:
        mh._live_send_photo, mh._live_channel = orig_send, orig_chan


def test_generate_and_send_empty_prompt():
    out = mh.generate_and_send("   ")
    assert out == "IMAGE_FAILED: empty prompt", out


if __name__ == "__main__":
    test_no_image_returns_marker()
    test_describe_memoizes_per_turn()
    test_describe_never_raises()
    test_describe_never_raises_on_malformed_media()
    test_sanitize_image_roundtrips_to_jpeg()
    test_extract_pdf_text_success_with_stubbed_pypdf()
    test_extract_pdf_text_failure_returns_marker_never_raises()
    test_transcribe_audio_success_with_stubbed_openai_client()
    test_transcribe_audio_missing_key_returns_marker_never_raises()
    test_generate_and_send_disabled()
    test_generate_and_send_unsafe()
    test_generate_and_send_generation_failure()
    test_generate_and_send_success()
    test_generate_and_send_without_registered_channel()
    test_register_channel_wires_gate_and_sender()
    test_generate_and_send_empty_prompt()
    print("all media_handler tests passed")
