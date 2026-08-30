from __future__ import annotations

import pydantic_ai.models
import pytest


@pytest.fixture(autouse=True)
def block_real_model_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every ordinary test offline even if a developer shell has provider keys."""
    monkeypatch.setattr(pydantic_ai.models, "ALLOW_MODEL_REQUESTS", False)
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PYDANTIC_AI_ALLOW_MODEL_REQUESTS", "false")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
