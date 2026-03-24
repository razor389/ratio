# Backend Architecture

## Goals

This repository should use an explicit split-runtime foundation aimed at long-term maintenance:

- keep domain logic separate from scripts and vendor SDKs
- keep Python focused on ingestion and provider-specific LLM analysis
- keep Rust focused on the system-of-record backend concerns
- centralize configuration and logging conventions across both runtimes
- use a local database by default, while keeping the storage layer portable to managed Postgres later

## Proposed package layout

```text
ratio_backend/
  core/           # Python analysis config and logging
  services/       # Python ingestion and LLM draft-generation workflows
  integrations/   # Python provider-specific LLM clients
  domain/         # shared Python-side draft/data shapes

apps/
  ratio-backend/  # Rust API/backend binary entrypoint
crates/
  ratio-config/   # Rust config and logging bootstrap
  ratio-domain/   # Rust domain models
  ratio-storage/  # Rust local DB layer and migrations

docs/             # product spec, sizing logic, architecture notes
data/             # local SQLite database file location
output/           # generated artifacts from ingestion and analysis scripts
```

The current Python package name `ratio_backend` is legacy. In practice it should be treated as the Python analysis layer until it is renamed more explicitly.

## Layering rules

- Python analysis modules should not become the primary database or API layer
- Rust backend crates should not absorb provider-specific LLM orchestration unless there is a strong operational reason
- the Python/Rust boundary should use structured draft artifacts and source-document payloads
- Rust remains the owner of persistent state transitions, publication rules, and API contracts
- top-level ingestion scripts should eventually become thin entry points into the Python analysis layer

## Logging

Logging should be coordinated, not duplicated.

- Python should use `python-json-logger`
- Rust should use `tracing` plus `tracing-subscriber`
- both should follow the field vocabulary in [logging_contract.md](/mnt/c/Users/Ross/projects/ratio/docs/logging_contract.md)
- JSON should be the default format in both runtimes

## Database strategy

The initial default is local SQLite owned by Rust:

- default URL: `sqlite://data/ratio.db`
- Rust owns database access and schema evolution
- Python should not be treated as a peer database backend

This keeps local development simple while leaving an easy migration seam:

- swap the Rust storage layer to Postgres when cloud requirements justify it
- keep Rust domain and service interfaces stable
- keep Python focused on artifact generation regardless of the eventual database choice

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

1. Python collects source material and generates first-pass draft analysis
2. Rust ingests those artifacts and persists source documents and assessments
3. PM reviews and edits scores, notes, and public comment
4. Rust publishes atomically while archiving the previous published version

## LLM draft workflow

The Python LLM layer should return structured draft artifacts rather than prose summaries. Those artifacts should contain:

- four factor scores
- internal factor rationales
- assumptions
- provider/model/prompt metadata
- optional calculated aggregate score and suggested position size

That matches the intended use case in [spec.md](/mnt/c/Users/Ross/projects/ratio/docs/spec.md) and [sizing_logic.md](/mnt/c/Users/Ross/projects/ratio/docs/sizing_logic.md).

## Near-term next steps

1. Keep Outlook/forum extraction and LLM calls in Python, but narrow them to artifact generation
2. Remove Python database ownership assumptions from the codebase
3. Add a concrete artifact handoff contract from Python to Rust
4. Add Rust API/persistence tests around validation, versioning, and publish transactions
