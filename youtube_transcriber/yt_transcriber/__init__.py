"""Transcrição de vídeos do YouTube: legendas oficiais primeiro, Whisper como plano B."""

from .errors import (
    InvalidVideoReference,
    MissingDependency,
    NetworkError,
    NoCaptionsAvailable,
    RequestBlockedError,
    TranscriberError,
    VideoNotAccessible,
)
from .models import Segment, Transcript, WhisperOptions
from .service import transcribe
from .urls import extract_video_id

__version__ = "0.1.0"

__all__ = [
    "InvalidVideoReference",
    "MissingDependency",
    "NetworkError",
    "NoCaptionsAvailable",
    "RequestBlockedError",
    "Segment",
    "TranscriberError",
    "Transcript",
    "VideoNotAccessible",
    "WhisperOptions",
    "extract_video_id",
    "transcribe",
]
