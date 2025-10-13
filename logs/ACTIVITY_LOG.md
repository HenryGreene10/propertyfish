# PropertyFish Activity Log
_Convention: Every time Codex modifies the repository, append an entry:_

- **Timestamp (UTC)**:
- **Author/Agent**: (e.g., Codex)
- **Prompt (summary)**:
- **Files changed**:
- **Notes/Reasons**:

> Codex: Always append a new entry for each prompt you execute. Do not overwrite prior entries.

---

- **Timestamp (UTC)**: 2025-10-12T00:00:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Bootstrap repository structure, create scaffolding files, and log activity.
- **Files changed**: Initialized README, docs (PRD, Data Dictionary, API Contract, Intent Catalogue, Citations Policy, Test Plan), backend (FastAPI app stubs, services, models, db, utils, tests, pyproject), frontend (Next.js stubs), infra (docker-compose, env example, deploy doc), and this activity log.
- **Notes/Reasons**: Establishes initial project layout and minimal working stubs aligned to the provided contract and documentation.

---

- **Timestamp (UTC)**: 2025-10-12T12:00:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Initialize PropertyFish repo, scaffold backend+frontend, and write six docs.
- **Files changed**: README.md, logs/, docs/, backend/, frontend/, infra/
- **Notes/Reasons**: Establish single source of truth and deterministic API contract before coding.

---

- **Timestamp (UTC)**: 2025-10-12T12:30:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Sprint A implemented: PLUTO ingest, /resolve, /summary, tests.
- **Files changed**: backend/app/db/connection.py, backend/app/db/schema.sql, backend/app/db/seeds/pluto_sample.csv, backend/etl/pluto_ingest.py, backend/app/services/property_service.py, backend/app/routers/resolve.py, backend/app/routers/property.py, backend/tests/test_contract_smoke.py, infra/deploy.md
- **Notes/Reasons**: Add RealDictCursor connection, indexes/extensions, seed data and ingest, service layer for summary/resolve, wire routers, tests with monkeypatch, and dev bootstrap notes for Sprint A.

---

- **Timestamp (UTC)**: 2025-10-12T13:00:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Sprint B implemented: ACRIS ingest + /deeds + /mortgages + tests.
- **Files changed**: backend/app/db/seeds/acris_sample.csv, backend/etl/acris_ingest.py, backend/app/services/property_service.py, backend/app/routers/property.py, backend/tests/test_contract_smoke.py, infra/deploy.md
- **Notes/Reasons**: Added ACRIS CSV seed and ingest, service queries for deeds/mortgages, wired endpoints with source metadata, tests via monkeypatch, and Sprint B bootstrap notes.

---

- **Timestamp (UTC)**: 2025-10-12T13:30:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Sprint C implemented: DOB permits/violations, zoning ingest, geo endpoint, tests.
- **Files changed**: backend/app/db/seeds/dob_permits_sample.csv, backend/app/db/seeds/dob_violations_sample.csv, backend/app/db/seeds/zoning_sample.csv, backend/etl/dob_ingest.py, backend/etl/zola_ingest.py, backend/app/services/property_service.py, backend/app/routers/property.py, backend/tests/test_contract_smoke.py, infra/deploy.md
- **Notes/Reasons**: Added DOB and zoning seeds and ETLs, service methods, wired endpoints (/permits, /violations, /zoning, /geo), extended tests, and Sprint C dev bootstrap notes.

---

- **Timestamp (UTC)**: 2025-10-12T14:00:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Sprint D implemented: POST /api/chat/query, DTOs, service logic, tests, and simple frontend page.
- **Files changed**: backend/app/models/dto.py, backend/app/services/chat.py, backend/app/routes.py, backend/app/main.py, backend/tests/test_chat_query.py, frontend/chat.html, infra/deploy.md
- **Notes/Reasons**: Added rules-based chat endpoint with AnswerBundle and citations, mounted under /api/chat/query, tests for core scenarios, and a minimal HTML to exercise the endpoint.

---

- **Timestamp (UTC)**: 2025-10-12T14:10:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Make compose DB-only; remove other services and builds.
- **Files changed**: infra/docker-compose.yml
- **Notes/Reasons**: Simplify local stack to a single Postgres 16 service with persistent volume and healthcheck for faster dev iterations.

---

- **Timestamp (UTC)**: 2025-10-12T14:25:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Stabilize /api/chat/query with minimal seed, dev script, safe SQL; tighten tests.
- **Files changed**: infra/sql/seed_minimal.sql, scripts/dev-up.ps1, backend/app/services/chat.py, backend/tests/test_chat_query.py
- **Notes/Reasons**: Added minimal compatible schema/view seed and a PowerShell bootstrap; refactored chat service to safe SQLAlchemy queries tolerant to missing tables; replaced tests with async HTTPX cases covering BBL/address paths and graceful fallback.

---

- **Timestamp (UTC)**: 2025-10-12T14:30:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Configure pytest asyncio backend and harden chat safe-query rollback.
- **Files changed**: pytest.ini, backend/app/services/chat.py, logs/ACTIVITY_LOG.md
- **Notes/Reasons**: Ensure async tests run under asyncio; wrap all DB calls with SQLAlchemyError rollback to prevent InFailedSqlTransaction and degrade gracefully.

---

- **Timestamp (UTC)**: 2025-10-12T14:40:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Add runtime and dev dependency files.
- **Files changed**: requirements.txt, requirements-dev.txt, logs/ACTIVITY_LOG.md
- **Notes/Reasons**: Provide pinned dependency lists for runtime and tests, including asyncio/trio stack to satisfy anyio backends.

---

- **Timestamp (UTC)**: 2025-10-12T14:45:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Update pytest.ini for asyncio; add pytest-cov; make chat safe queries commit/rollback.
- **Files changed**: pytest.ini, requirements-dev.txt, backend/app/services/chat.py, logs/ACTIVITY_LOG.md
- **Notes/Reasons**: Ensure async tests run with asyncio only; include coverage plugin; avoid transaction poisoning by committing successful queries and rolling back on errors.

---

- **Timestamp (UTC)**: 2025-10-12T14:55:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Chat service: always emit section lines; align queries to seed tables/views; use safe query helper everywhere.
- **Files changed**: backend/app/services/chat.py, logs/ACTIVITY_LOG.md
- **Notes/Reasons**: Ensures consistent summaries for permits/violations/zoning/properties even on empty datasets and uses the unified permits_violations view with resilient DB calls.

---

- **Timestamp (UTC)**: 2025-10-12T15:00:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Refine chat: always include permits/violations sections, explicit zoning no-match message, ordered source dedupe.
- **Files changed**: backend/app/services/chat.py, logs/ACTIVITY_LOG.md
- **Notes/Reasons**: Match intent handling and messaging; ensure citations tables are dob_permits/dob_violations and sources preserve order without duplicates.

---

- **Timestamp (UTC)**: 2025-10-12T15:05:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Seed SQL: drop/recreate permits_violations view with explicit columns.
- **Files changed**: infra/sql/seed_minimal.sql
- **Notes/Reasons**: Ensures reproducible view definition even after schema drift; canonicalizes column names to match chat service expectations.

---

- **Timestamp (UTC)**: 2025-10-12T15:10:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Chat address parsing and contains-match filtering for properties.
- **Files changed**: backend/app/services/chat.py, logs/ACTIVITY_LOG.md
- **Notes/Reasons**: Added robust _extract_address regex, switched address filters to ILIKE %%contains%%, and fall back to parsing the question when no address detected.

---

- **Timestamp (UTC)**: 2025-10-12T15:12:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Ensure violations section always includes a dob_violations citation.
- **Files changed**: backend/app/services/chat.py, logs/ACTIVITY_LOG.md
- **Notes/Reasons**: Adds a synthetic citation when no row-level citations are available so UI badges/tests remain consistent.

---

- **Timestamp (UTC)**: 2025-10-12T15:14:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Adjust synthetic citation shape to minimal `{table:"dob_violations"}`.
- **Files changed**: backend/app/services/chat.py
- **Notes/Reasons**: Aligns with requested minimal citation format and keeps sources appended.

---

- **Timestamp (UTC)**: 2025-10-12T14:15:00Z
- **Author/Agent**: Codex
- **Prompt (summary)**: Add pytest.ini at repo root to set pythonpath.
- **Files changed**: pytest.ini, logs/ACTIVITY_LOG.md
- **Notes/Reasons**: Ensure pytest discovers backend app by adding `backend` to pythonpath for tests.
