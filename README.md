# resume-builder

To run:

```bash
bun run docker:dev
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
