from educational_video.pipeline import build_argument_parser, run_pipeline


def main() -> int:
    args = build_argument_parser().parse_args()
    try:
        run_pipeline(
            stage=args.stage,
            input_path=args.input,
            topic=args.topic,
            quality=args.quality,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Pipeline failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
