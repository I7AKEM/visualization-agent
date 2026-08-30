from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pydantic_ai.models
import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import DeferredToolRequests
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.response_types import BaseChunk, DataChunk

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
REQUEST_BODY = json.dumps(
    {
        "trigger": "submit-message",
        "id": "compatibility-chat",
        "messages": [
            {
                "id": "user-message-1",
                "role": "user",
                "parts": [{"type": "text", "text": "Run the offline compatibility probe."}],
            }
        ],
    }
).encode()


async def _encode_normalized(events: AsyncIterator[BaseChunk]) -> str:
    encoded: list[str] = []
    text_id: str | None = None
    async for event in events:
        payload = event.encode(7)
        if payload == "[DONE]":
            encoded.append("data: [DONE]\n\n")
            continue
        document = json.loads(payload)
        event_type = document.get("type", "")
        if event_type == "text-start":
            text_id = document["id"]
        if event_type in {"text-start", "text-delta", "text-end"} and document.get("id") == text_id:
            document["id"] = "text-part-1"
        if event_type == "message-metadata":
            document["messageMetadata"]["pydantic_ai"]["timestamp"] = "1970-01-01T00:00:00Z"
        encoded.append(f"data: {json.dumps(document, separators=(',', ':'), sort_keys=True)}\n\n")
    return "".join(encoded)


async def _custom_data(_: Any) -> AsyncIterator[DataChunk]:
    yield DataChunk(
        type="data-run-status",
        id="run-status-1",
        data={"stage": "complete", "progress": 1.0},
    )


async def _text_and_custom_stream() -> tuple[dict[str, str], str]:
    agent = Agent(TestModel(custom_output_text="Compatibility passed."))
    adapter = VercelAIAdapter(
        agent=agent,
        run_input=VercelAIAdapter.build_run_input(REQUEST_BODY),
        sdk_version=7,
        server_message_id="server-message-1",
    )
    stream = await _encode_normalized(
        adapter.run_stream(
            conversation_id="compatibility-chat",
            run_id="compatibility-text-run",
            on_complete=_custom_data,
        )
    )
    return dict(adapter.build_event_stream().response_headers or {}), stream


async def _hitl_stream() -> str:
    agent = Agent(
        TestModel(call_tools=["protected_action"]),
        output_type=[str, DeferredToolRequests],
    )

    @agent.tool_plain(requires_approval=True)
    def protected_action(value: str) -> str:
        """A deterministic tool that must never execute before server approval."""
        raise AssertionError(f"protected action executed unexpectedly: {value}")

    adapter = VercelAIAdapter(
        agent=agent,
        run_input=VercelAIAdapter.build_run_input(REQUEST_BODY),
        sdk_version=7,
        server_message_id="server-message-1",
    )
    return await _encode_normalized(
        adapter.run_stream(
            conversation_id="compatibility-chat",
            run_id="compatibility-hitl-run",
        )
    )


@pytest.mark.anyio
async def test_pydantic_ai_236_emits_ai_sdk_7_text_and_custom_data_golden() -> None:
    headers, observed = await _text_and_custom_stream()
    expected = (FIXTURES / "pydantic-ai-2.36.0-text-custom.sse").read_text(encoding="utf-8")
    assert headers == {"x-vercel-ai-ui-message-stream": "v1"}
    assert observed == expected
    assert pydantic_ai.models.ALLOW_MODEL_REQUESTS is False


@pytest.mark.anyio
async def test_pydantic_ai_236_emits_ai_sdk_7_hitl_approval_golden() -> None:
    observed = await _hitl_stream()
    expected = (FIXTURES / "pydantic-ai-2.36.0-hitl.sse").read_text(encoding="utf-8")
    assert observed == expected
    assert '"type":"tool-approval-request"' in observed
    assert '"type":"tool-output-available"' not in observed
    assert pydantic_ai.models.ALLOW_MODEL_REQUESTS is False
