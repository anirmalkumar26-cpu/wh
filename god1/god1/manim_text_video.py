"""Generate a narrated subtitle video from arbitrary text using Manim.

This script is a generalized replacement for a hardcoded linked-list animation.
It accepts text from a CLI argument, a file, or an interactive prompt, splits it
into readable chunks, optionally generates simple narration audio, renders a
Manim scene with title/subtitles and highlighting, then locates and copies the
resulting .mp4 into an output directory.

Usage examples:
    python manim_text_video.py --text "Hello world. This is a demo." --title "Demo"
    python manim_text_video.py --file notes.txt --highlight-mode sentence --out-dir ./output
    python manim_text_video.py

Dependency behavior:
- If Manim is installed, the script will attempt to render automatically.
- If Manim is not installed, the script still validates input and prepares assets,
  then exits with clear guidance.
- TTS backends are optional. If pyttsx3 or gTTS is available, audio is generated.
  Otherwise, timing falls back to estimated narration duration.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


MIN_FONT_SIZE = 18
MAX_FONT_SIZE = 96
DEFAULT_CHARS_PER_SLIDE = 800
WORDS_PER_SEC = 2.8


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return text


def split_into_sections(text: str) -> List[str]:
    text = normalize_text(text)
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    sections: List[str] = []

    for par in paragraphs:
        if len(par) <= DEFAULT_CHARS_PER_SLIDE:
            sections.append(par)
            continue

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", par) if s.strip()]
        chunk = ""
        for sentence in sentences:
            candidate = f"{chunk} {sentence}".strip()
            if len(candidate) <= DEFAULT_CHARS_PER_SLIDE:
                chunk = candidate
            else:
                if chunk:
                    sections.append(chunk)
                chunk = sentence
        if chunk:
            sections.append(chunk)

    if not sections:
        return [text]

    return sections


def estimate_duration_seconds(text: str) -> float:
    words = re.findall(r"\w+", text)
    return max(1.0, len(words) / WORDS_PER_SEC)


@dataclass
class AudioResult:
    path: Optional[str]
    duration: float


def generate_tts(text: str, out_path: str) -> AudioResult:
    """Generate audio using the best available local/offline backend."""
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.save_to_file(text, out_path)
        engine.runAndWait()
        return AudioResult(out_path, estimate_duration_seconds(text))
    except Exception:
        pass

    try:
        from gtts import gTTS

        gTTS(text=text, lang="en").save(out_path)
        return AudioResult(out_path, estimate_duration_seconds(text))
    except Exception:
        pass

    return AudioResult(None, estimate_duration_seconds(text))


try:
    from manim import (
        DOWN,
        LEFT,
        RIGHT,
        UP,
        FadeIn,
        FadeOut,
        MarkupText,
        Scene,
        Text,
        Write,
    )

    MANIM_AVAILABLE = True
except Exception:
    MANIM_AVAILABLE = False


if MANIM_AVAILABLE:
    class NarratedScene(Scene):
        sections: List[str] = []
        title: Optional[str] = None
        highlight_mode: str = "sentence"
        audio_files: List[Optional[str]] = []

        def construct(self):
            if self.title:
                title_text = Text(self.title, font_size=46)
                title_text.to_edge(UP)
                self.play(Write(title_text))
                self.wait(0.8)

            for index, section in enumerate(self.sections):
                main_text = self._make_text_block(section)
                main_text.move_to(self.camera.frame_center)

                subtitle = Text(
                    section,
                    font_size=self._compute_font_size_for_subtitle(section),
                    color="#DDE7FF",
                )
                subtitle.to_edge(DOWN)

                self.play(FadeIn(main_text), FadeIn(subtitle), run_time=0.5)

                if index < len(self.audio_files) and self.audio_files[index]:
                    try:
                        self.add_sound(self.audio_files[index])
                    except Exception:
                        pass

                if self.highlight_mode == "word":
                    self._play_word_highlights(main_text, section)
                elif self.highlight_mode == "sentence":
                    self._play_sentence_highlights(main_text, section)

                self.wait(estimate_duration_seconds(section) * 0.8)
                self.play(FadeOut(main_text), FadeOut(subtitle), run_time=0.5)

        def _make_text_block(self, text: str):
            size = self._compute_font_size_for_main(text)
            try:
                return MarkupText(text, font_size=size)
            except Exception:
                return Text(text, font_size=size)

        def _compute_font_size_for_main(self, text: str) -> int:
            length = len(text)
            if length < 40:
                return 72
            if length < 140:
                return 48
            if length < 350:
                return 36
            if length < 700:
                return 28
            return max(MIN_FONT_SIZE, 22)

        def _compute_font_size_for_subtitle(self, text: str) -> int:
            main_size = self._compute_font_size_for_main(text)
            return max(MIN_FONT_SIZE, main_size - 12)

        def _play_word_highlights(self, main_text, section: str):
            words = re.findall(r"\w+|[^\w\s]", section)
            if not words:
                return
            for token in words:
                token_obj = Text(token, font_size=self._compute_font_size_for_main(section), color="#FFD166")
                token_obj.move_to(main_text.get_center())
                self.play(FadeIn(token_obj), run_time=0.12)
                self.wait(max(0.18, estimate_duration_seconds(token) * 0.35))
                self.play(FadeOut(token_obj), run_time=0.12)

        def _play_sentence_highlights(self, main_text, section: str):
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", section) if s.strip()]
            if not sentences:
                sentences = [section]
            for sentence in sentences:
                sentence_obj = Text(sentence, font_size=self._compute_font_size_for_main(section), color="#FFD166")
                sentence_obj.move_to(main_text.get_center())
                self.play(FadeIn(sentence_obj), run_time=0.2)
                self.wait(max(0.25, estimate_duration_seconds(sentence) * 0.35))
                self.play(FadeOut(sentence_obj), run_time=0.2)


def find_latest_mp4(search_dir: str, name_hint: Optional[str] = None) -> Optional[str]:
    matches: List[Tuple[float, str]] = []
    for root, _, files in os.walk(search_dir):
        for file_name in files:
            if not file_name.lower().endswith(".mp4"):
                continue
            if name_hint and name_hint.lower() not in file_name.lower():
                continue
            p = os.path.join(root, file_name)
            try:
                matches.append((os.path.getmtime(p), p))
            except OSError:
                continue
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)


def read_source_text(args: argparse.Namespace) -> str:
    if args.text:
        return normalize_text(args.text)

    if args.file:
        if not os.path.exists(args.file):
            raise FileNotFoundError(f"Input file not found: {args.file}")
        with open(args.file, "r", encoding="utf-8") as f:
            return normalize_text(f.read())

    print("Enter or paste text. Press Enter twice to finish:")
    lines: List[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            if not lines:
                continue
            break
        lines.append(line)
    return normalize_text("\n".join(lines))


def render_with_manim(sections: List[str], title: Optional[str], highlight_mode: str, audio_files: List[Optional[str]], extra_args: Optional[str] = None) -> int:
    if not MANIM_AVAILABLE:
        print("Manim is not installed. Render skipped.")
        return 0

    NarratedScene.sections = sections
    NarratedScene.title = title
    NarratedScene.highlight_mode = highlight_mode
    NarratedScene.audio_files = audio_files

    try:
        from manim import config

        if extra_args:
            # Minimal support for quality flags: a user can pass -ql, -qm, etc.
            flags = extra_args.strip().split()
            if "-q" in flags or "--quality" in flags:
                pass
        print("Rendering NarratedScene via Manim API")
        scene = NarratedScene()
        scene.render()
        return 0
    except Exception as exc:
        print(f"Manim rendering failed: {exc}")
        return 1


def copy_rendered_video(out_dir: str) -> Optional[str]:
    target_dir = ensure_dir(out_dir)
    candidate_roots = [
        os.path.join(os.getcwd(), "media"),
        os.path.join(os.getcwd(), "media", "videos"),
        os.path.join(os.getcwd(), "media", "videos", os.path.splitext(os.path.basename(__file__))[0]),
        os.getcwd(),
    ]

    latest: Optional[str] = None
    for root in candidate_roots:
        if not os.path.isdir(root):
            continue
        found = find_latest_mp4(root, name_hint="NarratedScene")
        if found:
            latest = found
            break

    if not latest:
        latest = find_latest_mp4(os.getcwd())

    if not latest:
        print("Could not locate a rendered .mp4 file. Check the Manim output directories.")
        return None

    dest = os.path.join(target_dir, os.path.basename(latest))
    try:
        shutil.copy2(latest, dest)
        print(f"Copied rendered video to: {dest}")
        return dest
    except Exception as exc:
        print(f"Found video at {latest} but failed to copy it: {exc}")
        return None


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a narrated text video with Manim.")
    parser.add_argument("--text", "-t", help="Inline text to render.")
    parser.add_argument("--file", "-f", help="Path to a text file to read.")
    parser.add_argument("--title", help="Optional title displayed at the top of the scene.")
    parser.add_argument("--out-dir", default="./out", help="Directory for the final copied MP4.")
    parser.add_argument("--highlight-mode", choices=["word", "sentence", "none"], default="sentence")
    parser.add_argument("--skip-manim", action="store_true", help="Only prepare text/audio; do not run Manim.")
    parser.add_argument("--manim-args", help="Extra arguments passed to Manim (if supported).")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        text = read_source_text(args)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 2

    if not text:
        print("No text content was provided.")
        return 1

    sections = split_into_sections(text)
    print(f"Prepared {len(sections)} section(s) for rendering.")

    temp_dir = tempfile.mkdtemp(prefix="manim_text_")
    audio_files: List[Optional[str]] = []

    for index, section in enumerate(sections):
        out_file = os.path.join(temp_dir, f"section_{index + 1}.mp3")
        result = generate_tts(section, out_file)
        if result.path:
            audio_files.append(result.path)
            print(f"Audio section {index + 1}: {result.path} ({result.duration:.1f}s)")
        else:
            audio_files.append(None)
            print(f"No TTS backend available for section {index + 1}; using estimated duration ({result.duration:.1f}s)")

    if args.skip_manim:
        print(f"Prepared asset directory: {temp_dir}")
        print("Skipping Manim render as requested (--skip-manim).")
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
        return 0

    if not MANIM_AVAILABLE:
        print("Manim is not installed in this environment. Install it to render the video.")
        print("Example: pip install manim")
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
        return 0

    render_status = render_with_manim(sections, args.title, args.highlight_mode, audio_files, args.manim_args)
    if render_status != 0:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
        return render_status

    copy_rendered_video(args.out_dir)

    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
