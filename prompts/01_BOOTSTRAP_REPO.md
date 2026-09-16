# Prompt 01 — Bootstrap repository only

Ты работаешь в новом репозитории MAX ДВИЖ.

Сначала полностью прочитай `AGENTS.md`, все `docs/*.md`, `frontend/AGENTS.md`, `backend/AGENTS.md`, `CHECKLIST.md`.

На ЭТОМ этапе подготовь репозиторий к реализации, но не реализовывай продукт целиком.

Сделай:
1. Проверь документы на блокирующие противоречия. Не переписывай продукт самовольно.
2. Создай структуру по `docs/06_ARCHITECTURE.md`.
3. Инициализируй React+TS+Vite frontend, FastAPI backend, PostgreSQL/migrations, Dockerfiles, compose.yaml, lock files, formatter/lint/typecheck/tests.
4. Сохрани specification files без потери содержания.
5. Создай skeleton README со всеми разделами `docs/14_HACKATHON_SUBMISSION.md`, честно пометив неготовое.
6. Создай skeleton `DATA-API.yaml` и механизм export OpenAPI без выдумывания несуществующих контрактов.
7. Создай module/feature folders, но не делай fake product UI.
8. Сделай healthcheck + minimal frontend shell, чтобы Docker stack реально запускался.
9. Добавь базовый check/CI script, если это не мешает.
10. Запусти lint/typecheck/tests/build/Docker smoke.

Не делай matching engine, fake CandidatePlans, фейковые интеграции, AI или “готовый” моковый продукт.

В конце перечисли структуру, команды, результаты проверок, blockers и предложи commit message.

Не прекращай после генерации файлов: добейся реально запускаемого skeleton repo.
