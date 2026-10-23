# Resume Builder

Keep every role, project and bullet point in one library, then tailor a
LaTeX-typeset resume for each application without losing the original.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="apps/web/public/shots/dark/editor.webp">
  <img alt="The resume editor: the sections that make up a resume on the left, the compiled PDF alongside it" src="apps/web/public/shots/light/editor.webp">
</picture>

## What it is

Most resume tools make you keep a separate copy of your history for every
version of your resume, and the copies drift. This one inverts that: your
experience lives in one library, and a resume is a *selection and ordering* of
things already in it.

Add a role once. Use it in the frontend-focused resume and the backend-focused
one. Fix a typo in the library and both follow along, because neither of them
holds a copy — they hold a reference.

The output is not an HTML approximation of a resume. It is a real PDF, typeset
by pdfTeX from generated LaTeX, produced by a background worker. See
[the PDF pipeline](#how-the-pdf-gets-made).

## The product

### One library behind every resume

Education, experience, projects, skills and contact details live in a single
place, grouped by type.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="apps/web/public/shots/dark/sections.webp">
  <img alt="The sections page, listing education and experience entries in tables" src="apps/web/public/shots/light/sections.webp">
</picture>

### A version for every application

A resume picks sections out of that library and puts them in the order it
wants. Each one keeps its own selection, its own ordering and its own header,
so tailoring one leaves the others exactly as they were.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="apps/web/public/shots/dark/resumes.webp">
  <img alt="The resumes page, listing two resumes above a form for creating another" src="apps/web/public/shots/light/resumes.webp">
</picture>

### Bullets that carry emphasis

Bullet points support bold spans — select a phrase, press ⌘B — with a live
preview of how the line will typeset. Bullets drag to reorder, and so do whole
sections.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="apps/web/public/shots/dark/section-form.webp">
  <img alt="Editing an experience entry, showing bullet points and a bold-formatting preview" src="apps/web/public/shots/light/section-form.webp">
</picture>

### Careful with the destructive paths

Deleting a resume says which one, and what survives it — the sections it used
stay in the library.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="apps/web/public/shots/dark/confirm.webp">
  <img alt="A confirmation dialog asking whether to delete a resume" src="apps/web/public/shots/light/confirm.webp">
</picture>

### At a glance, and on a phone

<table>
<tr>
<td width="55%" valign="top">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="apps/web/public/shots/dark/dashboard.webp">
  <img alt="The dashboard, showing counts of resumes and sections" src="apps/web/public/shots/light/dashboard.webp">
</picture>
</td>
<td width="45%" valign="top">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="apps/web/public/shots/dark/editor-mobile.webp">
  <img alt="The editor at phone width, showing the compiled resume" src="apps/web/public/shots/light/editor-mobile.webp">
</picture>
</td>
</tr>
</table>

The whole app reflows to a single column on small screens, and follows your
system light/dark preference or an explicit toggle.

## Stack

| | |
| --- | --- |
| Web | React 19, React Router 8, TanStack Query + Form, Tailwind 4, Vite |
| API | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Data | Postgres 16 |
| Jobs | Postgres queue (LISTEN/NOTIFY, SKIP LOCKED), pdfTeX |
| Tooling | Bun, uv, Biome, Ruff, mypy, pytest |

The web app is a React Router SPA over a FastAPI service.

## Getting started

### Deploying with Docker

`docker-compose.yml` runs the whole application on a server, behind a reverse
proxy on the host:

```bash
cp .env.prod.example .env   # then fill it in
docker compose up --build -d
```

### Running it for development

From a fresh clone:

```bash
cp .env.example .env      # dev defaults work as-is
bun install
uv sync --directory apps/api
bun run docker:dev        # postgres + cloudbeaver; leave this running
bun run docker:latex      # the compile sandbox image, once
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

To change the sample data, edit `apps/api/scripts/seed.py` and re-run the seed.

### Looking at the database

CloudBeaver runs at http://localhost:8978 with the connection **Resume Builder
(dev)** already created (see `docker/cloudbeaver/initial-data-sources.conf`).
The username is filled in; enter `POSTGRES_PASSWORD` from your `.env` on first
connect and CloudBeaver remembers it.

## API client

The frontend's types are generated from the FastAPI OpenAPI spec by
[openapi-typescript](https://openapi-ts.dev/), and consumed through
`openapi-fetch` / `openapi-react-query`. The generated file is committed, so
regenerate it whenever a route or schema changes:

```bash
bun run codegen
```

It reads `http://localhost:8000/openapi.json`, so the API must be running.

The output is a single file, `apps/web/app/api/schema.d.ts`. The typed client built on
top lives in `apps/web/app/api/api.ts`.

## Checks

```bash
bun run test              # pytest + bun test
bun run verify            # format, lint and typecheck every app
```

```bash
TEST_DATABASE_URL=postgresql+psycopg://resume_user:resume_pass@localhost:5432/resume_db_test \
  uv run --directory apps/api pytest
```

## Landing page screenshots

The screenshots on the marketing page — and in this README — are captures of
the running app, regenerated by a script rather than taken by hand:

```bash
bun run apps/web/scripts/capture-shots.mjs
```

It needs the full stack running (including the worker, for the PDF preview) and
`cwebp` on `PATH`. See the header of
[`capture-shots.mjs`](apps/web/scripts/capture-shots.mjs) for the details.
