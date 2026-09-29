import os
import json
import sys
from pathlib import Path
from typing import List, Optional, Literal

from google import genai
from pydantic import BaseModel, Field


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_NAME = "gemini-3.6-flash"

OUTPUT_FILE = "scene_plan.json"

API_KEY = os.getenv("GEMINI_API_KEY")

# Default teaching pace.
# These are instructions to the future Manim renderer.
DEFAULT_ACTION_DURATION = 1.2
DEFAULT_PAUSE_AFTER_ACTION = 0.6
DEFAULT_PAUSE_AFTER_EXPLANATION = 1.0
DEFAULT_SCENE_BUFFER = 1.5


# ============================================================
# DATA MODELS
# ============================================================

class Timing(BaseModel):
    """
    Explicit timing information.

    The renderer should respect these values instead of
    making every animation extremely fast.
    """

    duration: float = Field(
        default=DEFAULT_ACTION_DURATION,
        description="Animation duration in seconds."
    )

    pause_after: float = Field(
        default=DEFAULT_PAUSE_AFTER_ACTION,
        description=(
            "Pause after this action so the learner has time "
            "to understand what happened."
        )
    )

    wait_before: float = Field(
        default=0.0,
        description=(
            "Pause before this action begins."
        )
    )


class VisualObject(BaseModel):
    id: str = Field(
        description=(
            "Stable unique identifier. "
            "This ID must NEVER change when the object persists "
            "between animation states."
        )
    )

    type: str = Field(
        description=(
            "Visual type such as circle, rectangle, arrow, line, "
            "node, linked_list_node, array_cell, graph, tree, "
            "pointer, label, text, equation, etc."
        )
    )

    label: Optional[str] = Field(
        default=None,
        description="Short visible label."
    )

    content: Optional[str] = Field(
        default=None,
        description="Visible text, number, formula, or value."
    )

    color: Optional[str] = Field(
        default=None,
        description=(
            "Semantic color: blue, green, orange, red, "
            "yellow, white, etc."
        )
    )

    position: Optional[str] = Field(
        default=None,
        description=(
            "Position or anchor. Examples: center, left, right, "
            "above node_1, below array_3."
        )
    )

    size: Optional[str] = Field(
        default=None,
        description="Relative visual size."
    )

    purpose: str = Field(
        description="Why this object is pedagogically important."
    )

    persistent: bool = Field(
        default=True,
        description=(
            "If true, preserve this object across states/scenes "
            "unless explicitly removed."
        )
    )


class Relationship(BaseModel):
    id: str = Field(
        description="Stable relationship identifier."
    )

    source: str = Field(
        description="Source object ID."
    )

    target: str = Field(
        description="Target object ID."
    )

    type: str = Field(
        description=(
            "Relationship such as points_to, connected_to, "
            "contains, compares_with, moves_toward, etc."
        )
    )

    visual_representation: str = Field(
        description=(
            "arrow, line, brace, path, boundary, pointer, etc."
        )
    )

    importance: str = Field(
        description="Why this relationship matters."
    )

    persistent: bool = Field(
        default=True,
        description="Whether the relationship should remain visible."
    )


class AnimationAction(BaseModel):
    order: int = Field(
        description="Execution order."
    )

    phase: Literal[
        "explain",
        "introduce",
        "demonstrate",
        "compare",
        "transition",
        "result",
        "reinforce"
    ] = Field(
        description=(
            "Educational phase of the action."
        )
    )

    action: str = Field(
        description=(
            "create, move, transform, highlight, connect, "
            "disconnect, swap, grow, shrink, fade_in, fade_out, "
            "indicate, replace, rotate, change_color, reveal, "
            "compare, trace, follow_path, wait."
        )
    )

    target: str = Field(
        description="Object or relationship ID."
    )

    description: str = Field(
        description=(
            "Exactly what should visually happen."
        )
    )

    timing: Timing = Field(
        default_factory=Timing,
        description="Timing and pacing information."
    )

    educational_reason: str = Field(
        description=(
            "What the learner should understand."
        )
    )

    narration: Optional[str] = Field(
        default=None,
        description=(
            "Short narration associated with this action."
        )
    )

    preserve_existing_objects: bool = Field(
        default=True,
        description=(
            "Do not erase unrelated objects while performing "
            "this action."
        )
    )


class StateTransition(BaseModel):
    """
    Describes the state before and after an important process.

    This is particularly useful for algorithms.
    """

    from_state: str = Field(
        description="Description of the current visual state."
    )

    to_state: str = Field(
        description="Description of the resulting visual state."
    )

    changed_objects: List[str] = Field(
        description=(
            "IDs of objects whose state/position/value changed."
        )
    )

    unchanged_objects: List[str] = Field(
        description=(
            "IDs that must remain visually continuous."
        )
    )

    explanation: str = Field(
        description="Why the transition happens."
    )


class Scene(BaseModel):
    id: str = Field(
        description="Unique scene identifier."
    )

    title: str = Field(
        description="Short scene title."
    )

    purpose: str = Field(
        description="What this scene teaches."
    )

    narration: Optional[str] = Field(
        default=None,
        description="Short scene-level narration."
    )

    visual_objects: List[VisualObject] = Field(
        description="Objects introduced or required by this scene."
    )

    relationships: List[Relationship] = Field(
        description="Important relationships."
    )

    actions: List[AnimationAction] = Field(
        description="Ordered actions."
    )

    state_transitions: List[StateTransition] = Field(
        default_factory=list,
        description="Important before/after states."
    )

    explanation_pause: float = Field(
        default=DEFAULT_PAUSE_AFTER_EXPLANATION,
        description=(
            "Pause after explaining an important concept "
            "before performing the visual action."
        )
    )

    scene_buffer: float = Field(
        default=DEFAULT_SCENE_BUFFER,
        description=(
            "Small pause at the end of the scene before "
            "transitioning."
        )
    )

    transition_to_next: str = Field(
        description="How this scene transitions to the next."
    )


class ScenePlan(BaseModel):
    topic: str

    learning_objective: str

    audience_level: str

    visual_strategy: str

    key_concepts: List[str]

    scenes: List[Scene]

    final_visual_summary: str


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = r"""
You are an expert educational animation director designing
animations for Manim Community Edition.

Your task is to transform educational material into a
SLOW, CLEAR, VISUAL, CONTINUOUS teaching animation.

The most important rule is:

THE VIEWER MUST HAVE TIME TO UNDERSTAND EACH VISUAL CHANGE.

Do NOT create a fast slideshow.

Do NOT make every animation happen immediately.

Do NOT repeatedly erase and redraw the whole scene.

The animation should feel like an excellent teacher explaining
something on a whiteboard.

============================================================
TEACHING RHYTHM
============================================================

Use this general rhythm whenever appropriate:

1. Explain what the learner is about to see.
2. Pause briefly.
3. Introduce the visual object.
4. Pause.
5. Perform the visual operation.
6. Pause.
7. Explain what changed.
8. Continue to the next operation.

Important algorithmic operations should normally take around
1 to 2 seconds or longer when the movement is conceptually
important.

Do not use extremely short animations such as 0.1 or 0.2 seconds
for important concepts.

Typical defaults:

- create/reveal object: 0.8–1.2 sec
- important movement: 1.2–2.0 sec
- highlight: 0.7–1.2 sec
- comparison: 1.0–1.5 sec
- major transition: 1.5–2.5 sec
- pause after important action: 0.6–1.2 sec
- explanation pause: approximately 1 sec

These are guidelines, not rigid requirements.

============================================================
PERSISTENT VISUAL STATE
============================================================

This is EXTREMELY IMPORTANT.

Objects should persist whenever possible.

If a linked list initially contains:

A → B

and we add C:

A → B → C

DO NOT recreate A and B.

Keep the exact same object IDs:

node_A
node_B

and create:

node_C

Then create/update the relationship:

node_B → node_C

Likewise, if a binary search array has:

[10, 20, 30, 40, 50, 60, 70]

do NOT redraw the entire array every time.

Keep the same array cells.

Move/highlight:

low
high
mid

and change their state.

The learner should visually recognize that it is the
SAME array and the search region is shrinking.

============================================================
NO OVERWRITING
============================================================

Never solve a new state by simply replacing the old scene.

If an object is no longer relevant:

- move it
- fade it intentionally
- mark it inactive
- change its color
- shrink it
- move it outside the active region

Only remove an object when there is a genuine pedagogical reason.

Do NOT accidentally overwrite important visual history.

============================================================
LINKED LIST RULE
============================================================

For a linked list explanation:

FIRST explain what a node is.

Then:

1. Show an empty area.
2. Introduce ONE node.
3. Explain the node's value.
4. Show its data portion.
5. Show its next/reference portion if relevant.
6. Pause.
7. Introduce the second node.
8. Connect node 1 → node 2.
9. Pause.
10. Introduce the third node.
11. Connect node 2 → node 3.
12. Continue.

The learner should visibly see the list being built.

Do not instantly show:

A → B → C → D

unless the educational purpose specifically requires
showing the completed state.

When a new node appears, use a distinct ID.

Example:

node_1
node_2
node_3

The existing nodes must remain persistent.

============================================================
BINARY SEARCH RULE
============================================================

For binary search, explicitly visualize:

1. The sorted array.
2. The target.
3. low.
4. high.
5. mid.
6. The comparison.
7. The half that is eliminated.
8. The movement of low/high.
9. The new mid.
10. Repeat.

For example:

low = 0
high = 6
mid = 3

Then:

Compare target with array[mid].

If target > array[mid]:

Explain:

"The target is larger, so everything at or below mid
can be eliminated."

Then visually shrink/fade/de-emphasize the left portion.

Then move:

low → mid + 1

Then calculate/show the new mid.

Do NOT instantly teleport to the final answer.

The viewer should SEE:

old low
old high
old mid

then the transition to:

new low
new high
new mid

Use different semantic colors:

low = blue
high = orange
mid = yellow
target = green
eliminated region = muted/red/gray

============================================================
ALGORITHMS IN GENERAL
============================================================

Algorithms should be animated as a PROCESS.

Never just show:

"Step 1"
"Step 2"
"Step 3"

Instead show the actual state transition.

For example, sorting:

Before:
[5, 2, 8, 1]

Compare 5 and 2.

Highlight both.

Pause.

Swap them.

Animate the movement.

Pause.

Then compare the next pair.

The viewer should understand WHY the swap occurred.

============================================================
CODE + VISUAL
============================================================

If programming material contains code:

Do not make the code the main animation.

Use code as supporting context.

For example:

if (arr[mid] < target)

The visual array should simultaneously show:

arr[mid]
target
comparison

The code line may be highlighted while the actual data
structure performs the operation.

============================================================
NARRATION
============================================================

Narration should explain the current visual state.

Avoid huge narration paragraphs.

Good:

"First, we need to find the middle element."

Then show the middle.

Then:

"The target is larger than the middle value."

Then move the search boundary.

Narration and animation should be synchronized conceptually.

============================================================
ACTION PHASES
============================================================

Every important action should have one of these phases:

explain
introduce
demonstrate
compare
transition
result
reinforce

Example:

Action 1:
phase = explain

Narration:
"We first identify the middle element."

Action 2:
phase = demonstrate

Action:
highlight mid

Action 3:
phase = compare

Action:
compare target with mid

Action 4:
phase = transition

Action:
move low

============================================================
TIMING
============================================================

Never assign extremely short durations to important operations.

Prefer human teaching speed.

Every important action must include:

duration
wait_before
pause_after

The pause is part of the teaching design.

============================================================
CONTINUITY BETWEEN SCENES
============================================================

Scenes are NOT independent slides.

Objects from earlier scenes may continue into later scenes.

If scene 1 creates:

node_1
node_2

then scene 2 should be allowed to use:

node_1
node_2

without recreating them.

When an object persists, keep exactly the same ID.

============================================================
SCENE DESIGN
============================================================

A scene should represent a meaningful conceptual unit.

Good:

Scene:
"Building the linked list"

Actions:
introduce node
explain node
introduce next node
connect nodes
pause
introduce third node
connect nodes

Bad:

Scene 1:
"Node"

Scene 2:
"Node 2"

Scene 3:
"Arrow"

Avoid tiny slideshow-like scenes.

============================================================
FINAL STATE
============================================================

At the end, show a stable visual summary.

Prefer reusing existing objects.

For a linked list:

head → node1 → node2 → node3 → null

For binary search:

array + target + final low/high/mid state

The viewer should be able to look at the final frame and
understand the main idea.

============================================================
MANIM COMPATIBILITY
============================================================

Use visual concepts that can be implemented with:

Circle
Square
Rectangle
RoundedRectangle
Line
Arrow
DoubleArrow
Brace
Polygon
VGroup
MathTex
Tex
Text
NumberPlane
Axes
Dot
Graph

and:

Create
Write
FadeIn
FadeOut
Transform
ReplacementTransform
MoveToTarget
Indicate
Circumscribe
GrowArrow
LaggedStart
AnimationGroup

Avoid external assets.

============================================================
OUTPUT
============================================================

Return ONLY valid structured data matching the schema.

No Markdown.

No commentary.

No Manim code.
"""


# ============================================================
# CLIENT
# ============================================================

def create_client():
    if not API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set.\n"
            "Set your Gemini API key before running."
        )

    return genai.Client(api_key=API_KEY)


# ============================================================
# INPUT
# ============================================================

def read_input() -> str:

    if len(sys.argv) > 1:

        input_path = Path(sys.argv[1])

        if not input_path.exists():
            raise FileNotFoundError(
                f"Input file does not exist: {input_path}"
            )

        return input_path.read_text(
            encoding="utf-8"
        ).strip()

    print("=" * 70)
    print("GEMINI EDUCATIONAL ANIMATION PLANNER")
    print("=" * 70)
    print()
    print("Paste your educational material.")
    print("Finish with Ctrl+Z + Enter on Windows")
    print("or Ctrl+D on Linux/macOS.")
    print()

    return sys.stdin.read().strip()


# ============================================================
# PROMPT
# ============================================================

def build_prompt(source_text: str) -> str:

    return f"""
Create a complete educational animation plan from the source
material below.

The resulting animation must be:

- slow enough to understand
- visually continuous
- process-oriented
- state-based
- persistent
- suitable for Manim
- synchronized with short explanations

IMPORTANT:

Do not jump through algorithm steps.

Do not redraw persistent objects.

Do not overwrite old visual states unnecessarily.

For linked lists, build nodes one by one.

For binary search, explicitly show low, high, mid, comparison,
elimination, boundary movement, and the next mid.

Every important operation needs duration and pause timing.

SOURCE MATERIAL
===============

{source_text}

END SOURCE MATERIAL

Return the complete structured animation plan.
"""


# ============================================================
# GENERATE
# ============================================================

def generate_scene_plan(
    client: genai.Client,
    source_text: str
) -> ScenePlan:

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=build_prompt(source_text),
        config={
            "system_instruction": SYSTEM_PROMPT,
            "response_mime_type": "application/json",
            "response_schema": ScenePlan,
            "temperature": 0.25,
        },
    )

    if not response.text:
        raise RuntimeError(
            "Gemini returned an empty response."
        )

    try:

        return ScenePlan.model_validate_json(
            response.text
        )

    except Exception as exc:

        print("Gemini returned:")
        print(response.text)

        raise RuntimeError(
            "Could not parse Gemini structured output."
        ) from exc


# ============================================================
# PLAN VALIDATION
# ============================================================

def validate_plan(plan: ScenePlan):

    object_ids = set()

    relationship_ids = set()

    for scene in plan.scenes:

        # ----------------------------------------------------
        # Validate object IDs
        # ----------------------------------------------------

        for obj in scene.visual_objects:

            if obj.id in object_ids:

                # Duplicate IDs are allowed ONLY if the object
                # is intentionally persistent across scenes.
                pass

            object_ids.add(obj.id)

        # ----------------------------------------------------
        # Validate relationship IDs
        # ----------------------------------------------------

        for relationship in scene.relationships:

            if relationship.id in relationship_ids:
                raise ValueError(
                    f"Duplicate relationship ID: "
                    f"{relationship.id}"
                )

            relationship_ids.add(
                relationship.id
            )

        # ----------------------------------------------------
        # Validate action order
        # ----------------------------------------------------

        orders = [
            action.order
            for action in scene.actions
        ]

        if orders != sorted(orders):

            raise ValueError(
                f"Actions in scene '{scene.id}' "
                f"are not ordered correctly."
            )

        # ----------------------------------------------------
        # Validate timing
        # ----------------------------------------------------

        for action in scene.actions:

            if action.timing.duration < 0.3:

                raise ValueError(
                    f"Action '{action.description}' "
                    f"is too fast: "
                    f"{action.timing.duration}s"
                )

            if action.timing.pause_after < 0:

                raise ValueError(
                    "pause_after cannot be negative."
                )

            if action.timing.wait_before < 0:

                raise ValueError(
                    "wait_before cannot be negative."
                )


# ============================================================
# SAVE
# ============================================================

def save_plan(
    plan: ScenePlan,
    output_path: str = OUTPUT_FILE
):

    data = plan.model_dump(
        exclude_none=True
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )

    print()
    print("=" * 70)
    print("SCENE PLAN CREATED")
    print("=" * 70)
    print()
    print(f"Topic: {plan.topic}")
    print(f"Audience: {plan.audience_level}")
    print(f"Scenes: {len(plan.scenes)}")
    print(f"Saved to: {output_path}")
    print()


# ============================================================
# PREVIEW
# ============================================================

def print_preview(plan: ScenePlan):

    print()
    print("=" * 70)
    print("VISUAL ANIMATION PREVIEW")
    print("=" * 70)

    print()
    print("TOPIC:")
    print(plan.topic)

    print()
    print("LEARNING OBJECTIVE:")
    print(plan.learning_objective)

    print()
    print("VISUAL STRATEGY:")
    print(plan.visual_strategy)

    print()
    print("KEY CONCEPTS:")

    for concept in plan.key_concepts:
        print(f"  - {concept}")

    print()
    print("SCENES:")

    total_duration = 0.0

    for index, scene in enumerate(
        plan.scenes,
        start=1
    ):

        scene_duration = 0.0

        for action in scene.actions:

            scene_duration += (
                action.timing.wait_before
                + action.timing.duration
                + action.timing.pause_after
            )

        scene_duration += (
            scene.explanation_pause
            + scene.scene_buffer
        )

        total_duration += scene_duration

        print()
        print(
            f"{index}. {scene.title}"
        )

        print(
            f"   Purpose: {scene.purpose}"
        )

        print(
            f"   Objects: "
            f"{len(scene.visual_objects)}"
        )

        print(
            f"   Relationships: "
            f"{len(scene.relationships)}"
        )

        print(
            f"   Actions: "
            f"{len(scene.actions)}"
        )

        print(
            f"   Estimated duration: "
            f"{scene_duration:.1f}s"
        )

    print()
    print(
        f"Estimated total animation time: "
        f"{total_duration:.1f}s"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    try:

        source_text = read_input()

        if not source_text:
            raise ValueError(
                "No educational text was provided."
            )

        print()
        print(
            f"Input length: "
            f"{len(source_text):,} characters"
        )

        print()
        print(
            "Sending material to Gemini..."
        )

        print(
            "Designing slow, continuous teaching animation..."
        )

        client = create_client()

        plan = generate_scene_plan(
            client,
            source_text
        )

        print(
            "Validating animation plan..."
        )

        validate_plan(plan)

        save_plan(
            plan,
            OUTPUT_FILE
        )

        print_preview(plan)

        print()
        print("=" * 70)
        print("DONE")
        print("=" * 70)
        print()
        print(
            f"Your renderer can now read: {OUTPUT_FILE}"
        )
        print()

    except KeyboardInterrupt:

        print(
            "\nOperation cancelled."
        )

        sys.exit(1)

    except Exception as exc:

        print()
        print("ERROR:")
        print(str(exc))

        sys.exit(1)


if __name__ == "__main__":
    main()
