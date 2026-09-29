# Development setup

Run these commands from the workspace root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
python -m alembic -c backend\alembic.ini upgrade head
python run.py
```

The API and OpenAPI UI are available at `http://127.0.0.1:8000` and
`http://127.0.0.1:8000/docs`. `.env` is loaded from the workspace root.

The mock lesson provider is selected when a Gemini key is absent, so startup
and automated tests do not require paid services. To explicitly use Gemini,
set `WH_AI_PROVIDER=gemini` and `GEMINI_API_KEY` in `.env`. Before production,
set `WH_ENV=production`, use a random `WH_JWT_SECRET` of at least 32 characters,
configure allowed `WH_CORS_ORIGINS`, choose an appropriate PostgreSQL
`WH_DATABASE_URL`, and run migrations before starting the service.

Create the first administrator interactively (no password is embedded in code):

```powershell
python -m backend.app.scripts.create_admin
```

Run backend tests with `python -m pytest backend\tests -q`. The original video
pipeline tests are run from its own project directory:
`Push-Location a; python -m pytest tests -q; Pop-Location`.
See [backend/README.md](../backend/README.md) for endpoint examples and the
manual video-rendering integration checklist.
