import { act } from "react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { UiCompatibilityProbe } from "./ui-probe";

declare global {
  // React uses this marker to make act() diagnostics deterministic in tests.
  var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}

describe("React 19 / Ant Design hydration compatibility", () => {
  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    globalThis.ResizeObserver ??= class ResizeObserverStub {
      disconnect() {}
      observe() {}
      unobserve() {}
    };
    window.matchMedia ??= () =>
      ({
        matches: false,
        media: "",
        onchange: null,
        addListener() {},
        removeListener() {},
        addEventListener() {},
        removeEventListener() {},
        dispatchEvent: () => false,
      }) as MediaQueryList;
  });

  afterEach(() => {
    document.body.replaceChildren();
  });

  it("hydrates server markup without a React recoverable error", async () => {
    const markup = renderToString(<UiCompatibilityProbe />);
    const container = document.createElement("div");
    container.innerHTML = markup;
    document.body.append(container);

    const recoverableErrors: unknown[] = [];
    const root = hydrateRoot(container, <UiCompatibilityProbe />, {
      onRecoverableError(error) {
        recoverableErrors.push(error);
      },
    });

    await act(async () => undefined);
    expect(recoverableErrors).toEqual([]);
    expect(container.textContent).toContain("Hydration probe");
    expect(container.textContent).toContain("Compatibility");

    await act(async () => root.unmount());
  });
});
