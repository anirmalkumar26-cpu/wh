# Backend architecture

The new application is independent from the three existing video projects. It
uses FastAPI for the HTTP/OpenAPI layer, SQLAlchemy for relational persistence,
Pydantic for input and generated-output validation, and services for transactional
business logic. SQLAlchemy's relational graph representation can be replaced
behind `services/graph.py` without changing the HTTP routes.

## Main modules

| Module | Responsibility |
|---|---|
| `backend/app/main.py` | App factory, dependency wiring, CORS, health, OpenAPI |
| `backend/app/core/config.py` | `.env` and environment configuration |
| `backend/app/core/database.py` | SQLAlchemy engine, SQLite setup, session lifetime |
| `backend/app/core/security.py` | Argon2 password hashing and signed access/refresh tokens |
| `backend/app/models.py` | Persistent account, lesson, graph, assessment, mastery, path, and video-job entities |
| `backend/app/schemas.py` | Validated API request and lesson-response contracts |
| `backend/app/ai/providers.py` | Local mock and optional Gemini lesson providers |
| `backend/app/api/` | Versioned routes, authentication dependencies, and role checks |
| `backend/app/services/auth.py` | Registration, login, refresh-token rotation, revocation |
| `backend/app/services/learning.py` | Lesson persistence, path creation, progress-driven recommendations |
| `backend/app/services/graph.py` | Concept storage, relationship checks, traversal, cycle detection |
| `backend/app/services/assessment.py` | Deterministic objective questions, scoring, evidence, mastery |
| `backend/app/services/video_jobs.py` | Persistent video-job execution and error state |
| `backend/app/video/adapter.py` | Isolated bridge to the existing `a/educational_video` CLI |
| `backend/migrations/` | Alembic environment and initial schema migration |

## Data flows

1. Student registration validates email/password, stores only an Argon2 hash,
   and creates a persisted access/refresh token family. API dependencies verify
   token signatures and session revocation before resolving the current user.
2. Lesson requests validate topic or notes and depth. A mock or Gemini provider
   returns a schema-validated lesson. The lesson, shared concept definition, and
   prerequisite links are then stored.
3. Assessments expose question choices but not answers. The deterministic
   evaluator records attempts and evidence, calculates transparent mastery
   states, and feeds learning-path/recommendation services.
4. Video requests create a database job before returning `202 Accepted`.
   FastAPI background processing invokes the adapter after the response. The
   adapter copies only the existing engine's source into a job-scoped directory,
   so its fixed data/output paths cannot overwrite the original engine samples.

## Trust and ownership boundaries

Student-created resources are filtered by their owner on retrieval and mutation.
Graph concept definitions are shared and graph mutation is teacher/admin-only
(lesson generation can add extracted definitions); student evidence and mastery are
user-specific. User-provided notes are constrained and described as unverified
in the local provider. Gemini output is treated as untrusted JSON and validated
before persistence. The current implementation does not ingest web content,
execute model-generated code, or expose server filesystem paths through API
responses.
