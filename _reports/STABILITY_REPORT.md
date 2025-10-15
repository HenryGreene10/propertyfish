# Stability Report

## A. Executive Summary
Backend automation is currently red: package installation fails because outbound network (pip) requests resolve to `EAI_AGAIN`, so we cannot install `wheel`, `setuptools`, `ruff`, `mypy`, or even `pytest`. As a result FastAPI tests abort before discovery (`ModuleNotFoundError: httpx`), and the `uvicorn` probe fails because we launch the app with `--factory` against a non-factory callable. Frontend automation is partially green: `npm ci` succeeds and `npm run build` produces `.next/`, but developer tooling is missing (`eslint`, `tsc`, `npm run test`) and dependency audits (`npm-check-updates`) fail while offline. No secrets or large binaries are committed, but most required env vars remain unset locally.

## B. Blocking Issues
1. **pip cannot reach PyPI** — `python3 -m venv .venv && source .venv/bin/activate && pip install -U pip wheel` ➜ DNS `EAI_AGAIN` ([log](logs/backend_pip_upgrade.log)). *Fix:* configure network / proxy or provide an internal PyPI mirror.
2. **Editable install fails (setuptools unavailable)** — `pip install -e .` ([log](logs/backend_pip_editable.log)). *Fix:* same network remedy; alternatively vendor wheels inside repo cache.
3. **Backend tests abort before collection** — `pytest -q` ([log](logs/backend_pytest_rerun.log)). Missing `httpx` because pytest itself never installed. *Fix:* restore pip connectivity, add `pytest` + `httpx` to dev requirements, rerun install.
4. **FastAPI boot probe fails** — `uvicorn app.main:app --host 127.0.0.1 --port 8000 --timeout-keep-alive 5 --factory` ([log](logs/backend_uvicorn_factory.log)) raises `FastAPI.__call__()` signature error; subsequent `curl` fails ([log](logs/backend_boot_probe.log)). *Fix:* drop `--factory` (`uvicorn app.main:app`) or return a factory function.
5. **Frontend has no test script** — `npm run test --silent` ([log](logs/frontend_test.log) + verbose [log](logs/frontend_test_verbose.log)). *Fix:* add Jest/Vitest script or stub that exits 0 until tests exist.

Repro (PowerShell):
```powershell
cd backend
python3 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -U pip wheel
pip install -e .
pytest -q
uvicorn app.main:app --host 127.0.0.1 --port 8000 --timeout-keep-alive 5 --factory
```
```powershell
cd frontend
npm run test --silent
```

## C. Non-blocking Issues / Warnings
- **Dependency audit offline** — `npx npm-check-updates -u` fails with `EAI_AGAIN` ([log](logs/frontend_ncu.log)); rerun once internet is available.
- **Lint/type tooling missing** — `./node_modules/.bin/eslint` and `./node_modules/.bin/tsc` not found ([logs](logs/frontend_eslint.log), [logs/frontend_tsc.log]); add `eslint`, `typescript`, configs.
- **Backend static analysis skipped** — `ruff`/`mypy` install failed ([log](logs/backend_tools_install.log)); re-run after network fix.

## D. Env & Secrets Audit
Required keys enumerated in [`env_required.json`](env_required.json). Current shell values ([log](logs/env_current_values.log)) show only `DATABASE_URL` set; everything else (Supabase, Socrata tokens, dataset IDs, frontend `NEXT_PUBLIC_API_BASE`) is missing, so ingestion, OCR, and Supabase features will fail until populated. `.gitignore` now ignores `.env*`, `.supabase/`, `secrets.json`, ensuring secrets stay out of git. No hard-coded secrets detected beyond local `POSTGRES_PASSWORD=postgres` in `infra/docker-compose.yml` (dev only).

## E. Dependency Health
- **Python** — `pip list` ([log](logs/backend_pip_list.log)) shows FastAPI 0.119.0, SQLAlchemy 2.0.44, uvicorn 0.37.0. Outdated comparison blocked by offline PyPI; rerun `pip list --outdated` once connectivity is restored.
- **Node** — `package.json` pins Next 14.2.5 / React 18.2.0. `npx npm-check-updates` failed (`EAI_AGAIN`). After networking returns, run `npx ncu -u && npm install` to surface patches.

## F. Test Status
- **Backend:** `pytest -q` → import error before collection (0 tests run). Primary cause: dev dependencies not installed.
- **Frontend:** `npm run test` missing; no unit test framework configured yet.

## G. Build Status
- **Backend app boot:** fails (see Blocking Issue #4).
- **Frontend build:** `npm run build` completes (`.next/` generated) but log captures only initial lines ([log](logs/frontend_build.log)); rerun with `CI=1` for full output.

## H. Data / Asset Risk
- `git ls-files` reports no tracked files >10 MB ([logs](logs/oversize_files.log), [logs/oversize_10mb_files.log)). Recommend Git LFS if future assets include PDFs, audio, or high-res imagery.

## I. Git Push Checklist
Pending changes (after this stabilization pass): `.gitignore`, backend ingestion tweaks, normalizer helpers, `_reports/*`, diagnostic scripts. No secrets observed. Review with `git status` and `_reports/PUSH_PREVIEW.txt` before pushing. Suggested push command: `git push -u origin chore/stabilize-<YYYYMMDD-HHMM>`.

## J. 24-hour Stabilization Plan
1. Restore outbound package access (or mirror) so pip/npm can fetch `wheel`, `setuptools`, `ruff`, `pytest`, `eslint`, `typescript`.
2. Remove `--factory` from uvicorn check or expose a factory returning `FastAPI` to make the smoke probe pass.
3. Add frontend test script (even placeholder) and devDependencies (`eslint`, `typescript`) so lint/type/test steps succeed.
4. Seed required env vars (Socrata tokens, Supabase creds, dataset IDs) via `.env` or secrets manager; document minimum set.
5. Retry `pytest`, `npm run build`, `npm run test`, and capture clean logs; update report and commit.
