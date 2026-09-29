# Project audit

## Scope and layout

The VS Code workspace root contains three separate Python video-generation
projects (`a/`, `god1/`, and `universal_video/`) plus generated media and local
test cache. There is no root-level Python application, dependency manifest,
backend, or Git repository. The new backend will therefore live in a new
root-level `backend/` directory and will not replace any of those projects.

## Existing video engines

### `a/` — `educational_video`

This is the best initial integration target: it is a modular and tested pipeline
with a CLI at `a/main.py` and the reusable stages in
`a/educational_video/`. `run_pipeline(stage, input_path, topic, quality)` handles
planning, audio, rendering, and final validation. The version-1 scene plan has
`topic`, three stable AVL visual objects, and `segments`; each segment has an
`id`, `narration`, optional `subtitle`, and supported visual `actions`.
`create_master_timeline` adds measured audio paths/durations, sequential
`timeline` bounds, and visual actions. Render expects that timeline and uses
Manim plus Windows SAPI speech synthesis.

The engine has a real WAV validator, timeline/SRT generation, and an MP4
validator. Its checked-in input is a seven-segment AVL right-rotation lesson.
It is intentionally specialized: topic-only planning is supported only for that
AVL example, the renderer implements AVL node/edge actions, and the audio
backend requires Windows PowerShell/SAPI. Its configuration writes into
`a/data/` and `a/output/`, so the backend must isolate jobs rather than invoke
the CLI against the checked-in project directories.

The existing pipeline tests passed (8 tests) when run from `a/`. A first
workspace-root invocation failed to import the package because this project's
tests must be run with `a/` as the working directory; this is a test invocation
detail, not a product failure.

### `god1/`

This project has a text-video entry point, a separate JSON/Manim renderer, and a
Pydantic/Google-GenAI scene planner. Its JSON scene-plan schema is based on
`scenes` and scene actions; rendering includes templates for recognized scene
IDs. Speech support is optional and uses gTTS or pyttsx3. It is a distinct,
partially overlapping engine rather than a compatible drop-in for the `a/`
version-1 segment/action plan.

### `universal_video/`

This project has a coordinated assessment, optional expansion, planning, speech,
subtitle, and rendering flow. Its plans use `title`, `scenes`, narration,
subtitles, durations, elements, and timed segments. It depends on Google
GenAI, Manim, and pyttsx3 and reads `GEMINI_API_KEY`. It is a broader candidate
for a future general-visual renderer, but its schemas and entry points differ
from both the `a/` and `god1/` pipelines.

## Compatibility and preservation decisions

The initial backend adapter targets `a/educational_video/` because it has the
clearest modular boundaries, a stable CLI, a versioned plan/timeline, and
passing focused tests. Backend video jobs must run against an isolated copy of
that engine and per-job input/output directories: calling the existing CLI in
place would overwrite its `data/scene_plan.json`, timeline, or generated output.
The existing `god1/` and `universal_video/` projects remain untouched and are
documented as potential future adapters.

No existing project files or generated media are to be moved, renamed, or
overwritten. The backend is independently testable with local/mock AI and video
providers; real Gemini credentials and OS video-rendering dependencies are
optional.

## Backend baseline and constraints

No backend framework, ORM, migrations, auth, or tests existed at the workspace
root. FastAPI, Pydantic, HTTPX, pytest, and Google GenAI are available in the
current Python environment. SQLAlchemy, Alembic, JWT/auth helper, and Argon2
packages were not installed at audit time. Python 3.11 is available; `a/`
documents Python 3.11+ and Manim 0.21.x.

## Implementation boundary

The backend is being added as a runnable foundation. Its implemented scope and
verified status are tracked in `docs/IMPLEMENTATION_STATUS.md`; functionality
that requires unavailable real credentials, rendering services, or teacher
authorization setup must be marked accordingly rather than described as
complete.
