## Ratio Project Spec

### 1. Product summary

Build a public, read-only dashboard that shows a curated set of portfolio companies. For each published company, clients can see:

* final factor scores
* final sizing output
* an optional final comment that PM explicitly enables for public display

PM manages the underlying data through an authenticated admin UI backed by a server-side API. Internal ingestion scripts, source documents, LLM drafts, and review history support that workflow, but none of that internal material is exposed publicly.

The sizing methodology itself is defined in [sizing_logic.md](/mnt/c/Users/Ross/projects/ratio/docs/sizing_logic.md). This spec treats that document as the source of truth for calculation rules.

---

## 2. Fixed product rules

These are non-negotiable v1 requirements:

* the public app is read-only and requires no login
* all public viewers see the same published company set
* clients see only final published values
* clients never see raw emails, forum posts, citations, drafts, internal notes, or LLM outputs
* the only narrative text that may appear publicly is an optional final comment approved by PM
* records are updated ad hoc, so public pages must show a last updated or as-of date
* PM needs an authenticated admin UI
* all admin reads and writes go through an authorized backend; the browser must never have direct database access
* each company has at most one current published assessment
* historical versions must be retained for admin use

---

## 3. Users and app surfaces

### 3.1 Public viewer

Unauthenticated, read-only.

Can:

* view the public dashboard
* view company detail pages
* view published factor scores and sizing output
* view the optional published comment when enabled
* view the public methodology page

Cannot:

* view raw sources or internal evidence
* view draft assessments or version history
* view internal reasoning or LLM-generated content
* edit data or trigger analysis

### 3.2 PM/admin

Authenticated.

Can:

* sign into the admin UI
* manage which companies appear publicly
* review internal source material and evidence links
* inspect draft and published assessments
* edit factor scores and final comments
* publish and unpublish companies
* review historical versions and audit history

### 3.3 Application structure

The system should have two clearly separated surfaces, whether or not they share the same backend:

* public app: serves published, read-only content
* admin app: authenticated surface for review, editing, publishing, and internal evidence

Routing, permissions, and API access must keep those surfaces separate.

---

## 4. Public product requirements

### 4.1 Dashboard

The main page shows the current published company set. For each company, display:

* company name
* ticker
* factor scores
* aggregate score if the product chooses to show it
* current sizing output
* last updated or as-of date
* whether a public comment is available

Expected capabilities:

* search by company name or ticker
* sort by ticker, score, sizing, and update date
* optional filtering later if it becomes useful

Because there is no login and all viewers see the same content, this page should be aggressively cacheable.

### 4.2 Company detail page

Each public company page should show:

* company name and ticker
* final published factor scores
* sizing output
* optional final published comment
* last published or as-of date
* methodology or calculation version label

It must not show:

* raw evidence
* citations
* internal rationale chains
* draft history
* LLM involvement

### 4.3 Methodology page

Provide a public explanation of:

* the factor framework at a high level
* how scores map to sizing
* the fact that assessments are human-reviewed before publication
* the ad hoc update cadence

This page should explain the method without exposing internal workflow detail that clients do not need.

---

## 5. Admin product requirements

### 5.1 Admin dashboard

The main internal landing page should show:

* all tracked companies
* publication status
* current draft versus published state
* last updated timestamp
* whether the public comment is enabled
* quick actions for edit, publish, history, and evidence

### 5.2 Company assessment editor

For a selected company, PM should be able to:

* view the current published assessment
* view or create the current draft assessment
* edit factor values
* edit sizing-related inputs if the product allows manual overrides, otherwise recalculate automatically
* edit the final public comment
* toggle whether that comment is visible publicly
* save drafts
* publish the current draft

### 5.3 Internal evidence view

Admin-only evidence pages or panels should expose:

* Outlook-derived items
* forum-derived items
* internal evidence links and citations
* timestamps and source type
* LLM first-pass output when available
* internal notes

### 5.4 Version history and auditability

PM should be able to:

* see all historical assessment versions for a company
* compare versions
* inspect who changed what and when
* restore an earlier version into a new draft if needed

### 5.5 Company visibility management

PM should be able to:

* add or remove companies from the public dashboard
* keep a company draft-only, published, or hidden
* reorder display if needed

Because all clients see the same company set, there is no per-client entitlement model in v1.

---

## 6. Publication and visibility model

### 6.1 Publicly visible data

Only these fields may appear in the public app or public API:

* company identity
* final factor scores
* final sizing output
* optional final public comment approved by PM
* published timestamp or as-of date
* methodology or calculation version label

### 6.2 Admin-only data

The following remain internal:

* extracted emails
* extracted forum posts
* source snippets and evidence associations
* LLM draft scores and rationale
* internal notes
* factor-level internal rationale
* intermediate calculation values unless the admin UI explicitly needs them

### 6.3 Publication rules

* one company may have many historical assessments
* one company may have zero or one active draft
* one company may have at most one published assessment
* publishing must replace the current published assessment atomically
* previously published versions are archived, not deleted

---

## 7. Assessment lifecycle

For each company, the normal workflow is:

1. ingest source material through internal scripts
2. create or refresh a draft assessment
3. review source evidence and draft output
4. edit scores and the final comment
5. publish the approved draft
6. archive the previously published version in history

This lifecycle is intentionally human-in-the-loop. LLM output can assist with drafting, but only PM-approved values become public.

---

## 8. Calculation rules

The detailed sizing method lives in [sizing_logic.md](/mnt/c/Users/Ross/projects/ratio/docs/sizing_logic.md). In this spec, the implementation requirements are:

* factor scoring and sizing calculations must follow that document exactly
* public surfaces show final factor scores and final sizing output, not intermediate math unless intentionally exposed
* admin surfaces may show calculation details, normalized values, or debug information if helpful for review
* calculation versioning should be tracked so published assessments can be tied to the logic used at the time
* precision should be preserved internally and rounded only for display

Any additional safeguards such as beta floors or position caps should be implemented consistently with the sizing reference.

---

## 9. Data model

### 9.1 `companies`

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

### 9.2 `source_documents`

Admin-only raw source records.

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

### 9.3 `assessments`

Versioned assessments across draft, published, and archived states.

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

Constraint:

* only one row per company may have `status = published`

### 9.4 `assessment_factors`

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

In v1, factor-level rationale can remain internal even if the public app later chooses to expose more detail.

### 9.5 `assessment_evidence_links`

Admin-only evidence associations.

Fields:

* `id`
* `assessment_id`
* `factor_key` nullable
* `source_document_id`
* `relevance_rank`
* `evidence_note` nullable
* `used_by_llm`
* `used_in_final_review`

### 9.6 `admin_users`

Fields:

* `id`
* `email`
* `name`
* `role`
* `password_hash` or auth provider subject
* `status`
* `created_at`
* `last_login_at`

### 9.7 `audit_events`

Fields:

* `id`
* `actor_user_id`
* `event_type`
* `entity_type`
* `entity_id`
* `before_json`
* `after_json`
* `created_at`

### 9.8 `publish_events`

Optional but useful for a clear publication trail.

Fields:

* `id`
* `company_id`
* `assessment_id`
* `published_by`
* `published_at`
* `notes` nullable

---

## 10. API surface

### 10.1 Public API

The public API is read-only and returns published content only.

Endpoints:

* `GET /api/public/companies`
* `GET /api/public/companies/:ticker`
* `GET /api/public/methodology`

The public company payload should include only the fields allowed by the publication model:

* ticker
* company name
* factor scores
* aggregate score if displayed
* sizing output
* public comment when enabled
* published timestamp

### 10.2 Admin API

The admin API requires authentication and authorization.

Auth endpoints:

* `POST /api/admin/auth/login`
* `POST /api/admin/auth/logout`
* `GET /api/admin/auth/me`

Company endpoints:

* `GET /api/admin/companies`
* `GET /api/admin/companies/:ticker`
* `PATCH /api/admin/companies/:ticker`
* `POST /api/admin/companies`
* `POST /api/admin/companies/:ticker/publish`
* `GET /api/admin/companies/:ticker/history`

Assessment endpoints:

* `GET /api/admin/assessments/:id`
* `POST /api/admin/companies/:ticker/drafts`
* `PATCH /api/admin/assessments/:id`
* `POST /api/admin/assessments/:id/recalculate`

Evidence endpoints:

* `GET /api/admin/companies/:ticker/evidence`
* `GET /api/admin/companies/:ticker/evidence/emails`
* `GET /api/admin/companies/:ticker/evidence/forum-posts`

Optional internal workflow endpoints later:

* `POST /api/admin/companies/:ticker/run-ingestion`
* `POST /api/admin/companies/:ticker/run-llm-draft`

---

## 11. Auth, backend, and transaction requirements

### 11.1 Authorization model

* the admin UI must require authentication
* the backend must authorize every admin read and mutation
* public and admin routes must be separated by route structure and middleware
* database credentials must never be exposed to the browser
* only backend or service accounts may write to the database
* admin mutations should be audited

Even if PM is the only admin initially, use backend-enforced roles so the model remains extensible.

### 11.2 Backend responsibilities

The backend service should:

* serve public read-only endpoints
* serve authenticated admin endpoints
* validate and authorize admin actions
* persist company, factor, evidence, and assessment data
* expose clean published snapshots for the public app
* manage versioning and publish transitions
* optionally host calculation logic directly

### 11.3 Publish transaction behavior

Publishing a draft should be an atomic transaction:

1. validate draft completeness
2. calculate or verify aggregate and sizing outputs
3. archive the current published version for that company
4. mark the new version as published
5. update company public state if needed
6. record audit and publish events

This guarantees that only one published assessment exists at a time.

---

## 12. Frontend requirements

### 12.1 Public frontend

Public routes:

* `/`
* `/company/:ticker`
* `/methodology`

Core UI elements:

* company table or cards
* factor score display
* sizing display
* optional comment panel
* last updated badge

Characteristics:

* read-only
* simple and fast
* cache-friendly
* no login flows

### 12.2 Admin frontend

Use either a separate admin app or an `/admin` section.

Admin routes:

* `/admin/login`
* `/admin`
* `/admin/companies`
* `/admin/company/:ticker`
* `/admin/company/:ticker/history`

Core UI elements:

* company admin table
* assessment editor form
* factor editor
* publish controls
* evidence viewer
* history or version comparison view

The admin UI should optimize for PM’s review and publishing workflow rather than public presentation.

---

## 13. Pipeline integration

Existing Python extraction scripts fit into the internal pipeline:

* Outlook extraction populates admin-only source records
* forum extraction populates admin-only source records
* a normalization step should write structured records into the main database or another import format the backend can consume
* LLM-generated first-pass drafts can be stored for review, but remain internal

If ingestion remains script-driven in v1, workflow endpoints for ingestion and draft generation can be deferred.

---

## 14. Recommended v1 scope

### Public app

* dashboard
* company detail page
* methodology page
* factor score display
* sizing display
* optional final comment
* no authentication

### Admin app

* login
* company list
* assessment editor
* factor editing
* public comment toggle and editor
* evidence viewer
* publish flow
* version history

### Internal pipeline

* continue Python-based ingestion
* normalize source records
* optionally store LLM first-pass drafts
* write draft-ready data to the main database

---

## 15. Open implementation decisions

Still worth deciding next:

* whether the admin UI is a separate app or an `/admin` section of the main app
* whether the public comment supports plain text only or rich text
* whether publish requires an explicit confirmation and preview step
* whether any non-factor sizing inputs are manually editable in admin
* whether the evidence viewer needs search or filtering by source and date
* whether version comparison should be side-by-side or change-log based

### Recommended next spec pass

The next useful document would be an implementation spec with:

* concrete SQL schema and constraints
* Rust endpoint contracts
* admin and public page map
* publish state machine
* wireframe-level admin workflow
