$ErrorActionPreference = 'Stop'

npm --prefix frontend ci
npm --prefix frontend run check
docker compose build
docker compose run --rm --no-deps backend ruff check .
docker compose run --rm --no-deps backend mypy app scripts
docker compose run --rm --no-deps backend pytest
