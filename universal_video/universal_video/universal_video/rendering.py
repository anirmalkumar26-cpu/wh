"""Isolated Manim rendering for a generated scene plan."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

try:
    from .audio import synthesise_segments
    from .config import ELEMENT_TYPES, QUALITY_NAMES, ensure_directory
    from .subtitles import retime_segments
except ImportError:
    from audio import synthesise_segments
    from config import ELEMENT_TYPES, QUALITY_NAMES, ensure_directory
    from subtitles import retime_segments


def _point(value: Any) -> tuple[float, float, float]:
    values = value if isinstance(value, (list, tuple)) else [0, 0]
    return float(values[0]), float(values[1]), 0.0


def _bounded(value: Any, default: float, low: float, high: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


def render_plan(plan_path: Path, output_dir: Path, quality: str = "h") -> Path:
    from manim import (
        Arc, Arrow, Axes, BLUE, Circle, Create, Dot, DOWN, Ellipse, FadeIn,
        GREEN, Line, Polygon, RED, Rectangle, RIGHT, Scene, Star, Text,
        Triangle, VGroup, WHITE, Write, config,
    )
    try:
        from manim import HexColor
    except ImportError:  # pragma: no cover - supported by current Manim
        HexColor = None

    plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("scene.json must contain at least one scene.")
    ensure_directory(output_dir)
    # Remove abandoned runs but never touch a successfully published result.
    for old in output_dir.glob(".render-*"):
        if old.is_dir():
            shutil.rmtree(old, ignore_errors=True)
    run_id = uuid.uuid4().hex
    render_dir = output_dir / f".render-{run_id}"
    render_dir.mkdir()
    segments = [
        {"index": index, "narration": str(scene.get("narration", "")),
         "subtitle": str(scene.get("subtitle", scene.get("narration", "")))}
        for index, scene in enumerate(scenes)
    ]
    audio_path = synthesise_segments(segments, render_dir)
    retime_segments(segments)
    for scene, segment in zip(scenes, segments):
        scene["duration"] = segment["duration"]

    named_colors = {"WHITE": WHITE, "RED": RED, "GREEN": GREEN, "BLUE": BLUE}

    def color_for(value: Any):
        raw = str(value or "WHITE").strip()
        if raw.upper() in named_colors:
            return named_colors[raw.upper()]
        if HexColor and raw.startswith("#") and len(raw) in (4, 7, 9):
            try:
                return HexColor(raw)
            except ValueError:
                pass
        return WHITE

    def make_element(data: dict[str, Any]):
        kind = data.get("type")
        position = _point(data.get("position", [0, 0]))
        color = color_for(data.get("color"))
        stroke = _bounded(data.get("stroke_width"), 3, 1, 12)
        fill = _bounded(data.get("fill_opacity"), 0, 0, 1)
        if kind in ("text", "label"):
            mob = Text(str(data.get("text", "")), font_size=32, color=color)
        elif kind == "circle":
            mob = Circle(radius=_bounded(data.get("radius"), .8, .05, 5), color=color)
        elif kind == "ellipse":
            mob = Ellipse(width=_bounded(data.get("width"), 2, .1, 10),
                          height=_bounded(data.get("height"), 1, .1, 7), color=color)
        elif kind == "rectangle":
            mob = Rectangle(width=_bounded(data.get("width"), 2, .1, 10),
                            height=_bounded(data.get("height"), 1, .1, 7), color=color)
        elif kind in ("line", "arrow"):
            end = _point(data.get("end", [1, 0]))
            mob = (Arrow(position, end, color=color, stroke_width=stroke)
                   if kind == "arrow" else Line(position, end, color=color, stroke_width=stroke))
        elif kind in ("polygon", "triangle"):
            points = data.get("points")
            if kind == "triangle" or not isinstance(points, list) or len(points) < 3:
                mob = Triangle(color=color).scale(_bounded(data.get("radius"), 1, .1, 3))
            else:
                mob = Polygon(*[_point(point) for point in points], color=color)
        elif kind == "star":
            mob = Star(n=int(_bounded(data.get("num_points"), 5, 3, 12)),
                       outer_radius=_bounded(data.get("outer_radius"), 1, .1, 3),
                       inner_radius=_bounded(data.get("inner_radius"), .45, .05, 2),
                       color=color)
        elif kind == "arc":
            mob = Arc(radius=_bounded(data.get("radius"), 1, .1, 4),
                      start_angle=_bounded(data.get("start_angle"), 0, -20, 20),
                      angle=_bounded(data.get("angle"), 3.14, -.0, 20), color=color)
        elif kind == "dot":
            mob = Dot(point=position, radius=_bounded(data.get("radius"), .08, .02, .5), color=color)
            return mob
        elif kind == "axes":
            mob = Axes(x_range=data.get("x_range", [-3, 3, 1]),
                       y_range=data.get("y_range", [-2, 2, 1]), color=color)
        else:
            return None
        mob.set_stroke(color=color, width=stroke)
        if fill:
            mob.set_fill(color=color, opacity=fill)
        mob.move_to(position)
        return mob

    class GeneratedVideo(Scene):
        def construct(self) -> None:
            self.add_sound(str(audio_path))
            for scene_data, segment in zip(scenes, segments):
                elements = [make_element(item) for item in scene_data.get("elements", [])
                            if isinstance(item, dict) and item.get("type") in ELEMENT_TYPES]
                elements = [item for item in elements if item is not None]
                group = VGroup(*elements)
                subtitle = Text(segment["subtitle"], font_size=28, color=WHITE).to_edge(DOWN)
                animation_time = min(.8, max(.15, segment["duration"] * .12)) if elements else 0
                if elements:
                    self.play(*[Write(mob) if isinstance(mob, Text)
                               else Create(mob) for mob in elements], run_time=animation_time)
                    # A subtle drift keeps static diagrams visually alive without changing timing.
                    if segment["duration"] > animation_time + .25:
                        self.play(group.animate.shift(RIGHT * .08), run_time=.2)
                self.play(FadeIn(subtitle), run_time=min(.2, max(.05, segment["duration"] / 10)))
                elapsed = animation_time + (.2 if elements and segment["duration"] > animation_time + .25 else 0)
                elapsed += min(.2, max(.05, segment["duration"] / 10))
                self.wait(max(.05, segment["duration"] - elapsed))
                self.remove(group, subtitle)

    destination = output_dir / "generated_video.mp4"
    audio_destination = output_dir / "narration.wav"
    staged_video = output_dir / f".generated_video-{run_id}.mp4"
    staged_audio = output_dir / f".narration-{run_id}.wav"
    try:
        config.quality = QUALITY_NAMES.get(quality, QUALITY_NAMES["h"])
        config.media_dir = str(render_dir)
        config.output_file = "generated_video"
        setattr(config, "disable_caching", True)
        GeneratedVideo().render()
        videos = list(render_dir.rglob("generated_video*.mp4"))
        if not videos:
            raise RuntimeError(f"Manim completed without creating a video in {render_dir}.")
        shutil.copy2(max(videos, key=lambda path: path.stat().st_mtime), staged_video)
        shutil.copy2(audio_path, staged_audio)
        os.replace(staged_video, destination)
        os.replace(staged_audio, audio_destination)
        plan["segments"] = segments
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        return destination
    finally:
        for staged in (staged_video, staged_audio):
            staged.unlink(missing_ok=True)
        shutil.rmtree(render_dir, ignore_errors=True)
