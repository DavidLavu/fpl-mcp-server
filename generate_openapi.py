from fastapi.openapi.utils import get_openapi
from main import app
import json

openapi_schema = get_openapi(
    title=app.title,
    version=app.version,
    description=app.description,
    routes=app.routes,
)

with open("openapi_v2.json", "w", encoding="utf-8") as f:
    json.dump(openapi_schema, f, indent=2)

