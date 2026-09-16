import json
from os import getenv
from pathlib import Path

from app.main import app

output_path = Path(getenv("OPENAPI_OUTPUT_PATH", "docs/openapi.json"))
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(
    json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"OpenAPI exported to {output_path}")
