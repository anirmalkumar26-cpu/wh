"""Per-segment TTS synthesis and WAV concatenation."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path
from typing import Any


def audio_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / float(stream.getframerate())


def concatenate_wav(paths: list[Path], output: Path) -> Path:
    with wave.open(str(paths[0]), "rb") as first:
        params, frames = first.getparams(), [first.readframes(first.getnframes())]
    for path in paths[1:]:
        with wave.open(str(path), "rb") as stream:
            if stream.getparams()[:3] != params[:3]:
                raise RuntimeError("TTS produced incompatible WAV formats.")
            frames.append(stream.readframes(stream.getnframes()))
    with wave.open(str(output), "wb") as stream:
        stream.setparams(params)
        stream.writeframes(b"".join(frames))
    return output


def synthesise_segments(segments: list[dict[str, Any]], directory: Path) -> Path:
    paths = []
    for index, segment in enumerate(segments):
        path = directory / f"narration-{index:03d}.wav"
        script = ("import pyttsx3, sys; e=pyttsx3.init(); e.setProperty('rate',155); "
                  "e.save_to_file(sys.argv[1], sys.argv[2]); e.runAndWait()")
        result = subprocess.run(["python", "-c", script, segment["narration"], str(path)],
                                capture_output=True, text=True, check=False)
        if result.returncode or not path.exists():
            raise RuntimeError(f"Could not create narration audio: {result.stderr.strip()}")
        segment["duration"] = round(max(0.1, audio_duration(path)), 2)
        paths.append(path)
    output = directory / "narration.wav"
    concatenate_wav(paths, output)
    return output
