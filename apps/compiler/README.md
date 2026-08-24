# compiler

Turns LaTeX source into a PDF over HTTP. That is the whole job.

This service has no database, no sessions, and no idea what a resume is. It
accepts a `.tex`, runs a sandboxed TeX engine over it, and returns the bytes.
Everything that decides *what* to compile lives in the API.

## Why it is a separate service

The source it compiles arrives from a browser. The web app generates the
`.tex` client-side and posts it to the API, so an authenticated user could
send arbitrary LaTeX instead — and LaTeX is a programming language with file
and shell access.

Keeping the engine in its own container means a hostile document lands
somewhere with nothing worth reaching: no secrets, no database credentials, no
application code, an unprivileged user, and a read-only filesystem. Isolating
that blast radius is the reason this is a service rather than a function call
inside the API.

It also keeps a 3.3 GB TeX Live installation out of the API image.

## Why pdfTeX and not Tectonic

Tectonic would have made a far smaller image — a single ~30 MB static binary
that fetches packages on demand, instead of a full TeX Live install.

It cannot be used. The Jake's Resume template ends its preamble with:

```latex
\input{glyphtounicode}
\pdfgentounicode=1
```

That emits the glyph-to-Unicode map that makes the PDF's text extractable, and
`\pdfgentounicode` is a **pdfTeX primitive**. Tectonic is XeTeX-based and
rejects it outright — the build fails with `Undefined control sequence`.

Dropping those two lines would compile fine and produce a PDF that applicant
tracking systems cannot read, which for a resume defeats the point. So the
image carries real TeX Live and the size is the price.

The property is verifiable: extracting text from a compiled resume yields the
name, employers, skills and contact details as searchable strings.

## HTTP interface

### `GET /healthz`

Returns `200 ok`. No authentication — the container's own health check calls
it.

### `POST /compile`

| | |
| --- | --- |
| Auth | `Authorization: Bearer <COMPILER_TOKEN>` |
| Body | LaTeX source, raw (not JSON), UTF-8 |
| Success | `200` with `Content-Type: application/pdf` |

Status codes:

| Code | Meaning |
| --- | --- |
| `200` | PDF in the body |
| `400` | Body was empty or whitespace |
| `401` | Missing or wrong bearer token |
| `413` | Source exceeded the 1 MB cap |
| `422` | The document failed to typeset. Body is the tail of the TeX log |
| `503` | Every compile slot was busy |
| `500` | The service itself broke (could not create a work directory, etc.) |

`422` is the interesting one: it means the caller's LaTeX is at fault, not the
service, so the TeX log comes back as plain text to be surfaced to the user.

```bash
curl -X POST http://localhost:8100/compile \
  -H "Authorization: Bearer $COMPILER_TOKEN" \
  --data-binary @resume.tex \
  -o resume.pdf
```

## How the API talks to it

The browser never reaches this service. The chain is:

```
browser                 API (FastAPI)              compiler (this service)
   |                        |                              |
   |  POST /resume/{id}/pdf |                              |
   |  { source: "\\doc..." }|                              |
   |----------------------->|                              |
   |                        | authenticate session cookie  |
   |                        | check the resume is theirs   |
   |                        |                              |
   |                        |  POST /compile               |
   |                        |  Bearer COMPILER_TOKEN       |
   |                        |----------------------------->|
   |                        |                              | sandboxed pdflatex
   |                        |<-----------------------------|
   |                        |         application/pdf      |
   |<-----------------------|                              |
   |   application/pdf      |                              |
```

The API is the only door that checks *who you are*; this service only checks
*that you are the API*. Relevant code:

- [`apps/api/services/compiler.py`](../api/services/compiler.py) — the HTTP client
- [`apps/api/routers/resume.py`](../api/routers/resume.py) — the `POST /resume/{id}/pdf` endpoint

The API translates failures rather than passing them through:

| This service | API returns |
| --- | --- |
| `422` + TeX log | `422`, `detail` = last 2000 chars of the log |
| `503`, connection refused, timeout | `503`, `detail` = "PDF export is unavailable" |

The `503` message is deliberately generic — internal hostnames and connection
errors stay server-side.

**Without `COMPILER_TOKEN` set on the API, PDF export returns `503`.** The API
refuses to call an unauthenticated compiler rather than trying and failing.

## Sandboxing

Each control and what it stops:

| Control | Stops |
| --- | --- |
| `-no-shell-escape` | `\write18{...}` executing shell commands |
| `openin_any=p` | `\input{/etc/passwd}` reading files outside the work directory |
| `openout_any=p` | Writing anywhere but the work directory |
| Per-request temp directory, removed after | Requests seeing each other's files; disk growth |
| Minimal `cmd.Env` | A stray secret in the container's environment reaching a document that looks for it |
| Context timeout + process-group kill | A runaway `\loop` running forever |
| Bounded concurrency | Parallel engines exhausting CPU and memory |
| 1 MB request cap | An endless body exhausting memory |
| Non-root user, read-only rootfs, `cap_drop: ALL` | Anything that gets past the above |

Two of these have a subtlety worth knowing before you change them:

**Paranoid mode forbids absolute paths**, including the engine's own input
file. That is why `Compile` sets `cmd.Dir` to the work directory and passes
`main.tex` and `-output-directory=.` as relative paths. Passing an absolute
path fails with `Not reading from /tmp/... (openin_any = p)`.

**Killing the child is not enough.** `pdflatex` spawns helpers that inherit the
output pipe, so killing only the direct child leaves `Wait` blocking on a
grandchild and the timeout stops being a timeout. `superviseProcessGroup` puts
the child in its own process group and signals the group, with `WaitDelay` as a
backstop. There is a test that fails if this regresses.

These are verified against live hostile documents, not just asserted:
`\input{/etc/passwd}` → `422`; `\write18` → `422`; an infinite loop → killed at
the timeout.

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `COMPILER_TOKEN` | — | **Required.** The service exits at startup without it |
| `PORT` | `8100` | |
| `LATEX_BIN` | `pdflatex` | Must be a pdfTeX-family engine |
| `COMPILE_TIMEOUT_SECONDS` | `20` | Wall clock per compile |
| `COMPILE_CONCURRENCY` | `2` | Engines running at once |

The 1 MB request cap is not configurable; a generated resume is around 6 KB.

## Running it

### With compose (normal)

Already wired up in `docker-compose.dev.yml`. Set `COMPILER_TOKEN` in `.env`
(see `.env.example`), then:

```bash
bun run docker:dev
```

Note there is **no `ports:` mapping** for this service — it is reachable only
on the compose network. That is intentional. Do not publish it.

### Standalone, with the same hardening compose applies

```bash
docker build -t resume-compiler .
docker run --rm -p 8100:8100 \
  --read-only --tmpfs /tmp:size=256m,mode=1777 \
  --security-opt no-new-privileges:true --cap-drop ALL \
  --memory 1g --pids-limit 128 \
  -e COMPILER_TOKEN=local-dev-token \
  resume-compiler
```

### Locally, without Docker

Needs a `pdflatex` on `PATH` with `fontawesome5`, `titlesec`, `enumitem` and
`marvosym` available (a full MacTeX or TeX Live install has these):

```bash
COMPILER_TOKEN=local-dev-token go run .
```

## Development

```bash
go test ./...
```

The tests need no TeX installation. `stubEngine` writes a small shell script
that stands in for `pdflatex` and can be told to emit a PDF, fail with a log,
hang, or dump its arguments and environment — which is how the sandbox flags
and the timeout behaviour are asserted without a 3 GB dependency.

From the repo root, `bun run test:compiler` runs the same suite, and
`bun run verify` includes `go fmt` and `go vet`.

## Files

| File | |
| --- | --- |
| `main.go` | Configuration, startup, and the `-healthcheck` self-probe |
| `router.go` | Routes, bearer-token auth, request limits, status mapping |
| `compiler.go` | The sandboxed engine invocation |
| `process_unix.go` | Process-group supervision so timeouts actually kill |
| `process_other.go` | No-op fallback, so the package builds off Unix |
| `warmup.tex` | Compiled during the image build to prove the template's packages are present |

`warmup.tex` earns its place: it pulls in every package the resume template
uses, so a missing one fails the image build instead of the first user request.
Keep its package list in step with the preamble in
[`apps/web/app/lib/latex/preamble.ts`](../web/app/lib/latex/preamble.ts).

## Operational notes

- **Image size is ~3.3 GB**, nearly all TeX Live. The Dockerfile already
  excludes TeX's documentation and translations; the remaining bulk is
  `texlive-fonts-extra`, which is where `fontawesome5` lives.
- **A compile takes ~250 ms** for a one-page resume, including process
  startup.
- **Output is deterministic.** `SOURCE_DATE_EPOCH=0` and `FORCE_SOURCE_DATE=1`
  pin the timestamp TeX embeds, so identical source produces an identical PDF.
  Nothing caches on that yet, but it means hashing the source would work as a
  cache key.
- **The service is stateless.** Scale it horizontally; there is nothing to
  coordinate.
- One pass only. Documents needing a second run for references or a table of
  contents would come out incomplete — resumes do not.
