#!/usr/bin/env python3
"""Prove the CI interpreter cannot issue Pydantic AI real-model requests."""

from __future__ import annotations

import os
import sys

import pydantic_ai.models

if pydantic_ai.models.ALLOW_MODEL_REQUESTS:
    print("ERROR: pydantic_ai.models.ALLOW_MODEL_REQUESTS is enabled", file=sys.stderr)
    raise SystemExit(1)
for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY"):
    if os.environ.get(key):
        print(f"ERROR: {key} must be absent from ordinary CI", file=sys.stderr)
        raise SystemExit(1)
print("PASS: Pydantic AI real-model requests are disabled and provider keys are absent")
