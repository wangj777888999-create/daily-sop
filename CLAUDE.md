# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

智能工作台 (AI Workbench) — local-only single-user tool. The headline feature is **SOP automation**: user uploads a Python data-analysis script, the backend parses it into a structured SOP (steps + data sources), the user can re-execute the SOP against new Excel/CSV inputs in a sandbox and download the result.

> **PROJECT_GUIDE.md is outdated** — it claims a Streamlit/Clean-Architecture stack. The real stack is Vue 3 + FastAPI as described below. Trust the code, not that doc.

## Stack & layout

- **Frontend** (`src/`, `index.html`, `vite.config.ts`): Vue 3 + Vue Router + Pinia + TypeScript + Tailwind. Vite dev server on **port 3000** with `/api` proxied to **`http://localhost:8003`**. Path alias `@` → `src/`.
- **Backend** (`backend/`): FastAPI + Pydantic + Pandas. Entrypoint `backend/main.py` mounts `backend/api/routes.py` under `/api`. Virtualenv lives in `backend/.venv`.
- **Persistence** (`data/`): JSON files, no database. `sops.json` (catalog), `execution_logs.json` (history), `uploads/{exec_id}/` (per-execution input files).

Key backend modules in `backend/sops/`:
- `code_parser.py` — Python AST → SOP JSON (`parse_code_with_sources` is the current entrypoint, returns `{name, description, steps, dataSources}`).
- `code_generator.py` — `SOPToExecutableCode(sop_dict)` reverses it back to runnable Python.
- `sandbox.py` — `SandboxExecutor(timeout=60)` runs generated code via `subprocess` with import allow/deny lists and a regex prefilter. Sandbox is best-effort, **not** strong isolation — assumed local-only.
- `storage.py` — JSON read/write with `fcntl` locks and atomic tmp→rename writes.
- `models.py` — Pydantic models. **Status enum is `pending|running|success|failed`** (not `completed`).

## Commands

```bash
# Frontend (run from repo root)
npm install
npm run dev          # Vite dev server on :3000
npm run build        # vue-tsc + vite build → dist/
npm run type-check   # vue-tsc --noEmit (no emit, just typecheck)

# Backend (run from backend/)
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8003

# Backend tests (pytest already configured, .pytest_cache present)
cd backend && pytest                              # all
cd backend && pytest sops/test_data_source.py     # one file
cd backend && pytest sops/test_models.py::TestSOP # one class/test
```

There is no frontend test runner configured.

## Cross-stack contracts (read before changing either side)

The frontend and backend disagree on shape; adapter layers paper over it. **Don't break the adapters without updating both ends.**

1. **SOP Step shape**:
   - Frontend (`src/types/sop.ts`): `{id, order, action, params, description, code?}`
   - Backend (`backend/sops/models.py`): `{step, action, params, description}`
   - Ingress conversion: `_convert_steps_format()` in `backend/api/routes.py`.
   - Egress conversion: `getSOP()` in `src/services/sopApi.ts` re-maps `step → order` and synthesizes `id`.

2. **Execution response**: backend returns `{execution_id, status, error_message, ...}`; frontend expects `{id, status, error, ...}`. `adaptExecutionResponse()` in `src/services/sopApi.ts` is the single mapping point.

3. **Status values**: canonical set is `pending | running | success | failed` everywhere. There is a separate `StepStatus` (`completed` etc.) used only for **step-display** state in `StepBadge.vue` / `types/index.ts` — don't conflate them.

4. **Generated-code file paths** (`backend/api/routes.py` `execute_sop`): when running a SOP, uploaded files go to `uploads/{exec_id}/{safe_filename}` and the generated code gets a `__INPUT_PATHS__ = {...}` dict prepended. Literal filename strings in the generated code are then rewritten to `__INPUT_PATHS__["..."]` lookups. This avoids quoting bugs with non-ASCII / spaces / quotes in filenames — preserve this approach if you touch execution.

## Design tokens

Colors, spacing, typography, radii, and shadows are defined in `tailwind.config.js` (米白 + 鼠尾草绿 palette: `pageBg`, `sidebarBg`, `accent`, `chip`, etc.). Use the tokens, not raw hex. The `ui.md` file at the repo root is the original design spec.

## Operational notes

- **Execution is synchronous and blocks for up to 60s** (the sandbox timeout). Frontend has polling logic that's now mostly cosmetic; if you make execution async, reuse it.
- **Don't add CORS / auth / rate-limiting** unless explicitly asked — `docs/local-audit-report.md` deliberately defers this for the local-only use case.
- The Python sandbox's import filter is regex-based and bypassable; do not present it as a security boundary.
- `教练签到分析最终版.py` at the repo root is a sample SOP-style user script (read-only, used as input for parser testing). Don't treat it as application code.
