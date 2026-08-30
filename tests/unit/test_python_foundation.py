from __future__ import annotations

from importlib.metadata import version

import pydantic_ai.models


def test_exact_python_runtime_dependencies_are_installed() -> None:
    assert version("pydantic-ai-slim") == "2.36.0"
    assert version("pydantic-evals") == "2.36.0"
    assert version("pydantic") == "2.13.5"
    assert version("pydantic-settings") == "2.15.0"
    assert version("logfire") == "4.41.0"
    assert version("fastapi") == "0.141.1"


def test_real_model_requests_are_blocked() -> None:
    assert pydantic_ai.models.ALLOW_MODEL_REQUESTS is False


def test_empty_workspace_packages_import() -> None:
    import visualization_agent_api
    import visualization_agent_contracts
    import visualization_agent_evals
    import visualization_agent_worker_analysis
    import visualization_agent_worker_export

    assert visualization_agent_api.__all__ == ()
    assert visualization_agent_contracts.__all__ == ()
    assert visualization_agent_evals.__all__ == ()
    assert visualization_agent_worker_analysis.__all__ == ()
    assert visualization_agent_worker_export.__all__ == ()
