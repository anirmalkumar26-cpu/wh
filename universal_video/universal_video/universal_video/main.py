"""Generate a scene plan from input.txt and render it to a narrated video."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .planning import create_plan
    from .rendering import render_plan
except ImportError:  # Support ``python main.py`` from this directory.
    from planning import create_plan
    from rendering import render_plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("educational_input.txt"))
    parser.add_argument("--json", type=Path, default=Path("scene.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("media"))
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    parser.add_argument("--quality", choices=["l", "m", "h", "p"], default="h")
    args = parser.parse_args()
    create_plan(args.input, args.json, args.model)
    render_plan(args.json, args.output_dir, args.quality)
    print("Done. The JSON, video, and narration audio are ready.")


if __name__ == "__main__":
    main()
