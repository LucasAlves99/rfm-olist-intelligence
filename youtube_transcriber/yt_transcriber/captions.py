"""Backend 1: legendas do próprio YouTube (rápido, sem baixar áudio, sem GPU)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

import requests
from youtube_transcript_api import (
    AgeRestricted,
    InvalidVideoId,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
    YouTubeTranscriptApi,
    YouTubeTranscriptApiException,
)

from .errors import (
    NetworkError,
    NoCaptionsAvailable,
    RequestBlockedError,
    TranscriberError,
    VideoNotAccessible,
)
from .models import Segment, Transcript


def _to_segments(snippets: Iterable[Any]) -> list[Segment]:
    raw = [(s.start, s.start + s.duration, " ".join(s.text.split())) for s in snippets]
    raw = [r for r in raw if r[2]]

    segments: list[Segment] = []
    for i, (start, end, text) in enumerate(raw):
        # As legendas do YouTube se sobrepõem (o trecho seguinte começa antes do atual
        # terminar). Cortar o fim evita cues sobrepostos em .srt/.vtt.
        if i + 1 < len(raw) and start < raw[i + 1][0] < end:
            end = raw[i + 1][0]
        segments.append(Segment(start, end, text))
    return segments


def _describe(transcripts: Iterable[Any]) -> str:
    return ", ".join(
        f"{t.language_code} ({'automática' if t.is_generated else 'manual'})" for t in transcripts
    )


def _pick(transcript_list: Any, languages: Sequence[str] | None) -> Any:
    if languages:
        try:
            # Respeita a ordem dos idiomas; dentro de cada um, manual antes de automática.
            return transcript_list.find_transcript(list(languages))
        except NoTranscriptFound:
            available = _describe(transcript_list)
            msg = f"Nenhuma legenda em {', '.join(languages)}."
            if available:
                msg += f" Disponíveis: {available}."
            raise NoCaptionsAvailable(msg) from None

    items = list(transcript_list)
    if not items:
        raise NoCaptionsAvailable("O vídeo não tem nenhuma legenda.")
    manual = [t for t in items if not t.is_generated]
    return (manual or items)[0]


def _translate_error(exc: YouTubeTranscriptApiException, video_id: str) -> TranscriberError:
    if isinstance(exc, TranscriptsDisabled):
        return NoCaptionsAvailable("O vídeo tem as legendas desativadas.")
    if isinstance(exc, RequestBlocked):  # cobre também IpBlocked (subclasse)
        return RequestBlockedError(
            "O YouTube bloqueou a requisição (IPs de nuvem/datacenter costumam ser bloqueados). "
            "Tente de uma rede residencial ou configure um proxy."
        )
    if isinstance(exc, AgeRestricted):
        return VideoNotAccessible("Vídeo restrito por idade (exige login).")
    if isinstance(exc, VideoUnavailable | VideoUnplayable | InvalidVideoId):
        return VideoNotAccessible(f"Vídeo indisponível ({type(exc).__name__}).")
    return TranscriberError(f"Falha ao obter legendas ({type(exc).__name__}).")


def fetch_captions(
    video_id: str,
    languages: Sequence[str] | None = None,
    *,
    api: Any | None = None,
) -> Transcript:
    """Busca a legenda. `languages=None` pega a primeira manual, senão a primeira automática."""
    api = api or YouTubeTranscriptApi()
    try:
        chosen = _pick(api.list(video_id), languages)
        fetched = chosen.fetch()
    except YouTubeTranscriptApiException as exc:
        raise _translate_error(exc, video_id) from exc
    except requests.exceptions.RequestException as exc:
        # A biblioteca só embrulha erros de resposta do YouTube; falha de conexão sobe crua.
        raise NetworkError(
            f"Não consegui falar com o YouTube ({type(exc).__name__}). "
            "Verifique a conexão e o proxy."
        ) from exc

    segments = _to_segments(fetched.snippets)
    if not segments:
        raise NoCaptionsAvailable("A legenda encontrada está vazia.")

    return Transcript(
        video_id=video_id,
        language=fetched.language_code,
        source="captions-auto" if fetched.is_generated else "captions",
        segments=segments,
    )
