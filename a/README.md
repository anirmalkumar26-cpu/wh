# Educational Video Generator

A modular Manim pipeline for narrated, highlighted data-structure lessons. The
first example demonstrates an AVL right rotation. It reuses the staged reveal,
dark background, semantic colors, and active-object emphasis of
`god1/god1/threads_json_video.py`, without changing either inspected project.

## Requirements

- Python 3.11 or newer (tested with Python 3.11)
- Manim Community 0.21.x, PyAV, and Manim's system dependencies, including FFmpeg
- Windows with a SAPI speech voice installed (the current machine has Microsoft
  David and Zira). TTS writes real PCM WAV files and fails explicitly if SAPI
  cannot generate them.

Install dependencies with `python -m pip install -r requirements.txt`. This project
does not need an LLM/API key. `pytest` is only needed to run the tests.

## Run

From this directory:

```powershell
python main.py --stage full
```

Select the initial lesson topic or a JSON/text source:

```powershell
python main.py --topic "AVL tree right rotation"
python main.py --input data\input.json --stage full
python main.py --input lesson.txt --stage plan
python main.py --stage audio
python main.py --stage render
```

`plan` saves a reusable `data/scene_plan.json`; it does not synthesize audio.
`audio` generates segment WAVs, measures their durations, writes the master
timeline and SRT. `render` requires those existing assets and renders without
regenerating them. `full` runs all stages. Existing audio is reused only when
its narration-text fingerprint matches the current plan. Final MP4 validation
checks decodable video and audio streams against the measured timeline.

Outputs are written beneath `output/`: `final.mp4`, `subtitles.srt`,
`narration.wav`, the per-segment WAV files, `scene_plan.json`,
`master_timeline.json`, and `pipeline_report.json`. The final video includes
Manim-muxed narration; the SRT is also delivered separately.

## Modules

- `educational_video.content`: input loading and content validation.
- `educational_video.planner`: stable visual IDs, AVL actions, and continuity
  validation.
- `educational_video.audio`: Windows SAPI synthesis, PCM validation, duration
  measurement, and narration concatenation.
- `educational_video.timeline`: measured timestamps, action-duration checks,
  and SRT generation.
- `educational_video.renderer`: persistent Manim node/edge objects and
  narration-synchronized highlighting.
- `educational_video.video_validator`: final audio/video stream and duration checks.
- `educational_video.pipeline`: stage orchestration and output reporting.
- `main.py`: CLI entry point.

The initial renderer intentionally targets the AVL example rather than claiming
to interpret arbitrary action types. Supply a script for non-AVL topics; a topic
alone selects the included AVL lesson only. The plan schema and IDs are
extensible; additional renderers can be added for other structures. Word-level alignment,
non-Windows TTS backends, and an external standalone-FFmpeg postprocessing
stage are not included. Manim requires FFmpeg for rendering and audio muxing.
