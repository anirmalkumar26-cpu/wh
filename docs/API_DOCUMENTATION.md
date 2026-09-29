# API documentation

The OpenAPI schema is served by the running app at `/openapi.json`, with Swagger
UI at `/docs`. All routes are versioned under `/api/v1`; protected routes require
`Authorization: Bearer <access_token>`.

| Method | Endpoint | Access / behavior |
|---|---|---|
| GET | `/health` | Public database/provider health |
| POST | `/auth/register` | Public student registration |
| POST | `/auth/login` | Public login |
| POST | `/auth/refresh` | Public refresh-token rotation |
| POST | `/auth/logout` | Signed-in user; revokes token family |
| GET | `/auth/me` | Current account |
| POST | `/admin/users` | Administrator creates teacher/administrator |
| POST, GET | `/lessons`, `/lessons/{lesson_id}` | Authenticated; lesson retrieval is owner-only |
| GET | `/knowledge-graph` | Authenticated graph including only the caller's mastery |
| POST, GET | `/knowledge-graph/concepts` | Teacher/admin create concepts; authenticated callers list the shared catalog |
| POST | `/knowledge-graph/relationships` | Teacher/admin only; rejects missing concepts/cycles |
| GET | `/knowledge-graph/concepts/{concept_id}/prerequisites` | Authenticated direct prerequisites |
| POST, GET | `/learning/paths` | Create/list caller's persisted paths |
| GET | `/progress` | Current user's mastery and not-assessed concepts |
| GET | `/recommendations` | Explainable recommendation; optional `target_concept_id` query |
| POST | `/assessments` | Create quiz for an owned lesson |
| POST | `/assessments/{assessment_id}/submit` | Submit answers and receive scoring/feedback |
| GET | `/assessments/{assessment_id}/attempts` | List caller's attempts |
| POST | `/videos/jobs` | Create persistent job and return 202 |
| GET | `/videos/jobs/{job_id}` | Read caller's job status |
| POST | `/videos/jobs/{job_id}/retry` | Retry caller's failed job |
| GET | `/videos/jobs/{job_id}/download` | Authorized completed-video download |

Lesson request:

```json
{"topic": "AVL Tree Right Rotation", "depth": "beginner"}
```

or:

```json
{"text": "My notes about AVL rotations ...", "depth": "intermediate"}
```

Exactly one of `topic` and `text` is required. The generated lesson includes an
overview, objectives, prerequisites, structured sections, key terms, common
mistakes, review questions, and recap. Requests, generated lessons, and
assessment attempts are validated at the API boundary.
