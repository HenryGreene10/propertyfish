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
