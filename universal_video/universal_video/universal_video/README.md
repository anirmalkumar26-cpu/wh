# Universal Video

Turn educational text into a Gemini-assessed, timed scene plan and narrated
Manim video with subtitles.

## Module chain

`main.py` orchestrates independent stages:

1. `assessment.py` assesses difficulty, target duration, and expansion needs.
2. `expansion.py` optionally creates a self-contained teaching script.
3. `planning.py` generates and normalises the scene plan (`scene.json`).
4. `audio.py` creates per-segment TTS WAV files and concatenates narration.
5. `subtitles.py` derives segment start/end times from the generated audio.
6. `rendering.py` performs a clean Manim render and writes the final media.

The stages exchange explicit `Path` and JSON-compatible `dict` values. The
Gemini key is never stored in the project; it is read from `GEMINI_API_KEY`.

## Setup

1. Install Python 3.10+ and the Manim system dependencies.
2. Install packages:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Set your Gemini key (get one from Google AI Studio):

   ```powershell
   $env:GEMINI_API_KEY = "your-key"
   ```

4. Put the text you want to animate in `educational_input.txt` (or pass
   `--input`).

## Run

```powershell
python main.py --input educational_input.txt --json scene.json --output-dir media
```

The application uses the current `gemini-3.5-flash-lite` model by default. You can
select another available model with `--model`. Gemini first assesses difficulty
and target duration, and expands short source material when it needs more
teaching context. It then returns scenes with narration and subtitle segments.

This writes `scene.json`, `media\narration.wav`, and
`media\generated_video.mp4`. Each narration segment is synthesized separately;
the resulting audio durations become the subtitle and scene timings, keeping
visuals, captions, and speech aligned. Every run uses a unique hidden
`.render-<unique-id>` Manim media directory and atomically replaces the final
video/audio, so stale frames, caches, and partial outputs cannot leak into a
new render. Plans support text/labels, circles, rectangles, ellipses, lines,
arrows, polygons/triangles, stars, arcs, dots, and axes, with safe colors,
labels, and lightweight entrance/motion animations. The default is high-quality rendering; use `--quality l` for a quick
preview or `--quality p` for production quality. To only generate JSON, run `python planner.py`; to render an existing plan, run
`python renderer.py --input scene.json --output-dir media`.

For a syntax/import check (no API calls):

```powershell
python -m py_compile *.py
python -c "import main, planning, assessment, expansion, audio, subtitles, rendering"
```
