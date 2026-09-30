# Enterprise Multi-Modal RAG & Document Intelligence Workspace

Vanco is a full-stack workspace for private document ingestion, OCR, hybrid retrieval, cited question answering, and operational visibility. The repository contains a Next.js App Router frontend, an async FastAPI service, PostgreSQL with pgvector, Redis-backed ingestion, and Alembic migrations.

## Start the complete stack

Requirements: Docker Desktop with Compose v2. From the repository root:

```powershell
Copy-Item .env.example .env
# Edit .env and set strong POSTGRES_PASSWORD and SECRET_KEY values.
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000). The API is at [http://localhost:8000](http://localhost:8000), its OpenAPI reference is at [http://localhost:8000/docs](http://localhost:8000/docs), and its dependency health endpoint is [http://localhost:8000/health](http://localhost:8000/health). Create an account from the sign-in screen. The workspace is scoped to that account.

Without an `OPENAI_API_KEY`, PDF and image extraction, OCR, chunking, local feature-hash embeddings, vector/full-text retrieval, citation display, and lifecycle metrics still work. The local embedding fallback is intended for development and is not a substitute for a production semantic embedding model. Set an OpenAI key to enable OpenAI embeddings and synthesized chat answers. The configured embedding model must produce 1,536 dimensions.

To stop the stack, run `docker compose down`. Persistent database, Redis, and uploaded files live in named volumes. `docker compose down -v` deletes those volumes and their data.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | Enables OpenAI embeddings and answer generation; optional for local development | Empty |
| `OPENAI_CHAT_MODEL` | OpenAI chat completion model | `gpt-4o-mini` |
| `OPENAI_EMBEDDING_MODEL` | OpenAI embedding model; must return 1,536 dimensions | `text-embedding-3-small` |
| `DATABASE_URL` | Async SQLAlchemy URL. Compose constructs this from the PostgreSQL variables. | `postgresql+asyncpg://vanco:vanco@localhost:5432/vanco` |
| `REDIS_URL` | Redis URL for the ingestion queue and rate limits | `redis://localhost:6379/0` |
| `SECRET_KEY` | HS256 JWT signing key; use a unique secret with at least 32 random characters in deployments | Development-only fallback |
| `POSTGRES_DB` | Compose database name | `vanco` |
| `POSTGRES_USER` | Compose database user | `vanco` |
| `POSTGRES_PASSWORD` | Compose database password | Development-only fallback |
| `NEXT_PUBLIC_API_URL` | Public API base URL compiled into the frontend image | `http://localhost:8000/api/v1` |
| `CORS_ORIGINS` | Comma-separated frontend origins accepted by the API | `http://localhost:3000` |
| `UPLOAD_DIR` | Backend file storage directory | `/app/storage` in Compose |

The frontend API URL is baked into the Next.js build. For a non-local deployment, set `NEXT_PUBLIC_API_URL` to the externally reachable API URL before building the frontend image. Keep secrets out of source control and use a secret manager for production.

## Local development

Start PostgreSQL and Redis first (for example, `docker compose up -d postgres redis`). Then create a Python 3.11+ environment and install the backend dependencies:

```powershell
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1
python -m pip install -r backend/requirements.txt
$env:DATABASE_URL = "postgresql+asyncpg://vanco:local-development-only@localhost:5432/vanco"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:UPLOAD_DIR = "./storage"
Set-Location backend
alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal:

```powershell
Set-Location frontend
npm install
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000/api/v1"
npm run dev
```

For local backend development without a `.env` file, provide the environment variables shown above in the shell. The Compose path reads the root `.env` automatically.

## Database migrations

Compose runs `alembic upgrade head` before starting the backend. To apply migrations manually from `backend/` with `DATABASE_URL` set:

```powershell
alembic upgrade head
```

The initial migration creates the `vector` extension and relational/index schema. To inspect the current migration revision, run `alembic current`; to create a future migration after model changes, run `alembic revision --autogenerate -m "describe change"`, review the generated migration, and apply it with `alembic upgrade head`.

## Tests and checks

```powershell
Set-Location backend
python -m pip install pytest
python -m pytest
python -m compileall -q app migrations

Set-Location ../frontend
npm run lint
npm run build
```

For a running stack, verify `GET /health`, register/sign in, upload a PDF or image, wait for `COMPLETED`, ask a question in the chat, open a citation, and inspect `/admin`. Unsupported file types, empty files, files over 25 MB, bad credentials, and user-owned resource boundaries are validated by the API.

## Application layout

```text
backend/app/api/v1/       Auth, document, chat, and observability routes
backend/app/core/         Settings, async database, JWT security, rate limits
backend/app/models/       PostgreSQL and pgvector ORM schema
backend/app/schemas/      Typed API request and response models
backend/app/services/     OCR, chunking, embeddings, RRF retrieval, RAG
backend/migrations/       Alembic environment and initial schema revision
frontend/src/app/         Overview, documents, chat, and observability routes
frontend/src/components/  Workspace shell and reusable interface elements
frontend/src/lib/         Typed API client and shared response types
docker-compose.yml        PostgreSQL, Redis, backend, frontend, named volumes
```

## Operational notes

- Uploaded content is private to its owner at API query time. The demo has account-level access, not organization/role administration or SSO.
- The API enforces per-IP registration/login limits and per-user upload/chat limits with Redis. Reverse proxy deployments must configure trusted proxy handling before relying on client IP limits.
- The ingestion worker runs inside the API process and consumes a Redis list. For multiple API replicas or independently scaled jobs, move ingestion to a dedicated worker process and use a durable queue with retry/dead-letter policy.
- Tesseract OCR is installed in the backend image. Local machine OCR additionally requires the Tesseract executable on `PATH`.
- The admin/observability page reports the signed-in user's workspace metrics; it is not a cross-tenant super-admin console.
- Before production use, configure TLS, strong secrets, database backups, object storage and retention, email verification/account recovery, authorization policy, audit retention, and provider/data-processing controls.
