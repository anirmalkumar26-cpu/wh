from pathlib import Path
from typing import Any

import av


def validate_final_output(video_path: Path, expected_duration: float) -> dict[str, Any]:
    if not video_path.is_file() or video_path.stat().st_size == 0:
        raise ValueError(f"Rendered video is missing or empty: {video_path}")
    try:
        container = av.open(str(video_path))
    except av.error.FFmpegError as exc:
        raise ValueError(f"Cannot read rendered video {video_path}: {exc}") from exc
    with container:
        video_streams = [stream for stream in container.streams if stream.type == "video"]
        audio_streams = [stream for stream in container.streams if stream.type == "audio"]
        if len(video_streams) != 1 or len(audio_streams) != 1:
            raise ValueError(
                f"{video_path}: expected one video and one narration stream, "
                f"found {len(video_streams)} video and {len(audio_streams)} audio"
            )
        video_stream, audio_stream = video_streams[0], audio_streams[0]
        video_duration = _stream_duration(video_stream)
        audio_duration = _stream_duration(audio_stream)
        tolerance = 0.15
        if abs(video_duration - expected_duration) > tolerance:
            raise ValueError(
                f"{video_path}: video duration {video_duration:.3f}s differs from timeline "
                f"{expected_duration:.3f}s by more than {tolerance:.2f}s"
            )
        if abs(audio_duration - expected_duration) > tolerance:
            raise ValueError(
                f"{video_path}: narration duration {audio_duration:.3f}s differs from timeline "
                f"{expected_duration:.3f}s by more than {tolerance:.2f}s"
            )
        if not any(container.decode(video=video_stream.index)):
            raise ValueError(f"{video_path}: video stream has no decodable frames")
        if not any(container.decode(audio=0)):
            raise ValueError(f"{video_path}: audio stream has no decodable samples")
        return {
            "video_codec": video_stream.codec_context.name,
            "audio_codec": audio_stream.codec_context.name,
            "video_duration": video_duration,
            "audio_duration": audio_duration,
            "has_decodable_video": True,
            "has_decodable_audio": True,
        }


def _stream_duration(stream: av.stream.Stream) -> float:
    if stream.duration is None or stream.time_base is None:
        raise ValueError(f"{stream.type} stream has no measurable duration")
    duration = float(stream.duration * stream.time_base)
    if duration <= 0:
        raise ValueError(f"{stream.type} stream has invalid duration {duration}")
    return duration
