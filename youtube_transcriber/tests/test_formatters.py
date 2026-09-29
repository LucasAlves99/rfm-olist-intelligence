import json
import re

import pytest

from yt_transcriber.formatters import (
    RENDERERS,
    clock,
    render,
    srt_time,
    to_json,
    to_md,
    to_srt,
    to_txt,
    to_vtt,
    vtt_time,
)
from yt_transcriber.models import Transcript


@pytest.mark.parametrize(
    "seconds, srt, vtt",
    [
        (0, "00:00:00,000", "00:00:00.000"),
        (1.5, "00:00:01,500", "00:00:01.500"),
        (59.9996, "00:01:00,000", "00:01:00.000"),  # arredonda uma vez só, sem "59,1000"
        (3661.5, "01:01:01,500", "01:01:01.500"),
        (100 * 3600 + 1, "100:00:01,000", "100:00:01.000"),
        (-3, "00:00:00,000", "00:00:00.000"),
    ],
)
def test_timestamps(seconds, srt, vtt):
    assert srt_time(seconds) == srt
    assert vtt_time(seconds) == vtt


def test_clock_truncates_like_a_player():
    assert clock(3661.9) == "01:01:01"
    assert clock(0.99) == "00:00:00"


def test_srt_structure(transcript):
    out = to_srt(transcript)
    blocks = out.strip().split("\n\n")
    assert len(blocks) == 3
    for i, block in enumerate(blocks, start=1):
        lines = block.split("\n")
        assert lines[0] == str(i)
        assert re.fullmatch(r"\d\d:\d\d:\d\d,\d{3} --> \d\d:\d\d:\d\d,\d{3}", lines[1])
        assert lines[2]
    assert "00:00:00,000 --> 00:00:02,500\nOlá, tudo bem?" in out


def test_vtt_structure(transcript):
    out = to_vtt(transcript)
    assert out.startswith("WEBVTT\n\n")
    assert "00:00:02.500 --> 00:00:05.000" in out
    assert "," not in re.findall(r"\d\d:\d\d:\d\d.\d{3} --> \S+", out)[0]


def test_json_roundtrip_keeps_accents(transcript):
    raw = to_json(transcript)
    assert "ação" in raw  # ensure_ascii=False: legível, não \u00e7
    data = json.loads(raw)
    assert data["video_id"] == "dQw4w9WgXcQ"
    assert data["title"] == "Título com acentuação"
    assert data["language"] == "pt"
    assert data["source"] == "captions"
    assert data["duration"] == 3665.0
    assert len(data["segments"]) == 3
    assert data["segments"][1] == {"start": 2.5, "end": 5.0, "text": transcript.segments[1].text}
    assert data["text"] == transcript.text


def test_md_links_jump_to_the_moment(transcript):
    out = to_md(transcript)
    assert out.startswith("# Título com acentuação\n")
    assert "[01:01:01](https://youtu.be/dQw4w9WgXcQ?t=3661) Já passou uma hora." in out
    assert "- Fonte: legenda do YouTube (criada pelo autor)" in out


def test_md_falls_back_to_video_id_when_no_title(transcript):
    transcript.title = None
    assert to_md(transcript).startswith("# dQw4w9WgXcQ\n")


def test_txt_plain_is_wrapped_prose(transcript):
    out = to_txt(transcript)
    assert out.endswith("\n")
    assert all(len(line) <= 100 for line in out.splitlines())
    assert " ".join(out.split()) == transcript.text


def test_txt_with_timestamps_is_one_line_per_segment(transcript):
    lines = to_txt(transcript, timestamps=True).splitlines()
    assert lines == [
        "[00:00:00] Olá, tudo bem?",
        "[00:00:02] Hoje vamos falar de ação e coração.",
        "[01:01:01] Já passou uma hora.",
    ]


@pytest.mark.parametrize("fmt", sorted(RENDERERS))
def test_every_format_survives_an_empty_transcript(fmt):
    empty = Transcript(video_id="dQw4w9WgXcQ", language="en", source="whisper")
    assert isinstance(render(empty, fmt), str)


def test_unknown_format_is_a_clear_error(transcript):
    with pytest.raises(ValueError, match="Formato desconhecido"):
        render(transcript, "docx")
