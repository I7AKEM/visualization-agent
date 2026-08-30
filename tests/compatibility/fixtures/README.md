# AI SDK 7 protocol reference fixture

`ai-sdk-7-reference.sse` is a normative-protocol reference assembled from the
official AI SDK UI stream protocol. It exercises message framing, custom data,
and a denied human-in-the-loop tool lifecycle.

It is deliberately not represented as output captured from Pydantic AI 2.36.0.
The exact cross-runtime gate remains pending until the Python slice supplies a
Pydantic-generated SSE fixture. This reference must not be used to justify an
adapter or to mark the Pydantic/AI SDK compatibility decision complete.
