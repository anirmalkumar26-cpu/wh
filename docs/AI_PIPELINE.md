# AI provider and learning pipeline

`backend/app/ai/providers.py` defines a lesson-provider protocol with two
implementations:

- `MockLessonProvider` is deterministic and selected by default if no Gemini
  key is configured. It supports local tests and explicitly treats supplied
  notes as unverified.
- `GeminiLessonProvider` uses the supported `google-genai` SDK, configured
  model and timeout, asks for JSON, validates the result against Pydantic lesson
  models, and retries bounded 429/5xx/connection-timeout errors.

Set `WH_AI_PROVIDER=gemini` and `GEMINI_API_KEY` to use Gemini. In development,
a missing key logs an explicit warning and selects the local mock even if
Gemini was selected. A non-development environment refuses to start without a
key. No implicit internet search is performed by Gemini; research grounding,
search providers, citation storage, cost/usage monitoring, and TTS/alignment
provider interfaces are not implemented.

Flow:

`validated topic/notes -> LessonProvider -> Pydantic LessonContent -> lesson and graph persistence -> assessment/path/video services`

Prompts tell Gemini to treat user notes as untrusted content. Structured output
is still considered untrusted until schema validation completes. The backend
does not accept executable code or arbitrary rendering instructions from the
model.
