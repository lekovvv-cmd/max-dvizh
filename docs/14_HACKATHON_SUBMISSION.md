# 14 — Hackathon submission

## Mandatory

### Working MAX solution
Bot/Mini App available and core scenario verifiable.

### Frozen source
Git repo + final commit hash or archive/checksum.

### README
Include purpose, user flow, architecture, one Docker command, environment/env vars/ports/dependencies, integrations, data/test data, verification steps, expected behavior, limitations, stop/restart.

### Dependencies
Lock/fixed versions for frontend/backend.

### Docker
Dockerfile(s), compose.yaml, .dockerignore, .env.example without secrets. Build <=5 minutes excluding initial base-image download.

### Presentation PDF
Slide 1 technical/unscored: MAX link, repo+commit, API URL, test credentials, required verification values/secrets in organizer-required format, short verification path. Never commit secrets.

From slide 2: name/team, executive summary, target/problem/evidence, solution/flow, expected effect, architecture, data/integrations, scaling, risks/assumptions, sources.

## Own API
Prepare public HTTPS API, OpenAPI 3.0/3.1, test accounts/data as needed, DATA-API.yaml.

## DATA-API.yaml
Include config version, solution/team, base URL, mandatory checks, method/path, params/body/headers, role, expected statuses, response required fields.

## Freeze checklist
- clean clone works;
- Docker build time verified;
- migrations documented/automatic;
- no secrets;
- core E2E passes repeatedly;
- provider failure tested;
- MAX mobile/web tested;
- OpenAPI exported;
- DATA-API current;
- README current;
- limitations listed;
- technical slide current;
- final commit hash captured;
- deployed URLs available.

## Bonus target
Document meaningful MAX use: bot notifications, deep links/start context, final share/return. Do not risk core stability for bonus.
