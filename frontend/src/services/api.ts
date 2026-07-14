import type { Pipeline, SSEEvent, StreamResult } from "../types";

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8001";

const PIPELINE_PATH: Record<Pipeline, string> = {
  fundamentals: "fundamentals",
  analysis: "analysis",
  report: "report",
};

/** Pure parse of one named SSE event's raw data payload -- kept side-effect-free so it's
 * unit-testable without a DOM/EventSource. Mirrors the three event names the backend's
 * `_sse_stream` (app/routers/streaming.py) actually emits. */
export function parseSSEEvent(eventType: string, rawData: string): SSEEvent {
  const payload = JSON.parse(rawData) as Record<string, unknown>;
  switch (eventType) {
    case "started":
      return { type: "started", ticker: payload.ticker as string };
    case "result":
      return { type: "result", data: payload as unknown as StreamResult };
    case "error":
      return { type: "error", ticker: payload.ticker as string, error: payload.error as string };
    default:
      throw new Error(`unknown SSE event type: ${eventType}`);
  }
}

export interface StreamHandlers {
  onEvent: (event: SSEEvent) => void;
  onConnectionError: () => void;
}

/** Opens the ticker SSE stream for the given pipeline and wires callbacks; returns a
 * cleanup function that closes the connection. */
export function streamPipeline(pipeline: Pipeline, ticker: string, handlers: StreamHandlers): () => void {
  const url = `${API_BASE_URL}/${PIPELINE_PATH[pipeline]}/${encodeURIComponent(ticker)}/stream`;
  const source = new EventSource(url);

  for (const eventType of ["started", "result", "error"] as const) {
    source.addEventListener(eventType, (event: MessageEvent<string>) => {
      handlers.onEvent(parseSSEEvent(eventType, event.data));
      if (eventType !== "started") {
        source.close();
      }
    });
  }
  source.onerror = () => {
    handlers.onConnectionError();
    source.close();
  };

  return () => source.close();
}
