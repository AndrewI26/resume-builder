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

## How the PDF gets made

Typesetting is slow and bursty — a run is CPU-bound for a second or two — so it
does not belong on the request path. The API writes a job into **Postgres** and
a pool of **workers** claims it. There is no separate queue server: the table
is the queue, `LISTEN`/`NOTIFY` is the doorbell, and `FOR UPDATE SKIP LOCKED`
is what hands each job to exactly one worker.

```mermaid
sequenceDiagram
    participant C as Browser
    participant A as FastAPI
    participant P as Postgres
    participant W as Worker
    participant T as pdfTeX

    C->>A: POST /resumes/:id/pdf
    A->>A: verify the resume belongs to the caller
    A->>P: INSERT pdf_jobs + NOTIFY pdf_jobs
    P->>W: notification wakes an idle worker
    W->>P: claim with FOR UPDATE SKIP LOCKED
    W->>P: load resume, sections, bullet points
    W->>W: build document, serialize to LaTeX
    W->>T: pdflatex in a sandbox, 20s cap
    T-->>W: PDF bytes
    W->>P: UPDATE pdf_jobs + NOTIFY pdf_jobs_done
    P-->>A: notification, awaited up to 45s
    A-->>C: 200 application/pdf
```

**The job carries a resume id and nothing else.** It re-reads the rows itself
rather than trusting a document sent in from outside, so there is no
caller-supplied LaTeX anywhere in the pipeline. Ownership is settled by the
endpoint before the job is ever queued.

**The queue bounds work rather than hiding it.** The request waits for its own
result, because the client asked for a file and gets one in the same response.
What the queue buys is a ceiling on how many compiles run at once: a compile is
CPU-bound, so running more of them makes each one slower rather than finishing
sooner, and unbounded exports would take the host down instead of merely
queueing. Jobs run with `max_tries = 1` — the document is identical on a retry,
so a retry cannot fix what failed.

**How many workers is set when the API starts.** `PDF_WORKER_COUNT` defaults to
3, and the API's lifespan starts that many:

```bash
PDF_WORKER_COUNT=6 bun run dev:api
```

Zero is a real answer, and it is what `docker-compose.yml` gives the API: there
a separate `worker` container claims the jobs instead. Either way the API keeps
one `LISTEN` connection open, because a request waiting here has to hear that
its job finished wherever it ran.

**The engine runs in a container.** A TeX document is a program, and the engine
that runs it is the least trustworthy thing in the application. Which sandbox
it gets depends on where the worker is:

| `LATEX_BACKEND` | Used by | The fence |
| --- | --- | --- |
| `docker` (default) | the API on the host | a container per compile: `--network=none`, read-only root, `--cap-drop=ALL`, `--memory=512m`, `--pids-limit=128`, nothing mounted. The document goes in on stdin and the PDF comes back on stdout |
| `local` | the `worker` container | the engine as a child process — that container is already the boundary, and starting containers from inside one would mean giving it a Docker socket, a far larger privilege than the one being contained |

Both are fenced the same way from the engine's side:

| Fence | Why |
| --- | --- |
| `openin_any=p`, `openout_any=p` | paranoid mode — `\input{/etc/passwd}` cannot reach the PDF |
| `-no-shell-escape` | no `\write18`, whatever the document says |
| a minimal environment | the engine inherits nothing the worker was started with, so a stray secret cannot leak into a document |
| `-halt-on-error` | fail on the first error instead of cascading |
| 20s timeout | a hung run is killed, container and all |
| `SOURCE_DATE_EPOCH=0` | identical input produces an identical file |

Build the compile image once before exporting on the host:

```bash
bun run docker:latex
```

**The engine has to be pdfTeX.** The template calls `\pdfgentounicode`, a pdfTeX
primitive that emits the glyph-to-Unicode map making the PDF readable by
applicant tracking systems — which for a resume is close to the whole point.
XeTeX-based engines such as Tectonic reject it.

Failures come back as themselves rather than a generic 500: a document the
engine rejected returns `422` with the tail of the TeX log, a missing engine
returns `503`, a compile that outlives the wait returns `504`, and a resume
deleted between queueing and running returns `404`. The worker cannot throw
across a table, so it records which failure it hit and the endpoint raises it
again on the other side.

Finished rows are deleted a minute after they are read, and a job whose worker
died is failed rather than left running, both by a reaper that runs alongside
the workers.

Relevant code:

| | |
| --- | --- |
| [`routers/resume.py`](apps/api/routers/resume.py) | the endpoint that queues and waits |
| [`services/pdf_queue.py`](apps/api/services/pdf_queue.py) | the queue: enqueue, claim, result, reap |
| [`services/pdf_worker.py`](apps/api/services/pdf_worker.py) | the worker loop and the pool |
| [`deps/notify.py`](apps/api/deps/notify.py) | the one LISTEN connection everything waits on |
| [`services/compiler.py`](apps/api/services/compiler.py) | the sandboxed pdfTeX run, both backends |
| [`services/latex/`](apps/api/services/latex) | document → LaTeX source |
| [`docker/latex/`](docker/latex) | the compile sandbox image |
| [`worker.py`](apps/api/worker.py) | standalone worker, for the compose deployment |

## Stack

| | |
| --- | --- |
| Web | React 19, React Router 8, TanStack Query + Form, Tailwind 4, Vite |
| API | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Data | Postgres 16 hosted, SQLite on the desktop |
| Jobs | Postgres queue (LISTEN/NOTIFY, SKIP LOCKED), pdfTeX |
| Tooling | Bun workspaces, uv, Biome, Ruff, mypy, pytest |

The application is one React app and one API, each deployed two ways. The app
is `packages/ui`, and `apps/` holds only what differs between deployments — so
a change to a screen reaches the browser and the desktop at once, rather than
being made twice and drifting.

```
packages/
  ui/           the React Router app, shared by both deployments
    app/routes/     pages
    app/components/ shared UI
    app/lib/        LaTeX serialization, resume documents
    app/api/        generated OpenAPI types + client
apps/
  api/          FastAPI service, worker, migrations
    routers/    HTTP endpoints
    services/   compile pipeline, LaTeX serialization, sections
    models/     SQLAlchemy tables
    schemas/    Pydantic request/response types
  web/          the browser deployment: Dockerfile, nginx, screenshots
```

The API is the same in both too. `MODE=cloud` is the hosted service — Postgres,
a queue, accounts, and compiles fenced in a container. `MODE=local` is the copy
the desktop app embeds: one SQLite file, nobody signed in, no queue, and
typesetting done in this process with the TeX the app ships. The routers,
services and schemas are the same code either way.

## Getting started

### Everything in one command

```bash
docker compose up --build
```

That builds and starts the whole application — Postgres, the API, the PDF
worker and the web app — and applies the migrations on the way up. The app
is at http://localhost:5173 and the API at http://localhost:8000; create an
account from the sign-in page.

No `.env` is needed: `docker-compose.yml` defaults every setting. Drop one at
the repo root (see `.env.example`) to change ports or the database credentials,
or to fill in `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` for Google sign-in.
The database lives in a named volume and survives `docker compose down`;
`down -v` is what throws it away. The job queue is a table in that same
database, so there is no second service to run.

The image the API and worker share carries a TinyTeX install with just the
packages the resume template loads, so `pdflatex` is there without a TeX Live
install on your machine. `PDF_WORKER_COUNT` sets how many compiles the worker
container runs at once (default 3).

> This runs the app, not a development loop: the web bundle is built into the
> image and the API runs without `--reload`, so code changes need a rebuild.
> For day-to-day work use the setup below, which runs only the backing services
> in Docker.

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

> There is no separate worker to start: the API runs its own, three by default.
> `PDF_WORKER_COUNT=6 bun run dev:api` runs six instead, and `0` runs none —
> useful if you want a standalone `uv run python worker.py` to do the work.
>
> Each compile runs in the `resume-builder-latex` container, so `bun run
> docker:latex` has to have been run at least once; the endpoint returns `503`
> when the image or Docker itself is missing. Set `LATEX_BACKEND=local` to use
> a `pdflatex` on your `PATH` instead.

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

The frontend's types are generated from the FastAPI OpenAPI spec by
[openapi-typescript](https://openapi-ts.dev/), and consumed through
`openapi-fetch` / `openapi-react-query`. The generated file is committed, so
regenerate it whenever a route or schema changes:

```bash
bun run codegen
```

It reads `http://localhost:8000/openapi.json`, so the API must be running.

The output is a single file, `packages/ui/app/api/schema.d.ts` — never edit it
by hand, since the next codegen run overwrites it. The typed client built on
top lives in `packages/ui/app/api/api.ts`.

## Checks

```bash
bun run test              # pytest + bun test
bun run verify            # format, lint and typecheck both apps
```

The API tests run against a throwaway SQLite file and need nothing started.
Set `TEST_DATABASE_URL` to run the same suite against a Postgres — the hosted
app's database — which is worth doing before changing a model.

The job queue's tests only run on that second pass. `FOR UPDATE SKIP LOCKED`
and `LISTEN/NOTIFY` are the whole mechanism and SQLite has no stand-in for
them, so they skip rather than pretend:

```bash
TEST_DATABASE_URL=postgresql+psycopg://resume_user:resume_pass@localhost:5432/resume_db_test \
  uv run --directory apps/api pytest
```

## The desktop app

The same app, in a window, with everything on your own machine. No account, no
network: it starts the API as a child process against a SQLite file in your
application data directory, and carries its own TeX distribution so a resume
typesets to a real PDF on a computer that has never had LaTeX installed.

```bash
bun run dev:desktop     # builds the app and opens it
```

In a checkout the API runs from source through `uv`, so an edit to a router
shows up without repackaging anything.

### Building installers

```bash
bun run package:desktop
```

Three things go in, and two of them cannot be cross-built — PyInstaller
produces a binary for the machine it runs on, and the TeX distribution is
per-platform. **So an installer can only be built on the kind of machine it is
for.** Building an x64 installer on an Apple Silicon Mac produces a `.dmg` that
fails on the first launch of the machine it was meant for.

| | |
| --- | --- |
| [`resume-api.spec`](apps/api/resume-api.spec) | the API as a single binary |
| [`bundle-texlive.sh`](apps/desktop/scripts/bundle-texlive.sh) | TinyTeX plus the packages the template needs |
| [`electron-builder.yml`](apps/desktop/electron-builder.yml) | the shell, and what gets shipped beside it |

The TeX bundle is most of the download — around 235MB installed.

### Releases

Pushing a tag builds macOS and Windows installers on their own runners and
attaches them to a draft release:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

The workflow can also be run by hand from the Actions tab, which builds the
installers and leaves them as artifacts without publishing anything. See
[`release-desktop.yml`](.github/workflows/release-desktop.yml).

The macOS app is ad-hoc signed and nothing is notarised, so both systems warn
on first launch. Proper signing needs a certificate in the repository's secrets
and a change to that workflow.

Ad-hoc rather than unsigned for a specific reason: skipping signing leaves the
bundle carrying the signature Electron's own binary shipped with, which stops
describing it once the sidecar and TeX are inside. macOS reports that invalid
signature as *"this app is damaged"*, and on Apple Silicon the usual
right-click-and-Open workaround will not get past it.

## Landing page screenshots

The screenshots on the marketing page — and in this README — are captures of
the running app, regenerated by a script rather than taken by hand:

```bash
bun run apps/web/scripts/capture-shots.mjs
```

It needs the full stack running (including the worker, for the PDF preview) and
`cwebp` on `PATH`. See the header of
[`capture-shots.mjs`](apps/web/scripts/capture-shots.mjs) for the details.
