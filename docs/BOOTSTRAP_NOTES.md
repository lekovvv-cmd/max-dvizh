# Bootstrap notes

## Specification consistency review

Reviewed on 2026-09-16 against all files in `docs/`, root and scoped `AGENTS.md`, `CHECKLIST.md`, and `prompts/01_BOOTSTRAP_REPO.md`.

No blocking contradiction was found for M0. The sources consistently require a React + TypeScript + Vite frontend, FastAPI backend, PostgreSQL, modular monolith, real migrations, Docker reproducibility, OpenAPI export and `DATA-API.yaml`.

## Deliberate M0 boundary

The repository provides the runnable technical skeleton only. It does not claim or fake product endpoints, candidate plans, matching, provider data, MAX identity or a bot. This preserves the milestone order in `docs/16_IMPLEMENTATION_PLAN.md` and the restriction in `prompts/01_BOOTSTRAP_REPO.md`.
