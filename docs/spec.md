## Ratio (Spec.md v1)

### 1. Product summary

Build a **public, read-only web dashboard** for clients that displays a curated set of portfolio companies, with for each company:

* final factor scores
* final sizing output
* an optional admin-enabled comment containing the final human-approved rationale

Scott will manage the underlying data through an **authenticated admin UI**. His workflow will update a cloud-hosted database using existing extraction pipelines, LLM-assisted drafting, and manual review. Clients will not see raw source material, draft outputs, or internal citations.

---

## 2. Final product rules

These are now fixed requirements:

* **Clients see no raw emails or forum posts**
* **Clients see only final published values**
* **Clients may see an optional comment/rationale only if Scott enables it**
* **Only final human-approved reasoning appears externally**
* **All clients see the same company set**
* **No authentication is required for client viewing**
* **Records are updated ad hoc**
* **Scott needs an admin UI**
* **Admin interaction with the database must be authorized**
* **There is only one current published assessment per company**
* **Historical versions must be retained for Scott/admin use**

This substantially simplifies the client-facing app and makes the main complexity live in the admin and publishing workflow.

---

## 3. Product goals

### Client-facing goals

Provide a clean, low-friction dashboard that lets any visitor:

* browse the current published company set
* understand the current factor scores
* see the current sizing output
* optionally read a concise final comment when enabled

### Admin goals

Provide Scott with a secure admin experience that lets him:

* manage which companies appear publicly
* review internal source material and internal citations
* run or import first-pass analyses
* edit factor values manually
* approve final comments
* publish the current assessment
* track historical versions over time

---

## 4. User types

### 4.1 Public client viewer

Unauthenticated, read-only.

Can:

* view dashboard
* view company detail pages
* see published factor scores and sizing
* see optional published comment if enabled

Cannot:

* view raw sources
* view internal notes
* view drafts
* edit anything
* trigger analysis

### 4.2 Scott/admin

Authenticated.

Can:

* sign into admin UI
* manage company visibility
* inspect internal source evidence
* view email/forum support material
* view internal citations and LLM draft outputs
* edit factors and final comments
* publish/unpublish companies
* review version history

---

## 5. Core product structure

The system should have **two distinct applications or two clearly separated app surfaces**:

### A. Public app

Read-only, no login required.

Purpose:

* present current published assessments only

### B. Admin app

Authenticated.

Purpose:

* manage ingestion results
* review evidence
* create and edit assessments
* publish final approved records

Even if both are served from the same backend, they should be logically and permission-wise separate.

---

## 6. Public-facing functionality

## 6.1 Public dashboard

The main page should show the currently published company set.

For each company:

* company name
* ticker
* factor scores
* total/aggregate score if used
* current sizing output
* last updated or “as of” date
* optional visible comment indicator

Features:

* search by company name or ticker
* sort by ticker, score, sizing, update date
* simple filtering if useful later

Because there is no login and all users see the same content, this page can be heavily cacheable.

## 6.2 Company detail page

Each company page should show:

* company name and ticker
* final published factor scores
* sizing output
* optional final published comment
* last published date
* methodology/version label

It should **not** show:

* raw evidence
* citations
* internal rationale chain
* LLM involvement
* draft history

## 6.3 Methodology page

A public page should explain:

* the factor framework at a high level
* how scores relate to sizing
* that assessments are human-reviewed and published
* that updates occur on an ad hoc basis

It should avoid exposing internal workflow details that are irrelevant to clients.

---

## 7. Admin functionality

## 7.1 Admin dashboard

Main internal landing page for Scott.

Should show:

* all tracked companies
* publication status
* current draft vs published state
* last updated timestamp
* whether optional comment is enabled
* quick access to edit/publish/history

## 7.2 Company assessment editor

For a selected company, Scott should be able to:

* view current published assessment
* view current draft assessment
* edit factor values
* edit sizing-related fields if needed or let them auto-calculate
* edit final public comment
* toggle whether the comment is shown publicly
* save draft
* publish current version

## 7.3 Internal evidence view

Admin-only page/panel showing supporting source material:

* Outlook-derived items
* forum-derived items
* internal citations/evidence links
* timestamps
* source type
* any LLM first-pass output

This is only for Scott/admin use.

## 7.4 Version history

Scott should be able to:

* see all historical versions for a company
* compare versions
* inspect who changed what and when
* restore an earlier version into a new draft if needed

Important: there is only one live published assessment per company, but many historical saved versions.

## 7.5 Company visibility management

Scott should be able to:

* add/remove companies from the public dashboard
* mark companies as draft-only, published, or hidden
* reorder display if needed

Because all clients see the same set, this is much simpler than per-client entitlements.

---

## 8. Updated source-data policy

### Public-facing

Never shown:

* raw emails
* raw forum posts
* internal citations
* LLM output
* source snippets

### Admin-facing only

Visible to Scott:

* extracted forum posts
* extracted emails
* internal evidence associations
* LLM first-pass scores and rationale
* internal notes

### Published content

Only these fields may appear publicly:

* company identity
* final factor scores
* final sizing output
* optional final comment approved by Scott
* published timestamp / as-of date

This keeps the public app very clean and sharply reduces privacy risk.

---

## 9. Assessment lifecycle

For each company, the lifecycle should be:

1. **Ingest**

   * internal scripts pull forum posts and email records
2. **Draft**

   * system creates or updates a draft assessment
3. **Review**

   * Scott reviews source evidence and draft values
4. **Edit**

   * Scott manually adjusts scores/comment
5. **Publish**

   * draft becomes the one current published assessment
6. **Archive**

   * prior published version remains in version history

At any moment:

* one company can have multiple drafts/history records
* one company can have only one current published assessment

---

## 10. Data model

## 10.1 companies

Fields:

* `id`
* `ticker`
* `company_name`
* `display_name`
* `sector`
* `industry`
* `description`
* `is_tracked`
* `is_published`
* `display_order`
* `created_at`
* `updated_at`

## 10.2 source_documents

Admin/internal only.

Fields:

* `id`
* `company_id`
* `source_type` (`outlook_email`, `forum_post`)
* `external_source_id` nullable
* `title` nullable
* `body_text`
* `author_email`
* `source_timestamp`
* `ingested_at`
* `source_metadata_json`
* `content_hash`

## 10.3 assessments

Represents versioned assessments, both draft and published.

Fields:

* `id`
* `company_id`
* `version_number`
* `status` (`draft`, `published`, `archived`)
* `created_at`
* `updated_at`
* `published_at` nullable
* `created_by`
* `updated_by`
* `published_by` nullable
* `as_of_date`
* `public_comment` nullable
* `is_public_comment_enabled`
* `internal_notes` nullable
* `llm_provider` nullable
* `llm_model` nullable
* `llm_prompt_version` nullable
* `calculation_version`
* `aggregate_score`
* `relative_score`
* `beta_like_score`
* `suggested_position_size`

Only one row per company may have `status = published` at a time.

## 10.4 assessment_factors

Fields:

* `id`
* `assessment_id`
* `factor_key`
* `factor_label`
* `score`
* `score_min`
* `score_max`
* `internal_rationale` nullable
* `public_rationale_override` nullable
* `sort_order`

For public display, you may not need factor-level rationale at all unless you later decide to expose it. Since the requirement is for a single optional comment, most rationale can remain internal.

## 10.5 assessment_evidence_links

Admin/internal only.

Fields:

* `id`
* `assessment_id`
* `factor_key` nullable
* `source_document_id`
* `relevance_rank`
* `evidence_note` nullable
* `used_by_llm`
* `used_in_final_review`

## 10.6 admin_users

Fields:

* `id`
* `email`
* `name`
* `role`
* `password_hash` or auth provider subject
* `status`
* `created_at`
* `last_login_at`

## 10.7 audit_events

Fields:

* `id`
* `actor_user_id`
* `event_type`
* `entity_type`
* `entity_id`
* `before_json`
* `after_json`
* `created_at`

## 10.8 publish_events

Optional but useful.

Fields:

* `id`
* `company_id`
* `assessment_id`
* `published_by`
* `published_at`
* `notes` nullable

---

## 11. Public API spec

The public API should be read-only and expose only published content.

### Endpoints

#### `GET /api/public/companies`

Returns all published companies.

For each company:

* ticker
* company name
* factor scores
* aggregate score if displayed
* sizing output
* public comment if enabled
* published timestamp

#### `GET /api/public/companies/:ticker`

Returns detail for one published company.

#### `GET /api/public/methodology`

Returns public methodology text/config.

Because there is no auth, these endpoints must never return draft or internal fields.

---

## 12. Admin API spec

The admin API must require authorization.

### Auth endpoints

* `POST /api/admin/auth/login`
* `POST /api/admin/auth/logout`
* `GET /api/admin/auth/me`

### Company/admin endpoints

* `GET /api/admin/companies`
* `GET /api/admin/companies/:ticker`
* `PATCH /api/admin/companies/:ticker`
* `POST /api/admin/companies`
* `POST /api/admin/companies/:ticker/publish`
* `GET /api/admin/companies/:ticker/history`

### Assessment endpoints

* `GET /api/admin/assessments/:id`
* `POST /api/admin/companies/:ticker/drafts`
* `PATCH /api/admin/assessments/:id`
* `POST /api/admin/assessments/:id/recalculate`

### Evidence endpoints

* `GET /api/admin/companies/:ticker/evidence`
* `GET /api/admin/companies/:ticker/evidence/emails`
* `GET /api/admin/companies/:ticker/evidence/forum-posts`

### Internal workflow endpoints later

* `POST /api/admin/companies/:ticker/run-ingestion`
* `POST /api/admin/companies/:ticker/run-llm-draft`

These can be deferred if ingestion stays script-driven.

---

## 13. Authorization requirements

Scott’s admin interaction with the DB must be authorized through the backend, not through direct browser DB access.

### Requirements

* admin UI must require authentication
* backend must verify admin identity before any mutation
* public API and admin API must be fully separated by route/middleware
* database credentials must never be exposed to the browser
* only backend/service accounts may write to the database
* all admin mutations should be audited

### Recommended model

* session cookie or token-based auth for admin UI
* role-based access control, even if there is only one admin initially
* backend-enforced authorization on every admin endpoint

---

## 14. Frontend spec

## 14.1 Public frontend

React frontend for public viewing.

Pages:

* `/`
* `/company/:ticker`
* `/methodology`

Components:

* company table/cards
* factor score display
* sizing display
* optional comment panel
* last updated badge

Characteristics:

* read-only
* simple
* fast
* cacheable
* no login flows

## 14.2 Admin frontend

Separate admin React app or an `/admin` section.

Pages:

* `/admin/login`
* `/admin`
* `/admin/companies`
* `/admin/company/:ticker`
* `/admin/company/:ticker/history`

Components:

* company admin table
* assessment editor form
* factor editor
* publish action controls
* evidence viewer
* history/version comparison

This should be optimized for Scott’s workflow, not for public presentation.

---

## 15. Backend spec

## 15.1 Rust backend responsibilities

The Rust service should:

* serve public read-only endpoints
* serve authenticated admin endpoints
* validate and authorize admin actions
* persist company and assessment data
* expose published snapshots cleanly
* handle versioning and publish transitions
* optionally host calculation logic

## 15.2 Publish transaction behavior

Publishing a company assessment should be an atomic transaction:

1. validate draft completeness
2. calculate aggregate/sizing outputs
3. archive previous published version for that company
4. mark new version as published
5. update company public state
6. record audit/publish event

This ensures only one published version exists at a time.

---

## 16. Versioning rules

Since Scott wants one current published assessment plus historical tracking:

### Rules

* every meaningful edit should update the current draft
* publish creates or finalizes a versioned assessment record
* previous published versions become archived, not deleted
* public UI always reads the latest published version only
* admin UI can access all versions

### Recommended version semantics

For each company:

* version 1, 2, 3, etc.
* exactly one `published`
* zero or more `archived`
* optionally one active `draft`

---

## 17. Update cadence

Updates are ad hoc, so the system should not assume a fixed publishing schedule.

Implications:

* public UI should always show “last updated” or “as of” date
* no need for cron-driven client refresh assumptions
* admin UI should support manual publish timing
* ingestion can remain on-demand or semi-manual initially

---

## 18. Calculation and display rules

The sizing logic remains deterministic and internal.

### Publicly visible

* final factor scores
* final sizing output
* optional final comment
* last updated date

### Admin/internal only

* calculation details if needed
* intermediate normalized values
* evidence backing
* LLM-generated rationale
* internal rationale per factor

This matches the requirement that only final human-approved reasoning should appear externally.

---

## 19. Implications for the existing Python scripts

Your current Python extraction scripts fit naturally into the internal pipeline.

### Outlook extractor

Continue using it to populate internal source records. The resulting emails should remain admin-only and never be shown publicly.

### Forum extractor

Continue using it to populate internal source records. Forum posts also remain admin-only unless Scott later chooses to surface derived comments based on them.

### Normalization step

Add a post-processing step that writes normalized records into the cloud database or into an import format consumed by the admin backend.

---

## 20. Recommended v1 scope

### Public app

* public dashboard
* company detail pages
* methodology page
* factor scores
* sizing display
* optional final comment
* no auth

### Admin app

* login
* company list
* assessment editor
* factor editing
* public comment toggle/edit
* evidence viewer
* publish flow
* version history

### Internal pipeline

* continue Python ingestion
* normalize source records
* optionally store LLM first-pass drafts
* write to DB for admin review

---

## 21. Key open implementation decisions

Still worth deciding next:

* whether admin UI is a separate app or `/admin` section of same app
* whether public comment is plain text only or supports rich text
* whether publish requires explicit confirmation and preview
* whether calculation inputs besides factors are editable in admin
* whether evidence viewer should support search/filter by source/date
* whether admin wants side-by-side version diff view

---

## 22. Recommended next step

The next useful pass is an **implementation spec** with:

* concrete SQL schema
* Rust endpoint contracts
* admin/public page map
* publish-state machine
* wireframe-level UI outline for Scott’s admin workflow
