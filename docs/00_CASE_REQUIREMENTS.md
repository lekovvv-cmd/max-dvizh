# 00 — Требования кейса «Досуг и развлечения»

Source: uploaded case PDF, 22 pages. This file converts the case into implementation constraints.

## Product requirements

Нужно самостоятельно:
- определить конкретного пользователя и приоритетный сегмент;
- выбрать конкретный проблемный участок пути в досуге;
- подтвердить актуальность проблемы;
- показать полезный результат;
- реализовать один приоритетный сценарий от начала до конца;
- определить измеримый ожидаемый эффект;
- объяснить масштабирование и условия внедрения.

Недостаточно формулировок «пользователи досуга», «туристы», «сделаем AI-ассистента/агрегатор». Сначала проблема, затем технология.

## MAX is mandatory

Основной сценарий должен проверяться в MAX.

Допустимо:
- chatbot;
- chatbot + connected Mini App.

Mini App подключается к боту и не является изолированным сервисом.

Работа должна быть доступна в:
- MAX mobile;
- MAX web.

## Data/integrations

Нужно учитывать происхождение, актуальность, территорию и период данных.

Если реальной интеграции нет, тестовые/синтетические/подготовленные данные разрешены, но должны быть явно обозначены.

Нельзя выдавать смоделированную интеграцию за настоящую.

Разделять:
- факт источника;
- расчёт продукта;
- рекомендацию;
- допущение/model data.

## Development restrictions

Нельзя:
- закрытые библиотеки/частные API без разрешения;
- чужой код без подходящей лицензии;
- рабочие токены/пароли/API keys в repo.

Нужно соблюдать законодательство РФ, актуальные правила MAX и правила хакатона.

Документация MAX обновляется: сверять актуальную документацию до разработки и перед сдачей.

Nickname chatbot после создания нельзя менять — выбрать осознанно.

После дедлайна зафиксированную версию кода менять нельзя до разрешённого этапа.

## Online score: product = 40%

Внутри продуктовой оценки:

### Scaling potential — 35%
- конкретные другие контексты/регионы/организации;
- условия адаптации;
- данные/интеграции/ресурсы;
- риски;
- реалистичный порядок тиражирования.

### User value — 25%
- конкретная ЦА;
- конкретная потребность;
- полезный результат;
- преимущество над текущим способом;
- подтверждение данными/наблюдениями/интервью/аргументированными допущениями.

### UX/UI — 20%
- цельный основной путь;
- понятные действия;
- loading/result/error feedback;
- без тупиков и лишних шагов.

### Coherence — 15%
- логика проблема → механика → результат;
- аргументированные решения;
- функции образуют единый продукт;
- реалистичность.

### Presentation — 5%
- быстро понятна проблема/решение/результат;
- читаемые схемы;
- без перегруза.

## Online score: technical = 60%

### Core functionality — 30%
Основной flow полностью проходится; ключевые функции реально работают; own API checks pass.

### Integration/data exchange — 20%
Компоненты, состояния, внешние интеграции и API contract корректны и предсказуемы.

### Stability/error handling — 10%
Повторное прохождение работает; ошибки обработаны; пользователь может продолжить без полного restart; нет систематических критичных timeout.

### Architecture — 20%
Структура логична для масштаба MVP, компоненты понятны, решения соответствуют функциональности.

### Security/dependencies/data — 10%
Нет secrets in code; версии фиксированы; data access соответствует логике; интеграции описаны; нет очевидных критичных рисков.

### Technical documentation — 10%
Решение воспроизводимо; описаны запуск, архитектура, зависимости, окружение, интеграции, проверки, ограничения.

## MAX platform bonus

+0.15 online bonus возможен за полезное использование MAX сверх минимального требования, если возможность встроена в продукт и работает end-to-end.

Для ДВИЖа цель:
- bot notifications;
- deep links/start context;
- final plan share/return;
- органичная Bot + Mini App связка.

Сам own API/много функций бонуса не дают.

## Mandatory submission

### Working MAX solution
Ссылка/способ пройти core flow.

### Frozen source version
Git repo + commit hash или archive + checksum.

### README must include
- purpose;
- core user flow;
- architecture/components;
- one Docker command to start local components;
- environment requirements;
- env vars;
- ports;
- dependencies;
- integrations;
- data handling;
- test-data handling;
- step-by-step verification;
- expected behavior;
- known limitations;
- stop/restart procedure.

### Dependency lock
Fixed versions for frontend/backend.

### Docker
- Dockerfile(s);
- compose.yaml/docker-compose.yml;
- .dockerignore;
- .env.example without working secrets.

Docker build <= 5 minutes excluding initial base image download.

### PDF presentation
Slide 1 is technical/unscored and must provide verification info: working MAX link, repo+commit, own API URL, test credentials, required verification values/secrets in organizer-prescribed format, short test path.

Do not commit working secrets. Follow organizer delivery format.

From slide 2: team/name, executive summary, target/problem/evidence, solution/flow, expected effect, architecture, data/integrations, scaling/adaptation, risks/assumptions, sources.

## Own API requirements

Our project has a backend API, therefore prepare:
- public HTTPS API;
- OpenAPI 3.0/3.1;
- test accounts as needed;
- test data;
- DATA-API.yaml.

DATA-API.yaml includes config version, solution/team, base URL, required checks, method/path, params/body/headers, role, expected statuses and response required fields.

## Final stage considerations

Final score: technical product 40%, defense 60%.

Need a realistic pilot: who/where, integration into current process, required data/integrations/participants, access channels, pilot metrics, next step.

## Development takeaway

Maximize not feature count but:
1. complete core flow;
2. stability;
3. explainable architecture;
4. honest real data;
5. native MAX value;
6. measurable user value;
7. scalable core/data separation.
