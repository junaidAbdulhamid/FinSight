# FinSight

FinSight is a secure, auditable retrieval-augmented generation platform for financial teams. It turns PDF, text, Markdown, and CSV source material into source-grounded portfolio summaries, risk insights, client communications, and research answers.

The production-shaped stack includes a responsive React workspace, an async FastAPI service, PostgreSQL with pgvector similarity search, provider-backed or deterministic local embeddings, Supabase Auth, persistent generations and citations, and an append-only activity trail.

## Architecture

```text
Browser → Supabase Auth
       → nginx / React → FastAPI → PostgreSQL + pgvector
                              ↘ OpenAI embeddings and generation (optional)
```

Ingestion extracts text, retains page metadata, creates overlapping chunks, embeds each chunk, and indexes it with HNSW cosine search. Generation searches only documents owned by the authenticated user, constructs a constrained evidence prompt, saves the answer and citations, and records an audit event.

## Run locally with Docker

Requirements: Docker Engine with Compose v2.

### Configure Supabase Auth

1. Create a Supabase project and open **Authentication → URL Configuration**. Set the Site URL to `http://localhost:5173` for local development and add the same address to Redirect URLs. Add each deployed HTTPS origin before production rollout.
2. Under **Authentication → Providers → Email**, enable email/password authentication. Keep **Confirm email** enabled for production; users will see a dedicated confirmation state after registration.
3. Under **Project Settings → API Keys**, create or copy a `sb_publishable_...` key. FinSight intentionally uses the publishable browser key; never provide a secret or `service_role` key.
4. Under **Authentication → Signing Keys**, migrate to and rotate onto an asymmetric RS256 or ES256 signing key. Allow at least 20 minutes for JWKS caches to observe a standby key before rotation.
5. Copy the example configuration and supply the project URL and the same publishable key to both the browser and API variables:

```bash
cp .env.example .env
# Edit VITE_SUPABASE_URL, VITE_SUPABASE_PUBLISHABLE_KEY,
# FINSIGHT_SUPABASE_URL, and FINSIGHT_SUPABASE_PUBLISHABLE_KEY.
# Add FINSIGHT_OPENAI_API_KEY for synthesized answers.
docker compose up --build
```

See Supabase's official [password authentication](https://supabase.com/docs/guides/auth/passwords), [redirect URL](https://supabase.com/docs/guides/auth/redirect-urls), and [JWT signing key](https://supabase.com/docs/guides/auth/signing-keys) guidance when configuring non-local environments.

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

Configuration uses `FINSIGHT_`-prefixed server variables and `VITE_` browser build variables. See [.env.example](.env.example). A publishable key is expected in browser assets and has limited privileges; never place a Supabase secret/service-role key in any FinSight variable. Never commit `.env`.

## API surface

| Endpoint | Purpose |
| --- | --- |
| `GET /api/auth/me` | Read the active identity |
| `POST /api/documents` | Validate and index an uploaded source |
| `GET /api/documents` | List the current user's source library |
| `DELETE /api/documents/{id}` | Remove a document and its chunks |
| `POST /api/generate` | Retrieve evidence and produce a cited output |
| `GET /api/audit` | Review recent user activity |
| `GET /health` | Container and load-balancer health check |

## Security and audit model

- Supabase Auth owns password storage, email confirmation, persisted browser sessions, and refresh-token rotation.
- The API validates asymmetric Supabase access tokens locally using the project's rotating JWKS and strict issuer, `authenticated` audience/role, expiry, and subject checks.
- Legacy HS256 access tokens are never verified with a shared JWT secret; they are checked against Supabase Auth's `/user` endpoint using only the publishable key.
- The local `users` table is a profile/ownership record keyed by the Supabase `sub`; it never stores new password hashes.
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
