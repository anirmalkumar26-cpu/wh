"""Create a narrated Manim video from arbitrary text.

Examples:
    python ben01.py --text "Welcome to my video"
    python ben01.py --text-file script.txt --title "Lesson 1" --output media/lesson.mp4
    python ben01.py --text-file script.txt --highlight-sentences --quality h
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

from manim import (
    BLACK,
    BLUE,
    GREEN,
    LEFT,
    ORANGE,
    WHITE,
    DOWN,
    FadeIn,
    FadeOut,
    Rectangle,
    Scene,
    Text,
    UP,
    VGroup,
    config,
)


def _normalize_text(value: str) -> str:
    text = " ".join(value.split())
    if not text:
        raise ValueError("The input text cannot be empty.")
    return text


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _paginate_sentences(sentences: list[str], max_chars: int = 300) -> list[list[str]]:
    pages: list[list[str]] = []
    current: list[str] = []
    current_chars = 0

    for sentence in sentences:
        sentence_length = len(sentence)
        if current and current_chars + 1 + sentence_length > max_chars:
            pages.append(current)
            current = [sentence]
            current_chars = sentence_length
        else:
            current.append(sentence)
            current_chars += sentence_length + (1 if current_chars else 0)

    if current:
        pages.append(current)

    return pages or [sentences]


def make_speech(text: str, path: Path, engine: str, voice: str | None) -> Path:
    if engine == "gtts":
        try:
            from gtts import gTTS
        except ImportError as exc:
            raise RuntimeError("Install gTTS or use --engine pyttsx3.") from exc
        target = path.with_suffix(".mp3")
        gTTS(text=text, lang=voice or "en").save(str(target))
        return target

    try:
        import pyttsx3
    except ImportError as exc:
        raise RuntimeError("Install pyttsx3 if you want offline speech synthesis.") from exc

    speaker = pyttsx3.init()
    if voice:
        match = next(
            (
                item
                for item in speaker.getProperty("voices")
                if voice.lower() in str(item.id).lower() or voice.lower() in str(item.name).lower()
            ),
            None,
        )
        if match is None:
            raise ValueError(f"No pyttsx3 voice matched {voice!r}.")
        speaker.setProperty("voice", match.id)
    speaker.save_to_file(text, str(path))
    speaker.runAndWait()
    return path


def audio_duration(path: Path, text: str) -> float:
    if path.suffix.lower() == ".wav":
        with wave.open(str(path), "rb") as source:
            duration = source.getnframes() / source.getframerate()
    else:
        try:
            from mutagen.mp3 import MP3

            duration = float(MP3(str(path)).info.length)
        except ImportError:
            duration = 0.0
    return duration if duration > 0 else max(1.0, len(text.split()) / 2.5)


def srt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def write_subtitles(subtitles: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as output:
        for index, subtitle in enumerate(subtitles, start=1):
            output.write(
                f"{index}\n{srt_time(subtitle['start'])} --> {srt_time(subtitle['end'])}\n{subtitle['text']}\n\n"
            )


def build_subtitles(sentences: list[str], duration: float) -> list[dict[str, Any]]:
    weights = [max(1, len(sentence)) for sentence in sentences]
    total = sum(weights)
    current = 0.0
    result: list[dict[str, Any]] = []
    for sentence, weight in zip(sentences, weights):
        end = duration if sentence == sentences[-1] else current + duration * weight / total
        result.append({"text": sentence, "start": current, "end": end})
        current = end
    return result


def build_pages(sentences: list[str], subtitle_times: list[dict[str, Any]], chars_per_page: int = 300) -> list[dict[str, Any]]:
    groups = _paginate_sentences(sentences, max_chars=chars_per_page)
    pages: list[dict[str, Any]] = []
    sentence_index = 0

    for group in groups:
        page_sentences = list(group)
        start_index = sentence_index
        sentence_index += len(page_sentences)
        end_index = sentence_index - 1
        page_start = subtitle_times[start_index]["start"] if start_index < len(subtitle_times) else 0.0
        page_end = subtitle_times[end_index]["end"] if end_index < len(subtitle_times) else page_start
        pages.append(
            {
                "sentences": page_sentences,
                "subtitle": " ".join(page_sentences),
                "start": page_start,
                "end": page_end,
            }
        )

    return pages or [{"sentences": sentences, "subtitle": " ".join(sentences), "start": 0.0, "end": max(1.0, duration_from_text(sentences))}]


def duration_from_text(sentences: list[str]) -> float:
    return max(1.0, sum(max(1, len(s)) for s in sentences) / 12.0)


class TextVideoScene(Scene):
    """Display a title and paginated text cards with optional sentence highlighting."""

    def _card(self, sentences: list[str], page_number: int, total_pages: int, highlight_index: int | None = None) -> VGroup:
        frame = Rectangle(width=config.frame_width - 1.0, height=4.8, stroke_color=BLUE, stroke_width=2, fill_color=BLUE, fill_opacity=0.08)
        frame.to_edge(DOWN, buff=0.9)

        title = Text(f"Page {page_number}/{total_pages}", color=ORANGE, font_size=22)
        title.next_to(frame.get_top(), UP, buff=0.15)

        lines = VGroup()
        for index, sentence in enumerate(sentences):
            line = Text(sentence, color=GREEN if highlight_index is not None and index == highlight_index else WHITE, font_size=30)
            line.set_max_width(config.frame_width - 2.2)
            lines.add(line)
        lines.arrange(DOWN, aligned_edge=LEFT, buff=0.22)
        lines.move_to(frame.get_center())

        return VGroup(frame, title, lines)

    def construct(self) -> None:
        config_path = os.environ.get("TEXT_VIDEO_CONFIG")
        if not config_path:
            raise RuntimeError("TEXT_VIDEO_CONFIG is missing. Run the script via main() rather than importing the scene directly.")

        with Path(config_path).open("r", encoding="utf-8") as source:
            video: dict[str, Any] = json.load(source)

        self.camera.background_color = BLACK
        self.add_sound(video["audio_path"])

        title = Text(video["title"], color=WHITE, font_size=42)
        title.to_edge(UP)
        self.add(title)

        for page_index, page in enumerate(video["pages"]):
            highlight_index = 0 if video.get("highlight_sentences") and page["sentences"] else None
            card = self._card(page["sentences"], page_index + 1, len(video["pages"]), highlight_index)
            self.play(FadeIn(card), run_time=0.22)

            caption = Text(page["subtitle"], color=WHITE, font_size=28)
            caption.set_max_width(config.frame_width - 1.5)
            caption.to_edge(DOWN, buff=0.18)
            self.play(FadeIn(caption), run_time=0.12)

            self.wait(max(0.15, page["end"] - page["start"]))
            self.play(FadeOut(caption), run_time=0.12)
            self.play(FadeOut(card), run_time=0.22)


def _resolve_text(args: argparse.Namespace) -> str:
    if args.text is not None:
        return _normalize_text(args.text)
    if args.text_file is not None:
        path = Path(args.text_file)
        if not path.exists():
            raise FileNotFoundError(f"Text file not found: {path}")
        return _normalize_text(path.read_text(encoding="utf-8"))

    if sys.stdin.isatty():
        print("No --text or --text-file was provided. Enter the text to narrate.")
        print("Finish with a blank line or press Ctrl+D/Ctrl+Z to end input.")
        lines: list[str] = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if not line.strip() and lines:
                break
            lines.append(line)
        text = "\n".join(lines).strip()
        if not text:
            raise ValueError("No text was entered in interactive mode.")
        return _normalize_text(text)

    text = sys.stdin.read()
    if not text.strip():
        raise ValueError("No text was provided on stdin.")
    return _normalize_text(text)


def discover_mp4(output_dir: Path, stem: str) -> Path:
    candidates: list[Path] = []
    for candidate_dir in (output_dir, output_dir / "manim_media", output_dir / "manim_media" / "videos"):
        if candidate_dir.exists():
            candidates.extend(candidate_dir.rglob("*.mp4"))

    if not candidates:
        raise FileNotFoundError(
            f"Manim completed without producing a video in the expected output directory. Looked under: {output_dir}."
        )

    matching = [path for path in candidates if path.stem == stem or stem in path.name]
    chosen = max(matching or candidates, key=lambda item: item.stat().st_mtime)
    return chosen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--text", help="Text to narrate.")
    source.add_argument("--text-file", type=Path, help="UTF-8 text file to narrate.")
    parser.add_argument("--title", default="Narrated Text", help="Title displayed at the top of the video.")
    parser.add_argument("--output", type=Path, default=Path("media/narrated_text.mp4"), help="Output MP4 location.")
    parser.add_argument("--engine", choices=("pyttsx3", "gtts"), default="pyttsx3", help="Speech engine to use.")
    parser.add_argument("--voice", help="Voice id fragment for pyttsx3 or language code for gTTS.")
    parser.add_argument("--quality", default="m", help="Manim render quality flag, e.g. l, m, h, or p.")
    parser.add_argument("--keep-assets", action="store_true", help="Keep generated audio, subtitle, and JSON files.")
    parser.add_argument("--highlight-sentences", action="store_true", help="Highlight the current sentence in a card.")
    parser.add_argument("--chars-per-page", type=int, default=300, help="Approximate character budget per paginated text card.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.chars_per_page < 40:
        raise ValueError("--chars-per-page must be >= 40.")

    text = _resolve_text(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    asset_dir = Path(tempfile.mkdtemp(prefix="text_video_"))
    audio_path = asset_dir / ("narration.mp3" if args.engine == "gtts" else "narration.wav")
    subtitle_path = args.output.with_suffix(".srt")

    sentences = _split_sentences(text)
    duration = audio_duration(make_speech(text, audio_path, args.engine, args.voice), text)
    subtitle_times = build_subtitles(sentences, duration)
    write_subtitles(subtitle_times, subtitle_path)

    pages = build_pages(sentences, subtitle_times, chars_per_page=args.chars_per_page)
    config_path = asset_dir / "video.json"
    config_path.write_text(
        json.dumps(
            {
                "audio_path": str(audio_path),
                "title": args.title,
                "pages": pages,
                "highlight_sentences": bool(args.highlight_sentences),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    command = [
        sys.executable,
        "-m",
        "manim",
        f"-q{args.quality}",
        str(Path(__file__).resolve()),
        "TextVideoScene",
        "-o",
        args.output.stem,
        "--media_dir",
        str(args.output.parent / "manim_media"),
    ]
    environment = os.environ.copy()
    environment["TEXT_VIDEO_CONFIG"] = str(config_path)

    try:
        subprocess.run(command, check=True, env=environment, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        stdout = exc.stdout.strip() if exc.stdout else ""
        details = stderr or stdout or "No error details were returned."
        raise RuntimeError(f"Manim failed while rendering the video. Details: {details}") from exc

    rendered = discover_mp4(args.output.parent, args.output.stem)
    args.output.write_bytes(rendered.read_bytes())

    if not args.keep_assets:
        for item in (audio_path, config_path):
            item.unlink(missing_ok=True)
        subtitle_path.unlink(missing_ok=True)
        for path in sorted(asset_dir.iterdir(), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
        if asset_dir.exists():
            asset_dir.rmdir()

    print(f"Video: {args.output}")
    print(f"Subtitles: {subtitle_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
