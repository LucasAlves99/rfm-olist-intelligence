import pytest

from yt_transcriber.errors import (
    NetworkError,
    NoCaptionsAvailable,
    RequestBlockedError,
    VideoNotAccessible,
)
from yt_transcriber.models import Segment, Transcript, WhisperOptions
from yt_transcriber.service import transcribe

VID = "dQw4w9WgXcQ"


def make(source):
    return Transcript(VID, "pt", source, [Segment(0, 1, "oi")])


class Spy:
    """Registra chamadas e devolve/levanta o configurado."""

    def __init__(self, result=None, error=None):
        self.calls = []
        self._result, self._error = result, error

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self._error:
            raise self._error
        return self._result


def test_auto_uses_captions_and_never_touches_whisper():
    captions, whisper = Spy(make("captions")), Spy(make("whisper"))
    t = transcribe(VID, captions_fn=captions, whisper_fn=whisper)
    assert t.source == "captions"
    assert len(captions.calls) == 1 and whisper.calls == []


def test_auto_falls_back_to_whisper_when_there_are_no_captions():
    captions = Spy(error=NoCaptionsAvailable("Sem legenda."))
    whisper = Spy(make("whisper"))
    status = []
    t = transcribe(VID, captions_fn=captions, whisper_fn=whisper, on_status=status.append)
    assert t.source == "whisper"
    assert any("Sem legenda." in m and "Whisper" in m for m in status)


@pytest.mark.parametrize(
    "error",
    [RequestBlockedError("bloqueado"), VideoNotAccessible("privado"), NetworkError("sem rede")],
)
def test_auto_does_not_fall_back_on_errors_whisper_cannot_fix(error):
    whisper = Spy(make("whisper"))
    with pytest.raises(type(error)):
        transcribe(VID, captions_fn=Spy(error=error), whisper_fn=whisper)
    assert whisper.calls == []


def test_captions_only_reraises_instead_of_falling_back():
    whisper = Spy(make("whisper"))
    with pytest.raises(NoCaptionsAvailable):
        transcribe(
            VID,
            method="captions",
            captions_fn=Spy(error=NoCaptionsAvailable("x")),
            whisper_fn=whisper,
        )
    assert whisper.calls == []


def test_whisper_only_skips_captions():
    captions, whisper = Spy(make("captions")), Spy(make("whisper"))
    t = transcribe(VID, method="whisper", captions_fn=captions, whisper_fn=whisper)
    assert t.source == "whisper"
    assert captions.calls == []


def test_languages_go_to_captions_and_whisper_settings_go_to_whisper():
    captions = Spy(error=NoCaptionsAvailable("x"))
    whisper = Spy(make("whisper"))
    opts = WhisperOptions(model="medium", device="cpu")
    transcribe(
        VID,
        languages=["pt", "en"],
        whisper=opts,
        whisper_language="pt",
        captions_fn=captions,
        whisper_fn=whisper,
    )
    assert captions.calls[0][0] == (VID, ["pt", "en"])
    _, kwargs = whisper.calls[0]
    assert kwargs["options"] == opts and kwargs["language"] == "pt"


def test_captions_languages_are_not_used_as_whisper_language():
    # Pediu legenda "pt" mas o vídeo só tem "en": forçar pt no Whisper geraria lixo.
    whisper = Spy(make("whisper"))
    transcribe(
        VID,
        languages=["pt"],
        captions_fn=Spy(error=NoCaptionsAvailable("x")),
        whisper_fn=whisper,
    )
    assert whisper.calls[0][1]["language"] is None


def test_default_whisper_options_when_none_given():
    whisper = Spy(make("whisper"))
    transcribe(VID, method="whisper", whisper_fn=whisper)
    assert whisper.calls[0][1]["options"] == WhisperOptions()


def test_unknown_method_is_rejected():
    with pytest.raises(ValueError, match="method"):
        transcribe(VID, method="magia")
