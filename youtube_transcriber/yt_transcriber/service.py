"""Orquestra os dois backends: legendas primeiro, Whisper só se não houver legenda."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .captions import fetch_captions
from .errors import NoCaptionsAvailable
from .models import Transcript, WhisperOptions
from .whisper_backend import transcribe_with_whisper

METHODS = ("auto", "captions", "whisper")


def transcribe(
    video_id: str,
    *,
    method: str = "auto",
    languages: Sequence[str] | None = None,
    whisper: WhisperOptions | None = None,
    whisper_language: str | None = None,
    on_status: Callable[[str], None] | None = None,
    on_progress: Callable[[float], None] | None = None,
    captions_fn: Callable[..., Transcript] = fetch_captions,
    whisper_fn: Callable[..., Transcript] = transcribe_with_whisper,
) -> Transcript:
    """`auto` tenta legendas e cai para Whisper; `captions` e `whisper` usam só um backend.

    Só `NoCaptionsAvailable` aciona o plano B. Vídeo indisponível ou bloqueio do YouTube
    não têm remédio no Whisper (o áudio vem do mesmo lugar), então esses erros sobem direto.
    """
    if method not in METHODS:
        raise ValueError(f"method deve ser um de {METHODS}, recebi {method!r}")
    say = on_status or (lambda _msg: None)

    if method in ("auto", "captions"):
        say("Buscando legendas do YouTube...")
        try:
            return captions_fn(video_id, languages)
        except NoCaptionsAvailable as exc:
            if method == "captions":
                raise
            say(f"{exc} Usando Whisper (mais lento).")

    return whisper_fn(
        video_id,
        language=whisper_language,
        options=whisper or WhisperOptions(),
        on_status=say,
        on_progress=on_progress,
    )
