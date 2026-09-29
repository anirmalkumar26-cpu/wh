"""Backward-compatible entry point for the rendering stage."""

try:
    from .rendering import render_plan
except ImportError:
    from rendering import render_plan

__all__ = ["render_plan"]

if __name__ == "__main__":
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("scene.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("media"))
    parser.add_argument("--quality", choices=["l", "m", "h", "p"], default="h")
    args = parser.parse_args()
    print(f"Rendered video to {render_plan(args.input, args.output_dir, args.quality)}")
