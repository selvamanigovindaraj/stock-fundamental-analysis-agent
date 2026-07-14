import { describe, expect, it } from "vitest";
import { parseSSEEvent } from "./api";

describe("parseSSEEvent", () => {
  it("parses a started event", () => {
    expect(parseSSEEvent("started", JSON.stringify({ ticker: "AAPL" }))).toEqual({
      type: "started",
      ticker: "AAPL",
    });
  });

  it("parses a result event's payload as opaque data", () => {
    const ratios = { ticker: "AAPL", current_ratio: 2.0 };
    expect(parseSSEEvent("result", JSON.stringify(ratios))).toEqual({
      type: "result",
      data: ratios,
    });
  });

  it("parses an error event", () => {
    expect(
      parseSSEEvent("error", JSON.stringify({ ticker: "AAPL", error: "boom" })),
    ).toEqual({ type: "error", ticker: "AAPL", error: "boom" });
  });

  it("rejects an unknown event type", () => {
    expect(() => parseSSEEvent("ping", "{}")).toThrow(/unknown SSE event type/);
  });
});
