import { useCallback, useEffect, useRef, useState } from "react";
import { streamPipeline } from "../services/api";
import type { Pipeline, StreamResult } from "../types";

type Status = "idle" | "connecting" | "running" | "done" | "error";

export function useAnalysisStream(): {
  status: Status;
  data: StreamResult | null;
  error: string | null;
  run: (pipeline: Pipeline, ticker: string) => void;
} {
  const [status, setStatus] = useState<Status>("idle");
  const [data, setData] = useState<StreamResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => () => cleanupRef.current?.(), []);

  const run = useCallback((pipeline: Pipeline, ticker: string) => {
    cleanupRef.current?.();
    setStatus("connecting");
    setData(null);
    setError(null);

    cleanupRef.current = streamPipeline(pipeline, ticker, {
      onEvent: (event) => {
        if (event.type === "started") {
          setStatus("running");
        } else if (event.type === "result") {
          setData(event.data);
          setStatus("done");
        } else {
          setError(event.error);
          setStatus("error");
        }
      },
      onConnectionError: () => {
        setError("Lost connection to the analysis server.");
        setStatus("error");
      },
    });
  }, []);

  return { status, data, error, run };
}
