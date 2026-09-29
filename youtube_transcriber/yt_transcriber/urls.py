"""Extrai o ID de 11 caracteres de qualquer forma comum de referenciar um vídeo."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from .errors import InvalidVideoReference

_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "www.youtube-nocookie.com",
    "youtube-nocookie.com",
}
_SHORT_HOSTS = {"youtu.be", "www.youtu.be"}
_PATH_PREFIXES = {"embed", "shorts", "live", "v"}


def extract_video_id(reference: str) -> str:
    """Aceita ID puro, watch?v=, youtu.be/, /shorts/, /embed/, /live/, com ou sem esquema.

    O host é validado de propósito: o ID acaba virando nome de arquivo e parte de uma URL,
    então uma URL de outro domínio não pode passar só por "parecer" ter um ID.
    """
    ref = reference.strip()
    if _ID.match(ref):
        return ref

    parsed = urlparse(ref if "://" in ref else f"https://{ref}")
    host = (parsed.hostname or "").lower()
    parts = [p for p in parsed.path.split("/") if p]

    candidate: str | None = None
    if host in _SHORT_HOSTS:
        candidate = parts[0] if parts else None
    elif host in _YOUTUBE_HOSTS:
        if parsed.path.rstrip("/") == "/watch":
            candidate = (parse_qs(parsed.query).get("v") or [None])[0]
        elif len(parts) >= 2 and parts[0] in _PATH_PREFIXES:
            candidate = parts[1]

    if candidate and _ID.match(candidate):
        return candidate
    raise InvalidVideoReference(f"Não reconheci '{reference}' como um vídeo do YouTube.")
