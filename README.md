# FinSight

FinSight is a secure, auditable retrieval-augmented generation platform for financial teams. It turns PDF, text, Markdown, and CSV source material into source-grounded portfolio summaries, risk insights, client communications, and research answers.

The production-shaped stack includes a responsive React workspace, an async FastAPI service, PostgreSQL with pgvector similarity search, provider-backed or deterministic local embeddings, persistent generations and citations, JWT authentication, and an append-only activity trail.

## Architecture

```text
Browser → nginx / React → FastAPI → PostgreSQL + pgvector
                              ↘ OpenAI embeddings and generation (optional)
```

Ingestion extracts text, retains page metadata, creates overlapping chunks, embeds each chunk, and indexes it with HNSW cosine search. Generation searches only documents owned by the authenticated user, constructs a constrained evidence prompt, saves the answer and citations, and records an audit event.

## Run locally with Docker

Requirements: Docker Engine with Compose v2.

```bash
cp .env.example .env
# Set a unique FINSIGHT_SECRET_KEY. Add FINSIGHT_OPENAI_API_KEY for synthesized answers.
docker compose up --build
```

Open [http://localhost:5173](http://localhost:5173). API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs) in development. Without an OpenAI key, FinSight uses deterministic local embeddings and returns retrieved passages, so the ingestion and retrieval loop remains usable offline.

## Develop without Docker

Start PostgreSQL 16 with the `vector` extension, then:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Configuration uses `FINSIGHT_`-prefixed variables. See [.env.example](.env.example). Never commit `.env` or credentials.

## API surface

| Endpoint | Purpose |
| --- | --- |
| `POST /api/auth/register` | Create an analyst account |
| `POST /api/auth/login` | Exchange credentials for access and refresh tokens |
| `POST /api/auth/refresh` | Rotate a refresh token |
| `GET /api/auth/me` | Read the active identity |
| `POST /api/documents` | Validate and index an uploaded source |
| `GET /api/documents` | List the current user's source library |
| `DELETE /api/documents/{id}` | Remove a document and its chunks |
| `POST /api/generate` | Retrieve evidence and produce a cited output |
| `GET /api/audit` | Review recent user activity |
| `GET /health` | Container and load-balancer health check |

## Security and audit model

- Passwords use memory-hard `scrypt` with unique random salts.
- Access tokens are short-lived and refresh tokens rotate on use.
- Every data query is scoped to the authenticated owner.
- Uploads use a media-type allowlist and configurable size limit.
- Prompts require source-only answers, inline citations, explicit uncertainty, and no return guarantees or personalized investment advice.
- Generations retain model, prompt version, excerpts, relevance, and source identifiers.
- Containers use minimal privileges and nginx/API security headers.

For an internet-facing AWS deployment, terminate TLS at an Application Load Balancer, place RDS in private subnets, keep secrets in Secrets Manager, restrict security groups, enable RDS encryption and backups, and stream container logs to CloudWatch. The images are suitable for ECR and ECS/Fargate.

## Verification

```bash
cd backend && pytest && ruff check .
cd frontend && npm run build
docker compose config --quiet
```

CI runs backend, frontend, and container checks on every push and pull request.

Financial disclaimer: FinSight helps users analyze supplied evidence. Outputs are not investment, legal, accounting, or tax advice and should be reviewed by a qualified professional.
