"""Generate a narrated video from arbitrary text using Manim.

Examples:
    python main.py --text "Hello world"
    python main.py --text-file script.txt --title "My Story" --output my_video.mp4
    python main.py --text "Your text here" --engine gtts
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

from manim import BLACK, BLUE, DOWN, FadeIn, FadeOut, Scene, Text, UP, config


def normalize_text(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError("The input text cannot be empty.")
    return cleaned


def chunk_text(text: str, words_per_slide: int = 30) -> list[str]:
    if words_per_slide <= 0:
        raise ValueError("--words-per-slide must be greater than zero.")
    words = text.split()
    if len(words) <= words_per_slide:
        return [text]
    chunks: list[str] = []
    for i in range(0, len(words), words_per_slide):
        chunk = " ".join(words[i:i + words_per_slide])
        if chunk:
            chunks.append(chunk)
    return chunks


def make_speech(text: str, audio_path: Path, engine: str, voice: str | None) -> Path:
    if engine == "gtts":
        try:
            from gtts import gTTS
        except ImportError as exc:
            raise RuntimeError("gTTS is not installed. Install it with: pip install gtts") from exc

        mp3_path = audio_path.with_suffix(".mp3")
        gTTS(text=text, lang=voice or "en").save(str(mp3_path))
        return mp3_path

    try:
        import pyttsx3
    except ImportError as exc:
        raise RuntimeError(
            "pyttsx3 is not installed. Install it with: pip install pyttsx3"
        ) from exc

    engine_obj = pyttsx3.init()
    if voice:
        voices = engine_obj.getProperty("voices")
        selected = next((v for v in voices if voice.lower() in str(v.id).lower()), None)
        if selected is None:
            raise ValueError(f"No pyttsx3 voice matched '{voice}'.")
        engine_obj.setProperty("voice", selected.id)

    engine_obj.save_to_file(text, str(audio_path))
    engine_obj.runAndWait()
    return audio_path


def get_audio_duration(path: Path, fallback_text: str) -> float:
    suffix = path.suffix.lower()
    if suffix == ".wav":
        with wave.open(str(path), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            if rate:
                return frames / float(rate)
    elif suffix == ".mp3":
        try:
            from mutagen.mp3 import MP3

            return float(MP3(str(path)).info.length)
        except ImportError:
            pass

    word_count = max(1, len(fallback_text.split()))
    return max(1.0, word_count / 2.5)


def srt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def write_subtitles(chunks: list[str], total_duration: float, output_path: Path) -> list[dict[str, Any]]:
    weights = [max(1, len(chunk)) for chunk in chunks]
    total_weight = sum(weights)
    current_time = 0.0
    entries: list[dict[str, Any]] = []

    with output_path.open("w", encoding="utf-8") as handle:
        for idx, (chunk, weight) in enumerate(zip(chunks, weights), start=1):
            if idx == len(chunks):
                end_time = total_duration
            else:
                end_time = current_time + (total_duration * weight / total_weight)

            entries.append({"text": chunk, "start": current_time, "end": end_time})
            handle.write(f"{idx}\n{srt_time(current_time)} --> {srt_time(end_time)}\n{chunk}\n\n")
            current_time = end_time

    return entries


class TextNarrationScene(Scene):
    """Animated slide-based text video for arbitrary narration."""

    def construct(self) -> None:
        config_path = os.environ.get("TEXT_VIDEO_CONFIG")
        if not config_path:
            raise RuntimeError("TEXT_VIDEO_CONFIG is missing. Run this script via the CLI entry point.")

        with Path(config_path).open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        self.camera.background_color = BLACK
        self.add_sound(data["audio_path"])

        title_text = data.get("title", "").strip()
        if title_text:
            title = Text(title_text, color=BLUE, font_size=36)
            title.to_edge(UP, buff=0.5)
            self.add(title)

        for subtitle in data["subtitles"]:
            text_obj = Text(subtitle["text"], color="#F5F5F5", font_size=36, line_spacing=0.9)
            text_obj.set_max_width(config.frame_width - 1.2)
            text_obj.set_max_height(config.frame_height - 2.2)
            if title_text:
                text_obj.next_to(title, DOWN, buff=0.5)
            else:
                text_obj.to_edge(DOWN, buff=0.8)

            start = self.renderer.time
            self.play(FadeIn(text_obj), run_time=0.25)
            elapsed = self.renderer.time - start
            remaining = subtitle["end"] - subtitle["start"] - elapsed
            self.wait(max(0.08, remaining))
            self.play(FadeOut(text_obj), run_time=0.2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--text", help="Text to narrate.")
    input_group.add_argument("--text-file", type=Path, help="Path to a UTF-8 text file to narrate.")
    parser.add_argument("--title", default="Narrated Video", help="Optional title displayed on screen.")
    parser.add_argument("--output", type=Path, default=Path("media/narrated_video.mp4"), help="Output MP4 file path.")
    parser.add_argument("--engine", choices=("pyttsx3", "gtts"), default="pyttsx3", help="Speech synthesis engine.")
    parser.add_argument("--voice", help="Voice or language code, e.g. 'en' or an installed pyttsx3 voice fragment.")
    parser.add_argument("--words-per-slide", type=int, default=30, help="How many words per screen of text.")
    parser.add_argument("--quality", default="m", help="Manim quality flag: l, m, h, p")
    parser.add_argument("--keep-assets", action="store_true", help="Keep generated audio and temp files.")
    return parser.parse_args()


def resolve_text(args: argparse.Namespace) -> str:
    if args.text is not None:
        return normalize_text(args.text)
    if args.text_file is not None:
        return normalize_text(args.text_file.read_text(encoding="utf-8"))
    return normalize_text(input("Enter text for the video: "))


def locate_rendered_video(base_dir: Path, expected_name: str) -> Path | None:
    matches = list(base_dir.rglob(f"{expected_name}.mp4"))
    if not matches:
        return None
    return sorted(matches, key=lambda item: (len(item.parts), str(item)))[0]


def main() -> int:
    args = parse_args()
    text = resolve_text(args)
    slides = chunk_text(text, words_per_slide=args.words_per_slide)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="text_video_"))
    audio_path = temp_dir / ("narration.mp3" if args.engine == "gtts" else "narration.wav")

    speech_file = make_speech(text, audio_path, args.engine, args.voice)
    total_duration = get_audio_duration(speech_file, text)
    srt_path = args.output.with_suffix(".srt")
    subtitles = write_subtitles(slides, total_duration, srt_path)

    config_file = temp_dir / "video_config.json"
    config_file.write_text(
        json.dumps({"audio_path": str(speech_file), "title": args.title, "subtitles": subtitles}),
        encoding="utf-8",
    )

    media_dir = args.output.parent / "manim_media"
    command = [
        sys.executable,
        "-m",
        "manim",
        f"-q{args.quality}",
        str(Path(__file__).resolve()),
        "TextNarrationScene",
        "-o",
        args.output.stem,
        "--media_dir",
        str(media_dir),
    ]

    environment = os.environ.copy()
    environment["TEXT_VIDEO_CONFIG"] = str(config_file)
    subprocess.run(command, check=True, env=environment)

    rendered_video = locate_rendered_video(media_dir, args.output.stem)
    if rendered_video is None:
        raise FileNotFoundError(
            f"Manim finished but no video named '{args.output.stem}.mp4' was produced."
        )

    shutil.copy2(rendered_video, args.output)
    if not args.keep_assets:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"Video created: {args.output}")
    print(f"Subtitles: {srt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
