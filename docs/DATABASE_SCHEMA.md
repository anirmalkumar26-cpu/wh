# Database schema

The initial Alembic migration is
`backend/migrations/versions/5e0cb3d62a67_initial_backend_schema.py`. SQLite is
the development default; SQLAlchemy URLs also support PostgreSQL when the
configured driver is installed.

| Table | Important fields and relationships |
|---|---|
| `users` | Unique normalized email, Argon2 hash, student/teacher/administrator role, active flag |
| `auth_sessions` | User FK, unique token ID, token family, access/refresh kind, expiration, revocation timestamp |
| `lessons` | Owner FK, topic, optional directly supplied notes, depth, validated structured JSON |
| `concepts` | Shared canonical name, description, subject, difficulty |
| `concept_relationships` | Concept source/target FKs and relation type; unique triple; prerequisite direction is prerequisite → dependent concept |
| `assessments` | Owner and lesson FKs, question/answer-key JSON |
| `assessment_attempts` | Assessment and user FKs, score, maximum, recorded answer evidence |
| `concept_mastery` | User/concept FKs, transparent state/score/evidence; unique per user and concept |
| `learning_paths` | User and target-concept FKs, ordered step snapshot and revision |
| `video_jobs` | Owner and lesson FKs, status/stage/progress, sanitized failure/report JSON |

User-owned records use foreign keys with cascade deletion. Large audio/video
files remain outside the database in `backend/data/video_jobs/`; database
records store report metadata and a constrained relative output reference.
SQLite connections explicitly enable foreign-key enforcement.

Assessment answers and lesson notes are stored to support history and
personalization. They are not included in application logs. Configurable
retention/deletion workflows and administrative audit tables remain future
work.
