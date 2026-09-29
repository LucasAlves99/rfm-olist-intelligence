import json

import pytest

from yt_transcriber import cli, service
from yt_transcriber.errors import NoCaptionsAvailable
from yt_transcriber.formatters import render
from yt_transcriber.models import Segment, Transcript, WhisperOptions

A, B = "dQw4w9WgXcQ", "9bZkp7q19f0"


def make(video_id):
    return Transcript(video_id, "pt", "captions", [Segment(0, 1, f"fala de {video_id}")])


@pytest.fixture
def calls(monkeypatch):
    log = []

    def fake(video_id, **kwargs):
        log.append((video_id, kwargs))
        return make(video_id)

    monkeypatch.setattr(service, "transcribe", fake)
    return log


def test_writes_one_file_per_format_and_prints_the_paths(tmp_path, calls, capsys):
    code = cli.main([A, "-f", "txt,srt", "-o", str(tmp_path), "-q"])
    out = capsys.readouterr()
    assert code == 0
    assert (tmp_path / f"{A}.txt").read_text(encoding="utf-8") == render(make(A), "txt")
    assert (tmp_path / f"{A}.srt").exists()
    assert out.out.split() == [str(tmp_path / f"{A}.txt"), str(tmp_path / f"{A}.srt")]
    assert out.err == ""  # -q: nada de andamento


def test_accepts_urls_and_creates_the_output_dir(tmp_path, calls):
    target = tmp_path / "a" / "b"
    assert cli.main([f"https://youtu.be/{A}?t=5", "-o", str(target), "-q"]) == 0
    assert (target / f"{A}.txt").exists()
    assert calls[0][0] == A


def test_batch_continues_after_a_failure_and_exit_code_reflects_it(tmp_path, monkeypatch, capsys):
    def fake(video_id, **kwargs):
        if video_id == A:
            raise NoCaptionsAvailable("sem legenda")
        return make(video_id)

    monkeypatch.setattr(service, "transcribe", fake)
    code = cli.main([A, B, "-o", str(tmp_path), "-q"])
    assert code == 1
    assert not (tmp_path / f"{A}.txt").exists()
    assert (tmp_path / f"{B}.txt").exists()  # o segundo saiu mesmo com o primeiro falhando
    assert "sem legenda" in capsys.readouterr().err


def test_invalid_reference_is_reported_without_calling_the_service(tmp_path, calls, capsys):
    code = cli.main(["isto-nao-e-video", "-o", str(tmp_path)])
    assert code == 1 and calls == []
    assert "isto-nao-e-video" in capsys.readouterr().err


def test_stdout_mode_prints_only_the_transcript(calls, capsys, tmp_path):
    assert cli.main([A, "--stdout", "-f", "json", "-q"]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["video_id"] == A
    assert not list(tmp_path.iterdir())


def test_stdout_with_several_videos_is_a_usage_error(calls):
    with pytest.raises(SystemExit) as exc:
        cli.main([A, B, "--stdout"])
    assert exc.value.code == 2 and calls == []


def test_stdout_with_several_formats_is_a_usage_error(calls):
    with pytest.raises(SystemExit) as exc:
        cli.main([A, "--stdout", "-f", "txt,srt"])
    assert exc.value.code == 2


def test_unknown_format_is_a_usage_error(calls, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([A, "-f", "txt,docx"])
    assert exc.value.code == 2 and calls == []
    assert "docx" in capsys.readouterr().err


def test_duplicate_formats_are_written_once(tmp_path, calls, capsys):
    cli.main([A, "-f", "txt,TXT,txt", "-o", str(tmp_path), "-q"])
    assert capsys.readouterr().out.split() == [str(tmp_path / f"{A}.txt")]


def test_options_are_forwarded_to_the_service(tmp_path, calls):
    cli.main(
        [
            A,
            "-o",
            str(tmp_path),
            "-q",
            "-l",
            "pt, en",
            "-m",
            "whisper",
            "--model",
            "tiny",
            "--device",
            "cpu",
            "--whisper-language",
            "pt",
        ]
    )
    _, kwargs = calls[0]
    assert kwargs["languages"] == ["pt", "en"]
    assert kwargs["method"] == "whisper"
    assert kwargs["whisper"] == WhisperOptions(model="tiny", device="cpu")
    assert kwargs["whisper_language"] == "pt"


def test_defaults(tmp_path, calls):
    cli.main([A, "-o", str(tmp_path), "-q"])
    _, kwargs = calls[0]
    assert kwargs["languages"] is None and kwargs["method"] == "auto"
    assert kwargs["whisper"] == WhisperOptions() and kwargs["whisper_language"] is None


def test_timestamps_flag_reaches_the_txt_renderer(tmp_path, calls):
    cli.main([A, "-t", "-o", str(tmp_path), "-q"])
    assert (tmp_path / f"{A}.txt").read_text(encoding="utf-8") == "[00:00:00] fala de " + A + "\n"


def test_status_messages_go_to_stderr_not_stdout(tmp_path, monkeypatch, capsys):
    def fake(video_id, on_status=None, **kwargs):
        on_status("Buscando legendas...")
        return make(video_id)

    monkeypatch.setattr(service, "transcribe", fake)
    cli.main([A, "-o", str(tmp_path)])
    out = capsys.readouterr()
    assert "Buscando legendas..." in out.err
    assert "Buscando" not in out.out


def test_ctrl_c_exits_130(monkeypatch, capsys):
    def fake(video_id, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(service, "transcribe", fake)
    assert cli.main([A, "-q"]) == 130
