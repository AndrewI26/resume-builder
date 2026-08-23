# resume-builder

## Getting started

From a fresh clone:

```bash
cp .env.example .env      # dev defaults work as-is
bun install
uv sync --directory apps/api
bun run docker:dev        # postgres + cloudbeaver; leave this running
bun run db:upgrade        # apply migrations
bun run db:seed           # sample data + demo account
```

Then, in two more terminals:

```bash
bun run dev:api           # http://localhost:8000
bun run dev:web           # http://localhost:5173
```

Sign in at http://localhost:5173 as **demo@example.com** / **demo1234**.

### Sample data

`bun run db:seed` fills the database with one demo user and a realistic spread
of sections (personal info, educations, experiences with bolded bullet points,
projects, skills) plus two resumes built from them.

Every seeded row has a deterministic id, so re-running the seed deletes exactly
the rows it owns and reinserts them — anything you created by hand is left
alone. It is safe to re-run whenever you want a clean baseline, and it refuses
to run unless `NODE_ENV=development`. The demo account's password is committed
in the seed script; it is a development fixture and must never exist in a
deployed environment.

To change the sample data, edit `apps/api/scripts/seed.py` and re-run the seed.

### Looking at the database

CloudBeaver runs at http://localhost:8978 with the connection **Resume Builder
(dev)** already created (see `docker/cloudbeaver/initial-data-sources.conf`).
The username is filled in; enter `POSTGRES_PASSWORD` from your `.env` on first
connect and CloudBeaver remembers it.

The connection is created from the committed config only when the CloudBeaver
workspace volume is empty, so it appears on a fresh clone and never overwrites
connections you have saved. To get it back after changing that file:

```bash
docker compose -f docker-compose.dev.yml rm -sf cloudbeaver
docker volume rm resume-builder_cloudbeaver_workspace
bun run docker:dev
```

For a shell instead:

```bash
docker compose -f docker-compose.dev.yml exec postgres psql -U resume_user -d resume_db
```

## API client

The frontend's API layer is generated from the FastAPI OpenAPI spec by Orval.
The generated code is committed, so regenerate it whenever an API route or
schema changes:

```bash
bun run codegen
```

It reads `http://localhost:8000/openapi.json`, so the API must be running.
Override the source with `VITE_API_URL`.

Generated files live in `apps/web/app/api/generated` and are excluded from
linting and typechecking: Biome skips the directory via `files.includes`, and
codegen prepends `// @ts-nocheck` to every file. Code that imports them is still
fully typechecked against the generated types.
