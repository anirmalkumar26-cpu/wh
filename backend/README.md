# WH Backend

This is an independent FastAPI backend at the workspace root. Run commands from
the workspace root so `backend.app` imports and the existing `a/` video engine
resolve consistently.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
python -m alembic -c backend\alembic.ini upgrade head
python run.py
```

The backend uses a deterministic local lesson provider when `WH_AI_PROVIDER=auto`
and no Gemini key is present. `/api/v1/health` and all tests therefore work
without paid API credentials. Set `WH_AI_PROVIDER=gemini`, `GEMINI_API_KEY`, and
optionally `WH_GEMINI_MODEL` to enable lesson generation with Gemini. The provider
requests JSON and validates it against the lesson schema.

Set `WH_JWT_SECRET` to a random secret before deployment and set `WH_ENV=production`.
`WH_DATABASE_URL` accepts SQLite and SQLAlchemy PostgreSQL URLs. Use the
repeatable migration command above after changing models. A teacher or
administrator account can be created only from an administrator account;
create the first administrator interactively with:

```powershell
python -m backend.app.scripts.create_admin
```

Student self-registration always creates the student role. Access tokens expire
after 20 minutes by default; refresh tokens rotate and are stored/revoked by
token family. Logout revokes the current token family.

## Run and test

```powershell
python run.py
python -m pytest backend\tests -q
```

OpenAPI UI and schema: `http://127.0.0.1:8000/docs` and
`http://127.0.0.1:8000/openapi.json`.

## Main endpoints

All API routes are under `/api/v1`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Database and provider health |
| POST | `/auth/register` | Register a student and issue tokens |
| POST | `/auth/login` | Authenticate and issue tokens |
| POST | `/auth/refresh` | Rotate a refresh-token family |
| POST | `/auth/logout` | Revoke the signed-in token family |
| GET | `/auth/me` | Current account |
| POST | `/admin/users` | Administrator creates teacher/admin accounts |
| POST | `/lessons` | Create a topic- or text-based lesson |
| GET | `/lessons/{lesson_id}` | Retrieve an owned lesson |
| GET/POST | `/knowledge-graph` and `/knowledge-graph/concepts` | Read graph / add a concept |
| POST | `/knowledge-graph/relationships` | Add a relationship with prerequisite-cycle validation |
| GET | `/knowledge-graph/concepts/{id}/prerequisites` | Read direct prerequisites |
| POST | `/learning/paths` | Build a persisted prerequisite path |
| GET | `/learning/paths` | List the current student's paths |
| GET | `/progress` | Current student's evidence-derived mastery |
| GET | `/recommendations` | Explainable next-concept recommendation |
| POST | `/assessments` | Generate a deterministic objective quiz |
| POST | `/assessments/{id}/submit` | Score objective answers and update mastery |
| GET | `/assessments/{id}/attempts` | List owned assessment attempts |
| POST | `/videos/jobs` | Queue a persistent video job |
| GET | `/videos/jobs/{id}` | Read owned job state |
| POST | `/videos/jobs/{id}/retry` | Retry a failed job |
| GET | `/videos/jobs/{id}/download` | Download an owned completed video |

## Example flow

Register (password requires 12+ characters and upper/lowercase plus a digit):

```powershell
$user = Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/auth/register `
  -ContentType application/json `
  -Body '{"email":"student@example.com","password":"StrongPass1234"}'
$headers = @{ Authorization = "Bearer $($user.access_token)" }
```

Create a lesson and then an assessment:

```powershell
$lesson = Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/lessons `
  -Headers $headers -ContentType application/json `
  -Body '{"topic":"AVL Tree Right Rotation","depth":"beginner"}'
$quiz = Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/assessments `
  -Headers $headers -ContentType application/json `
  -Body (@{ lesson_id = $lesson.id; question_count = 3 } | ConvertTo-Json)
```

Submit answers by question ID (the sample AVL quiz's correct choice is `B`):

```powershell
$answers = @{}
foreach ($question in $quiz.questions) { $answers[$question.id] = "B" }
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/v1/assessments/$($quiz.id)/submit" `
  -Headers $headers -ContentType application/json `
  -Body (@{ answers = $answers } | ConvertTo-Json)
```

## Video adapter

The adapter copies `a/educational_video/` and `a/main.py` into an isolated
per-job directory before invoking the existing CLI. It never writes to the
original `a/data/` or `a/output/` sample paths. The current engine uses Windows
SAPI/PowerShell, Manim, and FFmpeg; rendering can fail where these dependencies
are not available. Jobs persist their status and sanitized error report. The
adapter currently turns validated lesson sections into captioned segments; it
does not synthesize arbitrary visual diagrams or execute AI-produced code.

## Manual integration testing

Use a non-production database and a valid Gemini key only when testing
`WH_AI_PROVIDER=gemini`. Confirm `/api/v1/health`, create a student, generate a
lesson, and validate that the returned structured JSON meets the documented
schema. For real video output, install the existing `a/requirements.txt` and
Manim system dependencies (including FFmpeg), verify Windows SAPI is available,
queue a video job, poll until complete, download it, and inspect the validation
metadata. This integration requires no changes to the existing pipeline.
