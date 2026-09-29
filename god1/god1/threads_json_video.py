"""Render an educational Manim video from the generated scene-plan JSON.

Usage:
    python threads_json_video.py --json tm\\output.json --quality l

The renderer intentionally uses the scene IDs and object metadata from the
planner output, while providing stable visual templates for the seven concepts
in the current plan.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from manim import (
    BLACK,
    BLUE,
    DOWN,
    DR,
    DL,
    FadeIn,
    FadeOut,
    GREEN,
    LEFT,
    Line,
    ORANGE,
    RED,
    RIGHT,
    RoundedRectangle,
    Scene,
    Text,
    UP,
    VGroup,
    WHITE,
    YELLOW,
    Arrow,
    Circle,
    Create,
    Dot,
    GrowArrow,
    Indicate,
    LaggedStart,
    MoveAlongPath,
    Rectangle,
    SurroundingRectangle,
    Transform,
    config,
)


COLORS = {
    "blue": BLUE,
    "green": GREEN,
    "orange": ORANGE,
    "red": RED,
    "yellow": YELLOW,
    "white": WHITE,
}


def color_for(value: str | None, fallback=WHITE):
    return COLORS.get((value or "").lower(), fallback)


def fit_text(text: str, width: float, font_size: int = 28) -> Text:
    item = Text(text, font_size=font_size, color=WHITE)
    item.set_max_width(width)
    return item


class ThreadsFromJson(Scene):
    """High-contrast, diagram-first renderer for ScenePlan JSON."""

    plan: dict[str, Any] = {}

    def construct(self) -> None:
        path = Path(self.renderer.file_writer.movie_file_path).parent.parent.parent / "tm" / "output.json"
        configured = self.renderer.camera.file_writer if False else None
        del configured
        json_path = Path(__import__("os").environ.get("THREADS_JSON", str(path)))
        with json_path.open("r", encoding="utf-8") as handle:
            self.plan = json.load(handle)

        self.camera.background_color = BLACK
        self.target_duration = float(__import__("os").environ.get("THREADS_DURATION", "60"))
        self.scene_count = max(1, len(self.plan.get("scenes", [])))
        self._intro()
        for index, scene_data in enumerate(self.plan.get("scenes", []), start=1):
            self._render_scene(scene_data, index, len(self.plan.get("scenes", [])))
        self._outro()

    def _header(self, title: str, index: int, total: int) -> VGroup:
        bar = Rectangle(
            width=config.frame_width,
            height=0.12,
            stroke_width=0,
            fill_color=BLUE,
            fill_opacity=0.8,
        ).to_edge(UP, buff=0)
        label = Text(f"{index:02d}  {title}", font_size=32, color=WHITE)
        label.to_edge(UP, buff=0.28)
        progress = Text(f"{index}/{total}", font_size=18, color="#8EA8C7")
        progress.to_corner(UR if False else DR, buff=0.25)
        return VGroup(bar, label, progress)

    def _intro(self) -> None:
        kicker = Text("OPERATING SYSTEMS", font_size=22, color=BLUE)
        title = Text(self.plan.get("topic", "Threads and Concurrency"), font_size=48, color=WHITE)
        subtitle = fit_text(
            "How independent execution paths share resources, compete for CPU time, and coordinate safely.",
            10.5,
            26,
        )
        group = VGroup(kicker, title, subtitle).arrange(DOWN, buff=0.35)
        self.play(FadeIn(kicker, shift=UP), FadeIn(title, shift=UP), FadeIn(subtitle), run_time=1.2)
        self.wait(1.2)
        self.play(FadeOut(group), run_time=0.6)

    def _outro(self) -> None:
        title = Text("One process. Many paths. One coordinated result.", font_size=38, color=WHITE)
        caption = fit_text(
            "Threads make programs responsive and fast - synchronization makes them correct.",
            10.5,
            27,
        )
        group = VGroup(title, caption).arrange(DOWN, buff=0.35)
        self.play(FadeIn(group, shift=UP), run_time=0.8)
        self.wait(1.5)
        self.play(FadeOut(group), run_time=0.5)

    def _render_scene(self, data: dict[str, Any], index: int, total: int) -> None:
        scene_start = self.renderer.time
        scene_id = data.get("id", "")
        header = self._header(data.get("title", "Concept"), index, total)
        narration = data.get("narration") or data.get("purpose", "")
        caption = fit_text(narration, 10.8, 21).to_edge(DOWN, buff=0.22)
        self.add(header)
        self.play(FadeIn(caption), run_time=0.25)

        if "process_vs_thread" in scene_id:
            diagram = self._process_threads()
        elif "concurrency" in scene_id:
            diagram = self._concurrency_parallelism()
        elif "lifecycle" in scene_id:
            diagram = self._lifecycle()
        elif "threading_models" in scene_id:
            diagram = self._models()
        elif "race_condition" in scene_id:
            diagram = self._race_condition()
        elif "deadlock" in scene_id:
            diagram = self._deadlock()
        elif "thread_pool" in scene_id:
            diagram = self._thread_pool()
        else:
            diagram = self._generic_scene(data)

        actions = data.get("actions", [])
        action_timings = [
            action.get("timing", {})
            for action in actions
            if isinstance(action, dict)
        ]
        reveal_time = max(
            0.8,
            min(2.0, sum(float(item.get("duration", 1.0)) for item in action_timings) / max(1, len(action_timings))),
        )
        self._animate_diagram(scene_id, diagram, reveal_time)
        explanation_pause = float(data.get("explanation_pause", 1.0))
        action_pause = sum(
            max(0.0, float(item.get("pause_after", 0.0)))
            for item in action_timings
        )
        self.wait(max(1.4, explanation_pause + min(action_pause, 3.0)))
        scene_buffer = float(data.get("scene_buffer", 0.0))
        if scene_buffer > 0:
            self.wait(scene_buffer)
        # Reserve an equal teaching interval for every section so the complete
        # lesson reaches the requested runtime without rushing the diagrams.
        reserved_scene_time = max(0.0, (self.target_duration - 5.8) / self.scene_count)
        remaining = reserved_scene_time - (self.renderer.time - scene_start) - 0.55
        if remaining > 0:
            self.wait(remaining)
        self.play(FadeOut(diagram), FadeOut(caption), FadeOut(header), run_time=0.55)

    def _animate_diagram(self, scene_id: str, diagram: VGroup, reveal_time: float) -> None:
        """Animate the teaching action rather than presenting a static card."""
        if "process_vs_thread" in scene_id:
            process, label, shared, threads, arrows = diagram
            self.play(FadeIn(process), FadeIn(label), run_time=0.45)
            self.play(LaggedStart(*[FadeIn(item, shift=UP * 0.25) for item in shared], lag_ratio=0.25), run_time=0.9)
            self.play(FadeIn(threads, shift=DOWN * 0.3), run_time=0.7)
            self.play(LaggedStart(*[GrowArrow(item) for item in arrows], lag_ratio=0.25), run_time=0.9)
            self.play(threads[0].animate.shift(UP * 0.22), threads[1].animate.shift(UP * 0.22), run_time=0.8)
            return
        if "concurrency" in scene_id:
            left_title, right_title, core_left, core_right, timeline, parallel, arrows = diagram
            self.play(FadeIn(left_title), FadeIn(right_title), run_time=0.35)
            self.play(FadeIn(core_left), FadeIn(core_right), run_time=0.6)
            self.play(GrowArrow(arrows[0]), GrowArrow(arrows[1]), run_time=0.7)
            self.play(LaggedStart(*[FadeIn(item, shift=RIGHT * 0.2) for item in timeline], lag_ratio=0.18), run_time=1.0)
            self.play(LaggedStart(*[FadeIn(item, shift=UP * 0.2) for item in parallel], lag_ratio=0.2), run_time=0.8)
            for item in timeline:
                self.play(Indicate(item, color=YELLOW), run_time=0.35)
            return
        if "lifecycle" in scene_id:
            nodes, arrows, tcb, link = diagram
            self.play(FadeIn(nodes[0], shift=LEFT * 0.3), run_time=0.45)
            for index, arrow in enumerate(arrows):
                self.play(GrowArrow(arrow), FadeIn(nodes[index + 1], shift=RIGHT * 0.3), run_time=0.55)
            self.play(GrowArrow(link), FadeIn(tcb, shift=DOWN * 0.2), run_time=0.6)
            marker = Dot(color=YELLOW).move_to(nodes[0].get_center())
            self.add(marker)
            for node in nodes[1:]:
                self.play(marker.animate.move_to(node.get_center()), run_time=0.65)
                self.play(Indicate(node, color=YELLOW), run_time=0.3)
            self.remove(marker)
            return
        if "threading_models" in scene_id:
            self.play(LaggedStart(*[FadeIn(row, shift=RIGHT * 0.25) for row in diagram], lag_ratio=0.3), run_time=1.3)
            for row in diagram:
                self.play(Indicate(row, color=YELLOW), run_time=0.45)
            return
        if "race_condition" in scene_id:
            shared, t1, t2, arrows, bad, mutex = diagram
            self.play(FadeIn(shared), FadeIn(t1), FadeIn(t2), run_time=0.7)
            self.play(GrowArrow(arrows[0]), GrowArrow(arrows[1]), run_time=0.8)
            self.play(Indicate(shared, color=RED), run_time=0.6)
            self.play(FadeIn(bad, shift=DOWN * 0.2), run_time=0.5)
            self.play(FadeOut(bad), FadeIn(mutex, shift=UP * 0.2), run_time=0.6)
            self.play(Indicate(mutex, color=GREEN), run_time=0.6)
            return
        if "deadlock" in scene_id:
            a, b, arrows, cycle, fix = diagram
            self.play(FadeIn(a, shift=LEFT * 0.3), FadeIn(b, shift=RIGHT * 0.3), run_time=0.7)
            self.play(GrowArrow(arrows[0]), GrowArrow(arrows[1]), run_time=1.0)
            self.play(FadeIn(cycle, shift=UP * 0.2), Indicate(cycle, color=RED), run_time=0.8)
            self.play(FadeIn(fix, shift=UP * 0.2), run_time=0.6)
            return
        if "thread_pool" in scene_id:
            queue, workers, result, arrows, note = diagram
            self.play(FadeIn(queue), FadeIn(workers), FadeIn(result), run_time=0.8)
            self.play(GrowArrow(arrows[0]), GrowArrow(arrows[1]), run_time=0.7)
            request = Circle(radius=0.12, color=YELLOW).move_to(queue.get_center())
            self.add(request)
            for worker in workers:
                self.play(request.animate.move_to(worker.get_center()), run_time=0.45)
                self.play(Indicate(worker, color=YELLOW), run_time=0.3)
                self.play(request.animate.move_to(result.get_center()), run_time=0.45)
                self.play(FadeOut(request), run_time=0.15)
                request = Circle(radius=0.12, color=YELLOW).move_to(queue.get_center())
                self.add(request)
            self.play(FadeOut(request), FadeIn(note, shift=UP * 0.2), run_time=0.5)
            return
        self.play(FadeIn(diagram, shift=UP * 0.15), run_time=reveal_time)

    def _box(self, label: str, color=BLUE, width=2.4, height=0.7, font_size=24) -> VGroup:
        rect = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=0.12,
            stroke_color=color,
            stroke_width=2,
            fill_color=color,
            fill_opacity=0.14,
        )
        text = fit_text(label, width - 0.22, font_size).move_to(rect)
        return VGroup(rect, text)

    def _process_threads(self) -> VGroup:
        process = RoundedRectangle(width=10.4, height=5.3, corner_radius=0.18, stroke_color=WHITE)
        process.shift(UP * 0.15)
        label = Text("PROCESS  |  shared address space", font_size=25, color=WHITE).next_to(process, UP, buff=0.16)
        shared = VGroup(
            self._box("CODE", BLUE, 2.7),
            self._box("GLOBAL DATA", GREEN, 2.7),
            self._box("HEAP", ORANGE, 2.7),
        ).arrange(RIGHT, buff=0.3).move_to(process.get_center() + UP * 1.15)
        thread_a = VGroup(
            self._box("T1  stack", YELLOW, 2.2, 0.72, 22),
            self._box("PC + registers", YELLOW, 2.2, 0.72, 21),
        ).arrange(DOWN, buff=0.14)
        thread_b = VGroup(
            self._box("T2  stack", YELLOW, 2.2, 0.72, 22),
            self._box("PC + registers", YELLOW, 2.2, 0.72, 21),
        ).arrange(DOWN, buff=0.14)
        threads = VGroup(thread_a, thread_b).arrange(RIGHT, buff=0.9).move_to(process.get_center() + DOWN * 1.05)
        arrows = VGroup(
            Arrow(thread_a.get_top(), shared.get_bottom(), color=YELLOW, buff=0.1),
            Arrow(thread_b.get_top(), shared.get_bottom(), color=YELLOW, buff=0.1),
        )
        return VGroup(process, label, shared, threads, arrows)

    def _concurrency_parallelism(self) -> VGroup:
        left_title = Text("CONCURRENCY", font_size=28, color=ORANGE)
        right_title = Text("PARALLELISM", font_size=28, color=GREEN)
        left_title.move_to(LEFT * 3.3 + UP * 2.1)
        right_title.move_to(RIGHT * 3.3 + UP * 2.1)
        core_left = self._box("1 CPU CORE", BLUE, 3.0, 0.7)
        core_right = VGroup(*[self._box(f"CORE {i}", GREEN, 1.35, 0.6, 19) for i in range(1, 4)]).arrange(DOWN, buff=0.18)
        core_left.move_to(LEFT * 3.3 + UP * 0.95)
        core_right.move_to(RIGHT * 3.3 + UP * 0.8)
        timeline = VGroup(
            *[self._box(f"T{i}", ORANGE if i % 2 else YELLOW, 1.25, 0.58, 20) for i in [1, 2, 1, 2, 1]]
        ).arrange(RIGHT, buff=0.12).move_to(LEFT * 3.3 + DOWN * 0.55)
        arrows = VGroup(
            Arrow(core_left.get_bottom(), timeline.get_top(), color=ORANGE),
            Arrow(core_right.get_left(), RIGHT * 2.0 + UP * 0.2, color=GREEN),
        )
        parallel = VGroup(
            self._box("T1", GREEN, 1.1, 0.55, 20),
            self._box("T2", GREEN, 1.1, 0.55, 20),
            self._box("T3", GREEN, 1.1, 0.55, 20),
        ).arrange(DOWN, buff=0.12).move_to(RIGHT * 2.0 + UP * 0.2)
        return VGroup(left_title, right_title, core_left, core_right, timeline, parallel, arrows)

    def _lifecycle(self) -> VGroup:
        states = ["NEW", "READY", "RUNNING", "BLOCKED", "TERMINATED"]
        nodes = VGroup(*[self._box(state, BLUE if state != "RUNNING" else GREEN, 1.75, 0.72, 21) for state in states])
        nodes.arrange(RIGHT, buff=0.15).scale(0.9).move_to(UP * 0.65)
        arrows = VGroup(*[
            Arrow(nodes[i].get_right(), nodes[i + 1].get_left(), color=WHITE, buff=0.08)
            for i in range(len(nodes) - 1)
        ])
        tcb = self._box("TCB\nPC | registers | stack | priority", ORANGE, 4.5, 1.25, 20).move_to(DOWN * 1.25)
        link = Arrow(nodes[2].get_bottom(), tcb.get_top(), color=ORANGE)
        return VGroup(nodes, arrows, tcb, link)

    def _models(self) -> VGroup:
        rows = []
        names = [("many-to-one", 4, 1), ("one-to-one", 3, 3), ("many-to-many", 4, 2)]
        for name, user_count, kernel_count in names:
            title = Text(name, font_size=24, color=WHITE)
            users = VGroup(*[Circle(radius=0.16, color=ORANGE) for _ in range(user_count)]).arrange(RIGHT, buff=0.12)
            kernels = VGroup(*[self._box("K", GREEN, 0.48, 0.38, 16) for _ in range(kernel_count)]).arrange(RIGHT, buff=0.15)
            row = VGroup(title, users, kernels).arrange(RIGHT, buff=0.35)
            rows.append(row)
        group = VGroup(*rows).arrange(DOWN, buff=0.35).move_to(UP * 0.2)
        return group

    def _race_condition(self) -> VGroup:
        shared = self._box("shared counter = 0", BLUE, 3.0, 0.9, 24).move_to(UP * 1.3)
        t1 = self._box("T1 reads 0\nwrites 1", ORANGE, 2.2, 0.9, 21).move_to(LEFT * 3 + DOWN * 0.35)
        t2 = self._box("T2 reads 0\nwrites 1", RED, 2.2, 0.9, 21).move_to(RIGHT * 3 + DOWN * 0.35)
        bad = self._box("lost update: result = 1", RED, 3.2, 0.75, 22).move_to(DOWN * 1.65)
        arrows = VGroup(Arrow(t1.get_top(), shared.get_left(), color=ORANGE), Arrow(t2.get_top(), shared.get_right(), color=RED))
        mutex = self._box("MUTEX: one thread at a time", GREEN, 4.0, 0.7, 22).move_to(DOWN * 1.65)
        return VGroup(shared, t1, t2, arrows, bad, mutex)

    def _deadlock(self) -> VGroup:
        a = self._box("T1 owns A\nwaits for B", RED, 2.3, 0.95, 21).move_to(LEFT * 2.7 + UP * 0.7)
        b = self._box("T2 owns B\nwaits for A", RED, 2.3, 0.95, 21).move_to(RIGHT * 2.7 + UP * 0.7)
        arrows = VGroup(
            Arrow(a.get_right(), b.get_left(), color=RED, buff=0.1),
            Arrow(b.get_left() + DOWN * 0.25, a.get_right() + DOWN * 0.25, color=RED, buff=0.1),
        )
        cycle = Text("circular wait  ->  DEADLOCK", font_size=30, color=RED).move_to(DOWN * 1.25)
        fix = self._box("fix: consistent lock ordering", GREEN, 4.0, 0.7, 22).move_to(DOWN * 2.0)
        return VGroup(a, b, arrows, cycle, fix)

    def _thread_pool(self) -> VGroup:
        queue = self._box("request queue", BLUE, 2.3, 0.85, 23).move_to(LEFT * 3.2)
        workers = VGroup(*[self._box(f"worker {i}", GREEN, 1.55, 0.62, 19) for i in range(1, 4)])
        workers.arrange(DOWN, buff=0.18).move_to(RIGHT * 0.2)
        result = self._box("responses", ORANGE, 2.0, 0.85, 23).move_to(RIGHT * 3.4)
        arrows = VGroup(
            Arrow(queue.get_right(), workers.get_left(), color=BLUE),
            Arrow(workers.get_right(), result.get_left(), color=ORANGE),
        )
        note = Text("reuse workers • avoid create/destroy overhead", font_size=25, color=WHITE).move_to(DOWN * 1.95)
        return VGroup(queue, workers, result, arrows, note)

    def _generic_scene(self, data: dict[str, Any]) -> VGroup:
        cards = []
        for item in data.get("visual_objects", [])[:6]:
            label = item.get("label") or item.get("content") or item.get("type", "object")
            cards.append(self._box(label, color_for(item.get("color"), BLUE), 2.2, 0.7, 20))
        group = VGroup(*cards).arrange_in_grid(rows=2, cols=3, buff=0.3)
        return group


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--quality", default="m", choices=("l", "m", "h", "p"))
    parser.add_argument("--output", type=Path, default=Path("output/threads_explained.mp4"))
    parser.add_argument("--duration", type=float, default=60.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.json.is_file():
        raise FileNotFoundError(args.json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    import os
    import sys
    os.environ["THREADS_JSON"] = str(args.json.resolve())
    os.environ["THREADS_DURATION"] = str(args.duration)
    command = [
        sys.executable,
        "-m",
        "manim",
        f"-q{args.quality}",
        "--disable_caching",
        "--media_dir",
        str((args.output.parent / "manim_media").resolve()),
        str(Path(__file__).resolve()),
        "ThreadsFromJson",
        "-o",
        args.output.name,
    ]
    import subprocess
    subprocess.run(command, cwd=args.output.parent, check=True)
    rendered_candidates = list((args.output.parent / "manim_media").rglob(args.output.name))
    if not rendered_candidates:
        raise FileNotFoundError(f"Manim completed but did not create {args.output.name}")
    rendered = max(rendered_candidates, key=lambda item: item.stat().st_mtime)
    if rendered.resolve() != args.output.resolve():
        rendered.replace(args.output)
    print(f"Video created: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
