"""Interface de linha de comando: `yt-transcribe URL [URL ...]`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import service
from .errors import TranscriberError
from .formatters import RENDERERS, render
from .models import WhisperOptions
from .urls import extract_video_id

EPILOG = """exemplos:
  yt-transcribe https://youtu.be/dQw4w9WgXcQ
  yt-transcribe dQw4w9WgXcQ -f srt,txt -l pt,en
  yt-transcribe URL --stdout -f txt | wc -w
  yt-transcribe URL --method whisper --model medium --whisper-language pt
"""


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="yt-transcribe",
        description="Transcreve vídeos do YouTube (legendas oficiais; Whisper se não houver).",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("videos", nargs="+", metavar="URL_OU_ID", help="um ou mais vídeos")
    p.add_argument(
        "-f",
        "--format",
        default="txt",
        metavar="FMT",
        help=f"formato(s), separados por vírgula: {', '.join(RENDERERS)} (padrão: txt)",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        default="transcripts",
        metavar="DIR",
        help="pasta de saída (padrão: transcripts)",
    )
    p.add_argument(
        "--stdout",
        action="store_true",
        help="imprime na saída padrão em vez de gravar arquivo (1 vídeo, 1 formato)",
    )
    p.add_argument(
        "-l",
        "--lang",
        metavar="CODIGOS",
        help="idiomas da legenda em ordem de preferência, ex.: pt,en "
        "(padrão: a primeira legenda manual disponível)",
    )
    p.add_argument(
        "-m",
        "--method",
        choices=service.METHODS,
        default="auto",
        help="auto = legendas e, sem elas, Whisper (padrão)",
    )
    p.add_argument(
        "-t",
        "--timestamps",
        action="store_true",
        help="no formato txt, uma linha por trecho com marcação de tempo",
    )
    p.add_argument("--model", default="small", help="modelo Whisper (padrão: small)")
    p.add_argument("--device", default="auto", help="auto, cpu ou cuda (padrão: auto)")
    p.add_argument(
        "--whisper-language",
        metavar="COD",
        help="idioma falado no áudio, ex.: pt (padrão: detectar sozinho)",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="não mostra mensagens de andamento")
    return p


def _parse_formats(raw: str, parser: argparse.ArgumentParser) -> list[str]:
    formats = [f.strip().lower() for f in raw.split(",") if f.strip()]
    bad = [f for f in formats if f not in RENDERERS]
    if bad or not formats:
        parser.error(f"formato inválido: {', '.join(bad) or raw!r}. Use: {', '.join(RENDERERS)}")
    return list(dict.fromkeys(formats))  # sem repetidos, mantendo a ordem


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    formats = _parse_formats(args.format, parser)
    if args.stdout and (len(args.videos) != 1 or len(formats) != 1):
        parser.error("--stdout exige exatamente 1 vídeo e 1 formato")
    languages = [c.strip() for c in args.lang.split(",") if c.strip()] if args.lang else None

    def status(msg: str) -> None:
        if not args.quiet:
            _err(msg)

    def progress(fraction: float) -> None:
        if not args.quiet and sys.stderr.isatty():
            end = "\n" if fraction >= 1 else ""
            print(f"\r  transcrevendo: {fraction:4.0%}", end=end, file=sys.stderr, flush=True)

    out_dir = Path(args.output_dir)
    failures = 0
    try:
        for ref in args.videos:
            try:
                video_id = extract_video_id(ref)
                status(f"[{video_id}]")
                transcript = service.transcribe(
                    video_id,
                    method=args.method,
                    languages=languages,
                    whisper=WhisperOptions(model=args.model, device=args.device),
                    whisper_language=args.whisper_language,
                    on_status=status,
                    on_progress=progress,
                )
            except TranscriberError as exc:
                failures += 1
                _err(f"erro em '{ref}': {exc}")
                continue

            if args.stdout:
                sys.stdout.write(render(transcript, formats[0], args.timestamps))
                continue

            out_dir.mkdir(parents=True, exist_ok=True)
            for fmt in formats:
                path = out_dir / f"{transcript.video_id}.{fmt}"
                path.write_text(render(transcript, fmt, args.timestamps), encoding="utf-8")
                print(path)  # stdout só com os caminhos gravados: fácil de encadear em scripts
            status(
                f"  {len(transcript.segments)} trechos · idioma {transcript.language} "
                f"· fonte: {transcript.source}"
            )
    except KeyboardInterrupt:
        _err("\ninterrompido.")
        return 130

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
