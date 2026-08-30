import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { readUIMessageStream, type UIMessageChunk } from "ai";
import { describe, expect, it } from "vitest";

function parseReferenceSse(source: string): UIMessageChunk[] {
  return source
    .split(/\r?\n\r?\n/u)
    .map((event) =>
      event
        .split(/\r?\n/u)
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n"),
    )
    .filter((data) => data.length > 0 && data !== "[DONE]")
    .map((data) => JSON.parse(data) as UIMessageChunk);
}

describe("AI SDK 7 UI message compatibility reference", () => {
  it("consumes custom data and a denied HITL tool lifecycle", async () => {
    const fixturePath = resolve(
      process.cwd(),
      "../../tests/compatibility/fixtures/ai-sdk-7-reference.sse",
    );
    const chunks = parseReferenceSse(await readFile(fixturePath, "utf8"));
    const stream = new ReadableStream<UIMessageChunk>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(chunk);
        controller.close();
      },
    });

    const observedToolStates = new Set<unknown>();
    let finalMessage: { parts: Array<Record<string, unknown>> } | undefined;

    for await (const message of readUIMessageStream({ stream })) {
      finalMessage = message as typeof finalMessage;
      for (const part of message.parts as Array<Record<string, unknown>>) {
        if (part.toolCallId === "tool-call-1") observedToolStates.add(part.state);
      }
    }

    expect(finalMessage).toBeDefined();
    expect(finalMessage?.parts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: "data-run-status",
          data: { stage: "approval_required", progress: 0.5 },
        }),
        expect.objectContaining({ type: "text", text: "Approval required." }),
        expect.objectContaining({ toolCallId: "tool-call-1", state: "output-denied" }),
      ]),
    );
    expect(observedToolStates).toContain("approval-requested");
    expect(observedToolStates).toContain("output-denied");
  });

  it("consumes the exact Pydantic AI 2.36.0 custom-data stream", async () => {
    const fixturePath = resolve(
      process.cwd(),
      "../../tests/compatibility/fixtures/pydantic-ai-2.36.0-text-custom.sse",
    );
    const chunks = parseReferenceSse(await readFile(fixturePath, "utf8"));
    const stream = new ReadableStream<UIMessageChunk>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(chunk);
        controller.close();
      },
    });

    let finalMessage: { parts: Array<Record<string, unknown>> } | undefined;
    for await (const message of readUIMessageStream({ stream })) {
      finalMessage = message as typeof finalMessage;
    }

    expect(finalMessage?.parts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: "text", text: "Compatibility passed." }),
        expect.objectContaining({
          type: "data-run-status",
          data: { stage: "complete", progress: 1 },
        }),
      ]),
    );
  });

  it("consumes the exact Pydantic AI 2.36.0 HITL approval stream", async () => {
    const fixturePath = resolve(
      process.cwd(),
      "../../tests/compatibility/fixtures/pydantic-ai-2.36.0-hitl.sse",
    );
    const chunks = parseReferenceSse(await readFile(fixturePath, "utf8"));
    const stream = new ReadableStream<UIMessageChunk>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(chunk);
        controller.close();
      },
    });

    let finalMessage: { parts: Array<Record<string, unknown>> } | undefined;
    for await (const message of readUIMessageStream({ stream })) {
      finalMessage = message as typeof finalMessage;
    }

    expect(finalMessage?.parts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          toolCallId: "pyd_ai_tool_call_id__protected_action",
          state: "approval-requested",
        }),
      ]),
    );
  });
});
