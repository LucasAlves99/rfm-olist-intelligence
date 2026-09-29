import pytest
import requests
from youtube_transcript_api import (
    AgeRestricted,
    InvalidVideoId,
    IpBlocked,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)
from youtube_transcript_api._transcripts import (
    FetchedTranscript,
    FetchedTranscriptSnippet,
    Transcript,
    TranscriptList,
)

from yt_transcriber.captions import fetch_captions
from yt_transcriber.errors import (
    NetworkError,
    NoCaptionsAvailable,
    RequestBlockedError,
    TranscriberError,
    VideoNotAccessible,
)

VID = "dQw4w9WgXcQ"


def snip(text, start, duration):
    return FetchedTranscriptSnippet(text=text, start=start, duration=duration)


class FakeTranscript(Transcript):
    """Transcript real da biblioteca; só o fetch() (que faria HTTP) é substituído."""

    def __init__(self, code, generated, snippets=None, fetch_error=None):
        super().__init__(
            http_client=None,
            video_id=VID,
            url="",
            language=code.upper(),
            language_code=code,
            is_generated=generated,
            translation_languages=[],
        )
        self._snippets = snippets if snippets is not None else [snip(f"texto {code}", 0, 1)]
        self._fetch_error = fetch_error

    def fetch(self, preserve_formatting=False):
        if self._fetch_error:
            raise self._fetch_error
        return FetchedTranscript(
            snippets=self._snippets,
            video_id=VID,
            language=self.language,
            language_code=self.language_code,
            is_generated=self.is_generated,
        )


class FakeApi:
    def __init__(self, *transcripts, list_error=None):
        manual = {t.language_code: t for t in transcripts if not t.is_generated}
        generated = {t.language_code: t for t in transcripts if t.is_generated}
        self._list = TranscriptList(VID, manual, generated, [])
        self._list_error = list_error

    def list(self, video_id):
        if self._list_error:
            raise self._list_error
        return self._list


def test_without_languages_prefers_manual_over_automatic():
    api = FakeApi(FakeTranscript("en", True), FakeTranscript("pt", False))
    t = fetch_captions(VID, api=api)
    assert (t.language, t.source) == ("pt", "captions")
    assert t.segments[0].text == "texto pt"


def test_without_languages_takes_automatic_when_no_manual_exists():
    t = fetch_captions(VID, api=FakeApi(FakeTranscript("en", True)))
    assert (t.language, t.source) == ("en", "captions-auto")


def test_language_order_wins_over_manual_vs_automatic():
    # Quem pediu "pt,en" prefere pt automática a en manual: a ordem dos idiomas manda.
    api = FakeApi(FakeTranscript("en", False), FakeTranscript("pt", True))
    t = fetch_captions(VID, ["pt", "en"], api=api)
    assert (t.language, t.source) == ("pt", "captions-auto")


def test_within_one_language_manual_beats_automatic():
    manual = FakeTranscript("pt", False, [snip("manual", 0, 1)])
    auto = FakeTranscript("pt", True, [snip("auto", 0, 1)])
    # As duas coexistem só em listas separadas; a manual deve vencer.
    api = FakeApi(auto, manual)
    assert fetch_captions(VID, ["pt"], api=api).segments[0].text == "manual"


def test_falls_through_to_the_second_language():
    t = fetch_captions(VID, ["fr", "en"], api=FakeApi(FakeTranscript("en", False)))
    assert t.language == "en"


def test_no_requested_language_lists_what_exists():
    api = FakeApi(FakeTranscript("en", False), FakeTranscript("es", True))
    with pytest.raises(NoCaptionsAvailable) as exc:
        fetch_captions(VID, ["pt"], api=api)
    msg = str(exc.value)
    assert "pt" in msg and "en (manual)" in msg and "es (automática)" in msg


def test_video_with_no_captions_at_all():
    with pytest.raises(NoCaptionsAvailable, match="nenhuma legenda"):
        fetch_captions(VID, api=FakeApi())


def test_overlapping_cues_are_clamped_and_text_is_cleaned():
    snippets = [
        snip("primeira\nlinha", 0.0, 4.0),  # termina em 4.0, mas a próxima começa em 2.0
        snip("segunda", 2.0, 3.0),
        snip("   ", 5.0, 1.0),  # só espaço: descartada
        snip("terceira", 6.0, 2.0),
    ]
    t = fetch_captions(VID, api=FakeApi(FakeTranscript("pt", False, snippets)))
    assert [(s.start, s.end, s.text) for s in t.segments] == [
        (0.0, 2.0, "primeira linha"),
        (2.0, 5.0, "segunda"),
        (6.0, 8.0, "terceira"),
    ]


def test_clamp_never_extends_a_cue_across_a_gap():
    snippets = [snip("a", 0.0, 1.0), snip("b", 5.0, 1.0)]
    t = fetch_captions(VID, api=FakeApi(FakeTranscript("pt", False, snippets)))
    assert t.segments[0].end == 1.0  # o silêncio entre 1.0 e 5.0 continua existindo


def test_empty_caption_is_treated_as_missing():
    api = FakeApi(FakeTranscript("pt", False, [snip("  ", 0, 1)]))
    with pytest.raises(NoCaptionsAvailable, match="vazia"):
        fetch_captions(VID, api=api)


@pytest.mark.parametrize(
    "error, expected",
    [
        (TranscriptsDisabled(VID), NoCaptionsAvailable),
        (IpBlocked(VID), RequestBlockedError),
        (RequestBlocked(VID), RequestBlockedError),
        (AgeRestricted(VID), VideoNotAccessible),
        (VideoUnavailable(VID), VideoNotAccessible),
        (InvalidVideoId(VID), VideoNotAccessible),
    ],
)
def test_library_errors_become_ours_when_listing(error, expected):
    with pytest.raises(expected):
        fetch_captions(VID, api=FakeApi(list_error=error))


def test_errors_raised_by_fetch_are_translated_too():
    api = FakeApi(FakeTranscript("pt", False, fetch_error=IpBlocked(VID)))
    with pytest.raises(RequestBlockedError):
        fetch_captions(VID, api=api)


def test_blocked_message_is_actionable():
    with pytest.raises(RequestBlockedError, match="proxy"):
        fetch_captions(VID, api=FakeApi(list_error=IpBlocked(VID)))


def test_only_no_captions_triggers_the_fallback_signal():
    # A ordem importa para o service: bloqueio e indisponibilidade NÃO são NoCaptionsAvailable.
    for error in (IpBlocked(VID), VideoUnavailable(VID), AgeRestricted(VID)):
        with pytest.raises(TranscriberError) as exc:
            fetch_captions(VID, api=FakeApi(list_error=error))
        assert not isinstance(exc.value, NoCaptionsAvailable)


def test_manual_is_preferred_even_if_the_library_lists_automatic_first():
    # Hoje a biblioteca itera manuais antes; não dependemos dessa ordem interna dela.
    class AutomaticFirst(list):
        pass

    listing = AutomaticFirst([FakeTranscript("en", True), FakeTranscript("pt", False)])

    class Api:
        def list(self, video_id):
            return listing

    t = fetch_captions(VID, api=Api())
    assert (t.language, t.source) == ("pt", "captions")


@pytest.mark.parametrize(
    "error",
    [
        requests.exceptions.ConnectionError("dns"),
        requests.exceptions.ProxyError("Tunnel connection failed: 403 Forbidden"),
        requests.exceptions.Timeout("lento"),
    ],
)
def test_connection_failures_become_a_network_error_not_a_traceback(error):
    # A biblioteca só embrulha erros do YouTube; falha de conexão sobe como `requests` cru.
    with pytest.raises(NetworkError, match="conexão") as exc:
        fetch_captions(VID, api=FakeApi(list_error=error))
    assert type(error).__name__ in str(exc.value)
    assert exc.value.__cause__ is error  # causa original preservada para depuração


def test_connection_failure_during_fetch_is_translated_too():
    api = FakeApi(FakeTranscript("pt", False, fetch_error=requests.exceptions.ConnectionError()))
    with pytest.raises(NetworkError):
        fetch_captions(VID, api=api)
