$ErrorActionPreference = 'Stop'
$docsPath = (Resolve-Path -LiteralPath 'docs').Path
docker compose run --rm --no-deps `
  --env OPENAPI_OUTPUT_PATH=/export/openapi.json `
  --volume "$docsPath`:/export" `
  backend python scripts/export_openapi.py
