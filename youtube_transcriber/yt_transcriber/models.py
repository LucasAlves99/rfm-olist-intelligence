from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Segment:
    """Um trecho falado: início e fim em segundos, texto já sem quebras de linha."""

    start: float
    end: float
    text: str


@dataclass
class Transcript:
    video_id: str
    language: str
    source: str  # "captions" (manual) | "captions-auto" (gerada pelo YouTube) | "whisper"
    segments: list[Segment] = field(default_factory=list)
    title: str | None = None

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments)

    @property
    def duration(self) -> float:
        return self.segments[-1].end if self.segments else 0.0

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


@dataclass(frozen=True)
class WhisperOptions:
    model: str = "small"
    device: str = "auto"
    compute_type: str = "default"
