# Backend Architecture

## Goals

This repository now has an explicit backend foundation aimed at long-term maintenance:

- keep domain logic separate from scripts and vendor SDKs
- centralize configuration and logging
- use a local database by default, while keeping the storage layer portable to managed Postgres later
- support internal LLM-assisted draft scoring without leaking internal rationale to the public surface

## Proposed package layout

```text
ratio_backend/
  core/           # config and logging
  domain/         # pure business models
  db/             # SQLAlchemy models, sessions, repositories
  services/       # sizing, draft generation, publishing workflows
  integrations/   # external providers such as LLM SDKs
docs/             # product spec, sizing logic, architecture notes
data/             # local SQLite database file location
output/           # generated artifacts from ingestion and analysis scripts
```

## Layering rules

- `domain` must not import SQLAlchemy, SDK clients, or file-system workflows
- `services` orchestrate business logic and call repositories or integrations
- `db` owns persistence details and can switch from SQLite to Postgres through `DATABASE_URL`
- `integrations` isolate vendor-specific code so model/provider swaps do not ripple upward
- top-level ingestion scripts should eventually become thin entry points that call `ratio_backend`

## Logging

Logging is configured centrally in `ratio_backend.core.logging`.

- default format is structured JSON for machine parsing
- a plain-text mode is available with `LOG_FORMAT=text`
- request context support is included now so future APIs and job runners can stamp `request_id`
- modules should use `get_logger(__name__)` instead of `print`

## Database strategy

The initial default is local SQLite:

- default URL: `sqlite:///data/ratio.db`
- tables are created automatically during backend bootstrap
- SQLAlchemy repositories isolate persistence behavior from the service layer

This keeps local development simple while leaving an easy migration seam:

- swap `DATABASE_URL` to Postgres when moving to cloud
- keep repository interfaces stable
- add migrations later without restructuring the application layers

## Initial schema scope

The current schema follows the spec more closely and is still backend-first:

- `companies`
- `assessments`
- `source_documents`
- `assessment_factors`
- `assessment_evidence_links`
- `admin_users`
- `audit_events`
- `publish_events`

This supports the core internal workflow:

1. ingest source documents
2. generate an internal LLM first-pass draft with factor scores and rationale
3. review and edit scores, notes, and public comment
4. publish atomically while archiving the previous published version

## LLM draft workflow

The imported summarization code was not kept as a compatibility layer. Instead, the reusable provider integration pattern now feeds a draft-generation service that returns:

- four factor scores
- internal factor rationales
- assumptions
- calculated aggregate score and suggested position size

That matches the intended use case in `docs/spec.md` and `docs/sizing_logic.md`.

## Near-term next steps

1. Move the Outlook and forum ingestion scripts behind `ratio_backend.integrations` and `services`
2. Add migration tooling once the schema stabilizes
3. Add tests around sizing rules, draft parsing, repository behavior, and publication workflow
4. Add public/admin API layers only after the domain and persistence contracts settle
