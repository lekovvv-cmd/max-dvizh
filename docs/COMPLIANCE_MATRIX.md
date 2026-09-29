# Матрица соответствия требованиям сдачи

Срез до изменений: `main` на `55913c5b3f92625a9e87342668d0a02099049208` (29.09.2026). Статусы показывают состояние **на старте** этой работы, а не утверждают готовность финальной сдачи. `promts/` и `output/` были локальными неотслеживаемыми каталогами; они не входят в проверяемый код.

| REQUIREMENT | STATUS | EVIDENCE | ACTION |
| --- | --- | --- | --- |
| Работающее решение в MAX | NEEDS_TEAM_INPUT | Код MAX auth, webhook и worker есть; живой MAX mobile/web в репозитории не подтверждён | Проверить на production с реальным ботом |
| Git repository + fixed commit | PARTIAL | Репозиторий и стартовый SHA есть; финальный SHA сдачи не установлен | Зафиксировать финальный SHA перед отправкой |
| README completeness | PARTIAL | Сценарий и запуск есть, но env, порты, данные и проверочный путь разрознены | Дополнить README |
| Single-command Docker start | PARTIAL | `compose.yaml` содержит пять обязательных сервисов | Проверить `docker compose up --build` и smoke |
| Environment variables | PARTIAL | `.env.example` содержит переменные; нет таблицы назначения | Добавить таблицу в README |
| Ports | PARTIAL | `compose.yaml` публикует 8080, 8000, 5432 | Описать переназначение и Redis |
| Dependencies | DONE | `frontend/package-lock.json`, `backend/requirements.lock` | Указать источники истины в README |
| External integrations | PARTIAL | MAX, KudaGo, Geoapify, PostgreSQL, Redis описаны в разных файлах | Собрать обязательность, ключи и отказы |
| Data handling | PARTIAL | `docs/SECURITY_AND_DATA.md`, ORM-модели | Кратко описать в README |
| Test/demo data | PARTIAL | Dev-only `X-Demo-User`, UI-переключатель, старый `seed-demo` endpoint | Описать воспроизводимый путь без синтетического провайдера |
| Verification steps and expected behavior | PARTIAL | `docs/TESTING.md` описывает проверки; нет короткого маршрута эксперта | Создать `EVALUATOR_SCENARIO.md` |
| Known limitations | PARTIAL | Ограничения источников есть, но не выделены в README | Сделать явный раздел |
| Stop/restart instructions | MISSING | README описывает только запуск | Добавить down, down -v, up |
| Lock files | DONE | Оба lock-файла присутствуют | Сохранить |
| Dockerfiles | DONE | `backend/Dockerfile`, `frontend/Dockerfile` | Сохранить |
| Compose and `.dockerignore` | DONE | `compose.yaml`, корневой и оба сервисных `.dockerignore` | Проверить config/build/smoke |
| `.env.example` | PARTIAL | Секреты пусты, локальный пароль подписан как dev-only | Уточнить необязательные и production-переменные |
| OpenAPI | PARTIAL | `docs/openapi.json` существует, но отстаёт от текущей генерации на два пути | Перегенерировать из FastAPI |
| `DATA-API.yaml` | PARTIAL | Есть роли и запросы; не все параметры/форматы ответа описаны | Сверить с текущим API |
| Public API base URL | NEEDS_TEAM_INPUT | `base_url: null`; подтверждённого HTTPS URL нет | Заполнить перед сдачей |
| Test accounts | NEEDS_TEAM_INPUT | Локальные demo ID возможны; MAX test accounts не указаны | Команда предоставляет MAX-аккаунты |
| Test data | PARTIAL | Demo identities создаются при первом запросе, provider-каталога в БД нет | Описать подготовку компании и ограничения источников |
| Security/secrets | PARTIAL | `.env*` игнорируются; scan ещё не выполнен | Проверить отслеживаемые файлы и docs |
| Source attribution | PARTIAL | Провайдер и source URL есть у кандидата; `source_fetched_at` есть у нормализованного ответа/старого снимка плана, но не у `dvizh_candidates` | Явно описать различие без ложного claim |
| Metrics | DONE | `docs/PRODUCT_METRICS.md`, CLI из БД | Кратко указать без заявлений об эффекте |
| Architecture | DONE | `docs/ARCHITECTURE.md` и модели | Дать краткую карту в README |
| MAX integration docs | PARTIAL | `docs/API.md`, `docs/DEPLOY_RELAXDEV.md` | Дать единый проверочный путь и prerequisites |
| Презентация, пилот, доказательства проблемы | NEEDS_TEAM_INPUT | Финального PDF и результатов исследования/пилота нет | Дать чек-листы без вымышленных значений |
| CI после этой работы | PARTIAL | Workflow настроен; новые изменения ещё не запущены | Дождаться результатов после push |

`NOT_APPLICABLE`: отдельный production seed аккаунтов — локальный demo auth создаёт пользователя на первом запросе и запрещён в production.
