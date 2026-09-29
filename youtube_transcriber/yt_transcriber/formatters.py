"""Renderizadores de saída: txt, srt, vtt, json e md."""

from __future__ import annotations

import json
import textwrap
from collections.abc import Callable

from .models import Transcript


def _hms_ms(seconds: float) -> tuple[int, int, int, int]:
    # Arredonda uma vez, em milissegundos inteiros. Formatar segundos float direto deixaria
    # 59.9996 virar "00:00:59,1000" em vez de "00:01:00,000".
    total = max(0, round(seconds * 1000))
    hours, rest = divmod(total, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, millis = divmod(rest, 1000)
    return hours, minutes, secs, millis


def srt_time(seconds: float) -> str:
    h, m, s, ms = _hms_ms(seconds)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def vtt_time(seconds: float) -> str:
    h, m, s, ms = _hms_ms(seconds)
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"


def clock(seconds: float) -> str:
    """HH:MM:SS truncado (o segundo em curso, como um player mostra)."""
    total = max(0, int(seconds))
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    return f"{h:02}:{m:02}:{s:02}"


def to_txt(t: Transcript, timestamps: bool = False) -> str:
    if timestamps:
        return "\n".join(f"[{clock(s.start)}] {s.text}" for s in t.segments) + "\n"
    return textwrap.fill(t.text, width=100) + "\n"


def to_srt(t: Transcript, timestamps: bool = False) -> str:
    blocks = [
        f"{i}\n{srt_time(s.start)} --> {srt_time(s.end)}\n{s.text}\n"
        for i, s in enumerate(t.segments, start=1)
    ]
    return "\n".join(blocks)


def to_vtt(t: Transcript, timestamps: bool = False) -> str:
    cues = [f"{vtt_time(s.start)} --> {vtt_time(s.end)}\n{s.text}\n" for s in t.segments]
    return "WEBVTT\n\n" + "\n".join(cues)


def to_json(t: Transcript, timestamps: bool = False) -> str:
    payload = {
        "video_id": t.video_id,
        "url": t.url,
        "title": t.title,
        "language": t.language,
        "source": t.source,
        "duration": round(t.duration, 3),
        "text": t.text,
        "segments": [
            {"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text} for s in t.segments
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


_SOURCE_LABEL = {
    "captions": "legenda do YouTube (criada pelo autor)",
    "captions-auto": "legenda automática do YouTube",
    "whisper": "Whisper (transcrição do áudio)",
}


def to_md(t: Transcript, timestamps: bool = False) -> str:
    head = [
        f"# {t.title or t.video_id}",
        "",
        f"- Vídeo: <{t.url}>",
        f"- Idioma: {t.language}",
        f"- Fonte: {_SOURCE_LABEL.get(t.source, t.source)}",
        "",
        "## Transcrição",
        "",
    ]
    # No Markdown cada trecho leva um link que abre o vídeo naquele instante.
    lines = [
        f"[{clock(s.start)}](https://youtu.be/{t.video_id}?t={int(s.start)}) {s.text}  "
        for s in t.segments
    ]
    return "\n".join(head + lines) + "\n"


Renderer = Callable[[Transcript, bool], str]

RENDERERS: dict[str, Renderer] = {
    "txt": to_txt,
    "srt": to_srt,
    "vtt": to_vtt,
    "json": to_json,
    "md": to_md,
}


def render(transcript: Transcript, fmt: str, timestamps: bool = False) -> str:
    try:
        renderer = RENDERERS[fmt]
    except KeyError:
        raise ValueError(f"Formato desconhecido: {fmt!r}. Use: {', '.join(RENDERERS)}") from None
    return renderer(transcript, timestamps)
