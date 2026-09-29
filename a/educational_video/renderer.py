import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from manim import (
    BLUE,
    GREEN,
    ORANGE,
    RED,
    TEAL,
    Transform,
    UP,
    WHITE,
    YELLOW,
    Circle,
    Create,
    FadeIn,
    Indicate,
    Line,
    Scene,
    Text,
    VGroup,
)

NODE_COLORS = {"node_10": TEAL, "node_20": GREEN, "node_30": ORANGE}
NODE_POSITIONS = {
    "root": (0, 1.25, 0),
    "left": (-2.0, -0.35, 0),
    "right": (2.0, -0.35, 0),
    "left_left": (-3.1, -1.7, 0),
}


class AVLRightRotationScene(Scene):
    """Render the plan's persistent node identities and rotation highlights."""

    def construct(self) -> None:
        timeline_path = os.environ.get("EDU_VIDEO_TIMELINE")
        if not timeline_path:
            raise RuntimeError("EDU_VIDEO_TIMELINE must point to the finalized master timeline")
        timeline = json.loads(Path(timeline_path).read_text(encoding="utf-8"))
        title = Text(timeline["topic"], font_size=34, color=BLUE).to_edge(UP, buff=0.35)
        self.add(title)
        self.nodes: dict[str, VGroup] = {}
        self.edges: dict[str, Line] = {}
        self.current_caption: Text | None = None
        self.node_positions: dict[str, tuple[float, float, float]] = {}

        for segment in timeline["segments"]:
            caption = Text(segment["subtitle"], font_size=25, color=WHITE)
            caption.scale_to_fit_width(12.3).to_edge(__import__("manim").DOWN, buff=0.3)
            if self.current_caption is not None:
                self.remove(self.current_caption)
            self.add(caption)
            self.current_caption = caption

            self.add_sound(segment["audio"]["file"])
            elapsed = 0.0
            for action in segment["visual"]["actions"]:
                duration = float(action["duration"])
                self._animate_action(action, duration)
                elapsed += duration
            remainder = float(segment["audio"]["duration"]) - elapsed
            if remainder > 0:
                self.wait(remainder)

    def _animate_action(self, action: dict[str, Any], duration: float) -> None:
        kind = action["type"]
        target = action["target"]
        if kind == "create_node":
            self._create_node(target, action["value"], action["position"], duration)
        elif kind == "connect":
            self._connect(action["source"], action["destination"], target, duration)
        elif kind == "highlight":
            node = self._require_node(target)
            self.play(Indicate(node, color=YELLOW), run_time=duration)
        elif kind == "rotate_right":
            self._rotate_right(target, action["pivot"], duration)
        else:
            raise ValueError(f"Unsupported action type: {kind!r}")

    def _create_node(self, node_id: str, value: str, position: str, duration: float) -> None:
        if node_id in self.nodes:
            raise ValueError(f"Node identity already exists: {node_id}")
        if position not in NODE_POSITIONS:
            raise ValueError(f"Unsupported AVL node position: {position!r}")
        center = NODE_POSITIONS[position]
        circle = Circle(radius=0.48, color=NODE_COLORS[node_id], stroke_width=5)
        circle.move_to(center)
        label = Text(value, font_size=31, color=WHITE).move_to(center)
        node = VGroup(circle, label)
        self.nodes[node_id] = node
        self.node_positions[node_id] = center
        self.play(Create(circle), FadeIn(label), run_time=duration)

    def _connect(self, source: str, destination: str, edge_id: str, duration: float) -> None:
        if edge_id in self.edges:
            raise ValueError(f"Relationship identity already exists: {edge_id}")
        start = self._require_node(source).get_center()
        end = self._require_node(destination).get_center()
        edge = Line(start, end, color=BLUE, stroke_width=4)
        self.edges[edge_id] = edge
        self.play(Create(edge), run_time=duration)
        edge.set_z_index(-1)

    def _rotate_right(self, root_id: str, pivot_id: str, duration: float) -> None:
        if root_id != "node_30" or pivot_id != "node_20":
            raise ValueError(f"Unsupported right rotation: {pivot_id} over {root_id}")
        root = self._require_node(root_id)
        pivot = self._require_node(pivot_id)
        child = self._require_node("node_10")
        old_root_edge = self.edges.get("edge_30_20")
        old_pivot_edge = self.edges.get("edge_20_10")
        if old_root_edge is None or old_pivot_edge is None:
            raise ValueError("Right rotation requires the 30→20 and 20→10 relationships")

        new_root = NODE_POSITIONS["root"]
        new_left = NODE_POSITIONS["left"]
        new_right = NODE_POSITIONS["right"]
        new_left_edge = Line(
            (new_root[0], new_root[1] - 0.48, 0),
            (new_left[0], new_left[1] + 0.48, 0),
            color=BLUE,
            stroke_width=4,
        )
        new_right_edge = Line(
            (new_root[0], new_root[1] - 0.48, 0),
            (new_right[0], new_right[1] + 0.48, 0),
            color=BLUE,
            stroke_width=4,
        )
        self.play(
            pivot.animate.move_to(new_root),
            root.animate.move_to(new_right),
            child.animate.move_to(new_left),
            Transform(old_pivot_edge, new_left_edge),
            Transform(old_root_edge, new_right_edge),
            run_time=duration,
        )
        old_pivot_edge.set_z_index(-1)
        old_root_edge.set_z_index(-1)
        del self.edges["edge_30_20"]
        self.edges["edge_20_10"] = old_pivot_edge
        self.edges["edge_20_30"] = old_root_edge
        self.node_positions.update({"node_20": new_root, "node_30": new_right, "node_10": new_left})

    def _require_node(self, node_id: str) -> VGroup:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise ValueError(f"Visual action references node that is not yet visible: {node_id}") from exc


def render_complete_video(timeline_path: Path, output_path: Path, quality: str = "low") -> Path:
    qualities = {"low": "-ql", "medium": "-qm", "high": "-qh"}
    if quality not in qualities:
        raise ValueError(f"Unsupported quality {quality!r}; choose one of {', '.join(qualities)}")
    if not timeline_path.is_file():
        raise FileNotFoundError(f"Master timeline not found: {timeline_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    media_dir = output_path.parent / "manim_media"
    command = [
        sys.executable,
        "-m",
        "manim",
        qualities[quality],
        "--disable_caching",
        "--media_dir",
        str(media_dir),
        str(Path(__file__).resolve()),
        "AVLRightRotationScene",
        "-o",
        output_path.stem,
    ]
    env = os.environ.copy()
    env["EDU_VIDEO_TIMELINE"] = str(timeline_path.resolve())
    result = subprocess.run(command, cwd=Path(__file__).resolve().parent.parent, env=env, capture_output=True, text=True)
    if result.returncode:
        detail = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-30:])
        raise RuntimeError(f"Manim rendering failed (exit {result.returncode}):\n{detail}")
    rendered = list(media_dir.rglob(f"{output_path.stem}.mp4"))
    if len(rendered) != 1 or rendered[0].stat().st_size == 0:
        raise RuntimeError(f"Manim reported success but did not produce exactly one non-empty video named {output_path.stem}.mp4")
    if rendered[0].resolve() != output_path.resolve():
        import shutil

        shutil.copy2(rendered[0], output_path)
    return output_path
