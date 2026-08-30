"""Force Pydantic AI's global real-model request gate off in ordinary CI tests."""

from __future__ import annotations

try:
    import pydantic_ai.models
except ModuleNotFoundError:
    pass
else:
    pydantic_ai.models.ALLOW_MODEL_REQUESTS = False
