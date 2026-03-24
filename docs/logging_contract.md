# Logging Contract

## Purpose

This project uses two runtimes:

- Python for ingestion and LLM analysis
- Rust for database interaction and API behavior

Those runtimes should emit logs that are easy to correlate during local development and production operations.

## Default format

- emit structured JSON logs by default
- allow plain-text logs for local debugging with `LOG_FORMAT=text`
- write logs to stdout/stderr so process managers and containers can collect them uniformly

## Shared semantic fields

These fields should exist either directly on each event or in stable enclosing span/context metadata:

- `timestamp`
- `level`
- `message`
- `service`
- `runtime`
- `environment`
- `component`
- `request_id`
- `run_id`
- `ticker`
- `company_id`
- `llm_provider`
- `llm_model`
- `prompt_version`

Not every event needs every field, but the names should stay consistent.

## Runtime conventions

### Python analysis jobs

- `runtime=python`
- `component=analysis`
- use `run_id` for one ingestion or analysis job
- attach `ticker` when processing a single company
- attach `llm_provider`, `llm_model`, and `prompt_version` around model calls

### Rust backend

- `runtime=rust`
- `component=api` or `component=storage` depending on the emitting scope
- use `request_id` for API requests
- include `company_id` or `ticker` on company-specific operations
- include publication/audit identifiers on publish flows when available

## Practical guidance

- Python should use `python-json-logger` with a shared field vocabulary
- Rust should use `tracing` and `tracing-subscriber` with JSON output and a root span carrying static runtime metadata
- avoid free-form prefixes in messages when a field can carry the same information
- log one event per meaningful state transition rather than printing verbose step-by-step chatter
