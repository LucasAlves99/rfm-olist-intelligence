import pytest

from yt_transcriber.models import Segment, Transcript


@pytest.fixture
def transcript() -> Transcript:
    return Transcript(
        video_id="dQw4w9WgXcQ",
        language="pt",
        source="captions",
        title="Título com acentuação",
        segments=[
            Segment(0.0, 2.5, "Olá, tudo bem?"),
            Segment(2.5, 5.0, "Hoje vamos falar de ação e coração."),
            Segment(3661.5, 3665.0, "Já passou uma hora."),
        ],
    )
