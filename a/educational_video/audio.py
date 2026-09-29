import base64
import hashlib
import json
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any

PCM_FORMAT = (1, 22050, 2)


def initialize_tts_engine() -> str:
    if not shutil.which("powershell.exe"):
        raise RuntimeError("Windows PowerShell is required for the built-in SAPI TTS backend")
    return "windows-sapi"


def generate_audio(text: str, output_path: Path) -> Path:
    initialize_tts_engine()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "$ErrorActionPreference = 'Stop'; "
        "$voice = New-Object -ComObject SAPI.SpVoice; "
        "$stream = New-Object -ComObject SAPI.SpFileStream; "
        "$stream.Format.Type = 22; "
        f"$stream.Open({_ps_literal(str(output_path.resolve()))}, 3, $false); "
        "$voice.AudioOutputStream = $stream; "
        f"$null = $voice.Speak({_ps_literal(text)}, 0); "
        "$stream.Close();"
    )
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"SAPI failed to synthesize {output_path.name}: {result.stderr.strip() or result.stdout.strip()}")
    get_audio_duration(output_path)
    return output_path


def get_audio_duration(path: Path) -> float:
    if not path.is_file():
        raise FileNotFoundError(f"Audio asset is missing: {path}")
    try:
        with wave.open(str(path), "rb") as source:
            params = source.getparams()
            if (params.nchannels, params.framerate, params.sampwidth) != PCM_FORMAT:
                raise ValueError(f"{path}: expected mono 16-bit 22050 Hz WAV, got {params}")
            duration = source.getnframes() / float(params.framerate)
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"{path}: unreadable WAV audio: {exc}") from exc
    if duration <= 0:
        raise ValueError(f"{path}: WAV audio is empty")
    return duration


def _ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def generate_audio_segments(plan: dict[str, Any], audio_dir: Path) -> list[dict[str, Any]]:
    result = []
    for segment in plan["segments"]:
        path = audio_dir / f"{segment['id']}.wav"
        metadata_path = path.with_suffix(".json")
        cache_is_valid = False
        if path.is_file() and metadata_path.is_file():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                cache_is_valid = metadata.get("text_sha256") == hashlib.sha256(
                    segment["narration"].encode("utf-8")
                ).hexdigest()
            except json.JSONDecodeError:
                cache_is_valid = False
        if not cache_is_valid:
            generate_audio(segment["narration"], path)
            metadata_path.write_text(
                json.dumps(
                    {"text_sha256": hashlib.sha256(segment["narration"].encode("utf-8")).hexdigest()},
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        result.append({**segment, "audio_path": str(path.resolve()), "audio_duration": get_audio_duration(path)})
    return result


def concatenate_audio_segments(segments: list[dict[str, Any]], output_path: Path) -> Path:
    first_path = Path(segments[0]["audio_path"])
    with wave.open(str(first_path), "rb") as first:
        expected = first.getparams()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as output:
        output.setparams(expected)
        for segment in segments:
            path = Path(segment["audio_path"])
            with wave.open(str(path), "rb") as source:
                if source.getparams()[:3] != expected[:3]:
                    raise ValueError(f"{path}: WAV format differs from {first_path}")
                output.writeframes(source.readframes(source.getnframes()))
    return output_path
