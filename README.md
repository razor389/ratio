# Ratio

Ratio is a split-runtime backend project for generating and publishing company assessment drafts.

- Python handles source collection and LLM-assisted draft analysis.
- Rust handles backend concerns such as database ownership, migrations, and API behavior.
- The sizing methodology is defined in [docs/sizing_logic.md](/mnt/c/Users/Ross/projects/ratio/docs/sizing_logic.md).

This repository is backend-first. There is no frontend app in this repo yet.

## Architecture

The current runtime boundary is:

- Python:
  - Outlook email collection
  - WebsiteToolbox forum collection
  - evidence normalization
  - provider-specific LLM calls
  - first-pass draft scoring, rationale, and sizing calculations
- Rust:
  - local SQLite bootstrap and schema ownership
  - backend API process
  - durable storage layer
  - future auth, versioning, publishing, and audit flows

More detail lives in:

- [docs/spec.md](/mnt/c/Users/Ross/projects/ratio/docs/spec.md)
- [docs/backend_architecture.md](/mnt/c/Users/Ross/projects/ratio/docs/backend_architecture.md)
- [docs/logging_contract.md](/mnt/c/Users/Ross/projects/ratio/docs/logging_contract.md)

## Repository Layout

```text
ratio_backend/
  core/         Python config and logging
  ingestion/    Outlook and forum collection
  integrations/ Provider-specific LLM clients
  domain/       Python-side draft and evidence types
  services/     Evidence pipeline, drafting, and sizing

apps/ratio-backend/
  Rust backend binary

crates/
  ratio-config/   Rust config and logging bootstrap
  ratio-domain/   Rust domain models
  ratio-storage/  Rust SQLite storage and migrations

docs/
  Product spec, sizing logic, logging contract, architecture notes
```

## Requirements

- Python 3.11+
- Rust stable toolchain
- Windows with Outlook installed for Outlook ingestion
- WebsiteToolbox API access for forum ingestion
- At least one LLM provider key for draft generation

## Configuration

Local configuration lives in [`.env`](/mnt/c/Users/Ross/projects/ratio/.env), which is gitignored.

Use [`.env.example`](/mnt/c/Users/Ross/projects/ratio/.env.example) as the reference for required values.

Important variables:

- `LLM_PROVIDER`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `SENDER_EMAIL`
- `EXCLUDED_EMAIL`
- `WEBSITETOOLBOX_API_KEY`
- `DATABASE_URL`
- `BASE_POSITION_SIZE`
- `BENCHMARK_TOTAL_SCORE`
- `BETA_FLOOR`

## Python Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Rust Setup

```bash
cargo check
```

To run the backend locally:

```bash
cargo run -p ratio-backend
```

The current Rust app exposes:

- `GET /healthz`

Default local bind:

- `http://127.0.0.1:3000/healthz`

## Ingestion Commands

Collect all forum posts for a ticker:

```bash
python -m ratio_backend.ingestion.forum_posts MSFT
```

Only posts authored by `FORUM_AUTHOR_EMAIL` are included.

This writes:

- `output/MSFT_forum_posts.json`

Collect sent Outlook emails for a ticker:

```bash
python -m ratio_backend.ingestion.outlook_ticker_search MSFT
```

This writes:

- `output/MSFT_sent_emails.json`

## Draft Generation

The Python orchestration layer now connects ingestion to the LLM draft service.

Primary service entrypoints:

- `ratio_backend.services.collect_evidence_for_ticker`
- `ratio_backend.services.generate_assessment_draft_for_ticker`

Command-line entrypoint:

```bash
python -m ratio_backend.services.pipeline MSFT
```

By default, a successful draft run also writes:

- `output/MSFT_llm_analysis.json`

Useful flags:

- `--collect-only`
- `--ignore-email`
- `--ignore-forum`
- `--lookback-years 5`
- `--company-name "Microsoft"`
- `--model <provider-specific-model>`

Examples:

```bash
python -m ratio_backend.services.pipeline MSFT --collect-only
python -m ratio_backend.services.pipeline MSFT --ignore-email
python -m ratio_backend.services.pipeline MSFT --ignore-forum
```

If both `--ignore-email` and `--ignore-forum` are supplied, the command prints a message and exits without running anything.
Use `--no-persist-artifacts` to skip writing the collected source files and LLM analysis artifact.

Example:

```python
from ratio_backend.services import generate_assessment_draft_for_ticker

draft = generate_assessment_draft_for_ticker(
    "MSFT",
    company_name="Microsoft",
    include_forum=True,
    include_outlook=True,
)

print(draft.aggregate_score)
print(draft.beta_like_score)
```

The draft service expects exactly four factors:

- `debt`
- `market_share_change`
- `market_definition_change`
- `relative_valuation`

Scores are fixed at `0..10`, and sizing is derived from the methodology in [docs/sizing_logic.md](/mnt/c/Users/Ross/projects/ratio/docs/sizing_logic.md).

## Logging

Python and Rust share a common structured logging vocabulary.

- Default format is JSON
- Set `LOG_FORMAT=text` for local plain-text logs
- Shared field names are documented in [docs/logging_contract.md](/mnt/c/Users/Ross/projects/ratio/docs/logging_contract.md)

## Current Status

Implemented now:

- Python ingestion modules for Outlook and forum collection
- Python evidence-to-draft pipeline
- LLM draft generation for factor scores, rationale, and sizing
- Rust SQLite bootstrap and health endpoint
- shared environment-driven config
- shared structured logging conventions

Not implemented yet:

- Rust ingestion of Python draft artifacts into durable assessment records
- admin/public API surface beyond healthcheck
- auth, publishing workflows, and audit UI flows

## Notes

- Outlook ingestion depends on `pywin32` and only works in a Windows environment with Outlook available.
- Forum ingestion uses the WebsiteToolbox API and requires `WEBSITETOOLBOX_API_KEY`.
- The Rust backend is the intended long-term system of record even when Python computes first-pass drafts.
