"""Backward-compatible entry point for the planning stage."""

try:
    from .planning import create_plan, normalise_plan
except ImportError:
    from planning import create_plan, normalise_plan

__all__ = ["create_plan", "normalise_plan"]

if __name__ == "__main__":
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("educational_input.txt"))
    parser.add_argument("--output", type=Path, default=Path("scene.json"))
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    args = parser.parse_args()
    create_plan(args.input, args.output, args.model)
    print(f"Wrote {args.output}")
