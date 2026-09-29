from pathlib import Path
from types import SimpleNamespace

import pytest

from yt_transcriber.errors import MissingDependency, VideoNotAccessible
from yt_transcriber.models import WhisperOptions
from yt_transcriber.whisper_backend import (
    _require,
    download_audio,
    transcribe_audio,
    transcribe_with_whisper,
)

VID = "dQw4w9WgXcQ"


class FakeYDL:
    """Imita yt_dlp.YoutubeDL: grava um "áudio" de verdade na pasta pedida."""

    last_options = None
    fail_with = None

    def __init__(self, options):
        type(self).last_options = options
        self._dir = Path(options["outtmpl"]).parent

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download):
        if self.fail_with:
            raise self.fail_with
        assert download is True and VID in url
        (self._dir / f"{VID}.m4a").write_bytes(b"audio")
        return {"id": VID, "ext": "m4a", "title": "Meu vídeo"}

    def prepare_filename(self, info):
        return str(self._dir / f"{info['id']}.{info['ext']}")


@pytest.fixture(autouse=True)
def _reset_fake():
    FakeYDL.fail_with = None
    FakeYDL.last_options = None


def fake_model_factory(segments, language="pt", duration=10.0):
    seen = {}

    def factory(size, device, compute_type):
        seen.update(size=size, device=device, compute_type=compute_type)

        class Model:
            def transcribe(self, path, **kwargs):
                seen.update(path=path, **kwargs)
                return iter(segments), SimpleNamespace(language=language, duration=duration)

        return Model()

    factory.seen = seen
    return factory


def seg(start, end, text):
    return SimpleNamespace(start=start, end=end, text=text)


def test_download_returns_file_and_title(tmp_path):
    path, title = download_audio(VID, tmp_path, ydl_factory=FakeYDL)
    assert path == tmp_path / f"{VID}.m4a" and path.read_bytes() == b"audio"
    assert title == "Meu vídeo"


def test_download_asks_for_audio_only_without_conversion(tmp_path):
    download_audio(VID, tmp_path, ydl_factory=FakeYDL)
    opts = FakeYDL.last_options
    assert opts["format"] == "bestaudio/best"
    assert opts["noplaylist"] is True
    assert "postprocessors" not in opts  # nada de converter: dispensa ffmpeg
    assert Path(opts["outtmpl"]).parent == tmp_path


def test_download_failure_becomes_a_clear_error(tmp_path):
    FakeYDL.fail_with = RuntimeError("HTTP 403")
    with pytest.raises(VideoNotAccessible, match="RuntimeError"):
        download_audio(VID, tmp_path, ydl_factory=FakeYDL)


def test_transcribe_audio_cleans_text_and_drops_empty_segments(tmp_path):
    factory = fake_model_factory([seg(0, 2, " Olá  mundo \n"), seg(2, 3, "   "), seg(3, 5, "fim")])
    t = transcribe_audio(
        tmp_path / "a.m4a",
        video_id=VID,
        title="T",
        options=WhisperOptions(model="tiny", device="cpu", compute_type="int8"),
        model_factory=factory,
    )
    assert [(s.start, s.end, s.text) for s in t.segments] == [(0, 2, "Olá mundo"), (3, 5, "fim")]
    assert (t.source, t.language, t.title, t.video_id) == ("whisper", "pt", "T", VID)
    assert factory.seen["size"] == "tiny"
    assert factory.seen["device"] == "cpu" and factory.seen["compute_type"] == "int8"


def test_transcribe_audio_filters_silence_and_passes_language(tmp_path):
    factory = fake_model_factory([seg(0, 1, "x")])
    transcribe_audio(tmp_path / "a.m4a", video_id=VID, language="en", model_factory=factory)
    assert factory.seen["vad_filter"] is True
    assert factory.seen["language"] == "en"


def test_language_autodetect_when_not_given(tmp_path):
    factory = fake_model_factory([seg(0, 1, "x")], language="es")
    t = transcribe_audio(tmp_path / "a.m4a", video_id=VID, model_factory=factory)
    assert factory.seen["language"] is None and t.language == "es"


def test_progress_is_monotonic_and_capped_at_one(tmp_path):
    factory = fake_model_factory(
        [seg(0, 2.5, "a"), seg(2.5, 5, "b"), seg(5, 10, "c"), seg(10, 12, "d")], duration=10.0
    )
    seen = []
    audio = tmp_path / "a.m4a"
    transcribe_audio(audio, video_id=VID, on_progress=seen.append, model_factory=factory)
    assert seen == [0.25, 0.5, 1.0, 1.0]
    assert seen == sorted(seen)


def test_no_progress_callback_when_duration_unknown(tmp_path):
    factory = fake_model_factory([seg(0, 1, "a")], duration=0)
    seen = []
    audio = tmp_path / "a.m4a"
    transcribe_audio(audio, video_id=VID, on_progress=seen.append, model_factory=factory)
    assert seen == []


def test_end_to_end_with_fakes_and_temp_audio_is_deleted():
    audio_paths = []

    def factory(size, device, compute_type):
        class Model:
            def transcribe(self, path, **kwargs):
                audio_paths.append(Path(path))
                assert Path(path).exists()  # existe enquanto transcreve
                return iter([seg(0, 1, "oi")]), SimpleNamespace(language="pt", duration=1.0)

        return Model()

    status = []
    t = transcribe_with_whisper(
        VID, on_status=status.append, ydl_factory=FakeYDL, model_factory=factory
    )
    assert t.title == "Meu vídeo" and t.segments[0].text == "oi"
    assert not audio_paths[0].exists() and not audio_paths[0].parent.exists()
    assert any("Baixando" in m for m in status) and any("Whisper" in m for m in status)


def test_temp_audio_is_deleted_even_when_transcription_fails():
    seen = {}

    def factory(size, device, compute_type):
        class Model:
            def transcribe(self, path, **kwargs):
                seen["path"] = Path(path)
                raise RuntimeError("sem memória")

        return Model()

    with pytest.raises(RuntimeError):
        transcribe_with_whisper(VID, ydl_factory=FakeYDL, model_factory=factory)
    assert not seen["path"].parent.exists()


def test_missing_optional_package_explains_how_to_install():
    with pytest.raises(MissingDependency, match="requirements-whisper.txt"):
        _require("pacote_que_nao_existe_xyz")
