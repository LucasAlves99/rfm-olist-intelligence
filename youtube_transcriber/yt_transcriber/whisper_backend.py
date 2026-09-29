"""Backend 2 (plano B): baixa o áudio com yt-dlp e transcreve localmente com faster-whisper.

Só é usado quando o vídeo não tem legenda. É bem mais lento que o backend de legendas e
precisa dos pacotes opcionais em requirements-whisper.txt.
"""

from __future__ import annotations

import importlib
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .errors import MissingDependency, TranscriberError, VideoNotAccessible
from .models import Segment, Transcript, WhisperOptions

StatusFn = Callable[[str], None]
ProgressFn = Callable[[float], None]


def _require(module: str) -> Any:
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise MissingDependency(
            f"O pacote '{module}' não está instalado. "
            "Para usar o Whisper: pip install -r requirements-whisper.txt"
        ) from exc


def download_audio(
    video_id: str, dest_dir: Path, *, ydl_factory: Callable[..., Any] | None = None
) -> tuple[Path, str | None]:
    """Baixa só o áudio (sem converter, então não precisa de ffmpeg). Devolve (arquivo, título)."""
    factory = ydl_factory or _require("yt_dlp").YoutubeDL
    options = {
        "format": "bestaudio/best",
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with factory(options) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
            return Path(ydl.prepare_filename(info)), info.get("title")
    except TranscriberError:
        raise
    except Exception as exc:  # yt-dlp levanta vários tipos (DownloadError, ExtractorError, OSError)
        raise VideoNotAccessible(f"Não consegui baixar o áudio ({type(exc).__name__}).") from exc


def transcribe_audio(
    audio: Path,
    *,
    video_id: str,
    title: str | None = None,
    language: str | None = None,
    options: WhisperOptions | None = None,
    on_progress: ProgressFn | None = None,
    model_factory: Callable[..., Any] | None = None,
) -> Transcript:
    options = options or WhisperOptions()
    factory = model_factory or _require("faster_whisper").WhisperModel
    model = factory(options.model, device=options.device, compute_type=options.compute_type)
    # vad_filter descarta silêncio/música: reduz muito as "alucinações" do Whisper nesses trechos.
    stream, info = model.transcribe(str(audio), language=language, vad_filter=True, beam_size=5)

    segments: list[Segment] = []
    for seg in stream:  # gerador: a transcrição de fato acontece durante esta iteração
        text = " ".join(seg.text.split())
        if text:
            segments.append(Segment(seg.start, seg.end, text))
        if on_progress and info.duration:
            on_progress(min(seg.end / info.duration, 1.0))

    return Transcript(
        video_id=video_id,
        language=info.language,
        source="whisper",
        segments=segments,
        title=title,
    )


def transcribe_with_whisper(
    video_id: str,
    *,
    language: str | None = None,
    options: WhisperOptions | None = None,
    on_status: StatusFn | None = None,
    on_progress: ProgressFn | None = None,
    ydl_factory: Callable[..., Any] | None = None,
    model_factory: Callable[..., Any] | None = None,
) -> Transcript:
    say = on_status or (lambda _msg: None)
    options = options or WhisperOptions()
    with tempfile.TemporaryDirectory(prefix="yt-transcriber-") as tmp:  # áudio some ao terminar
        say("Baixando o áudio...")
        audio, title = download_audio(video_id, Path(tmp), ydl_factory=ydl_factory)
        say(f"Transcrevendo com Whisper '{options.model}' (na primeira vez baixa o modelo)...")
        return transcribe_audio(
            audio,
            video_id=video_id,
            title=title,
            language=language,
            options=options,
            on_progress=on_progress,
            model_factory=model_factory,
        )
