import type {
  AnalysisRequest,
  AnalysisResult,
  AnalysisStage,
  ApiError,
  Capabilities,
  HistoryPage,
} from "@/lib/types";

// Empty by default, so requests stay on the origin serving the page and are
// forwarded to the API by the rewrite in next.config.mjs. Set
// NEXT_PUBLIC_API_URL only to call an API on a different host, which then has
// to allow this origin in CORS_ORIGINS.
const BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

const API = `${BASE_URL}/api/v1`;

export class ApiRequestError extends Error {
  readonly code: string;
  readonly requestId?: string;

  constructor(error: ApiError) {
    super(error.message);
    this.name = "ApiRequestError";
    this.code = error.code;
    this.requestId = error.request_id;
  }
}

async function toApiError(response: Response): Promise<ApiRequestError> {
  try {
    const body = (await response.json()) as { error?: ApiError };
    if (body.error) return new ApiRequestError(body.error);
  } catch {
    // Fall through to the generic message below.
  }
  return new ApiRequestError({
    code: "http_error",
    message: `Request failed with status ${response.status}.`,
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}

export function getCapabilities(): Promise<Capabilities> {
  return request<Capabilities>("/capabilities");
}

export function getHistory(sessionId: string, limit = 20): Promise<HistoryPage> {
  const params = new URLSearchParams({
    session_id: sessionId,
    limit: String(limit),
  });
  return request<HistoryPage>(`/history?${params.toString()}`);
}

export function getAnalysis(id: string): Promise<AnalysisResult> {
  return request<AnalysisResult>(`/analyses/${encodeURIComponent(id)}`);
}

export interface StreamHandlers {
  onStage: (stage: AnalysisStage) => void;
  onResult: (result: AnalysisResult) => void;
  onError: (error: ApiRequestError) => void;
  signal?: AbortSignal;
}

/**
 * Consumes the Server-Sent Event stream from POST /analyses/stream.
 *
 * `EventSource` cannot issue a POST, so the stream is read directly off the
 * response body and parsed here.
 */
export async function streamAnalysis(
  payload: AnalysisRequest,
  handlers: StreamHandlers,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API}/analyses/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: handlers.signal,
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") return;
    handlers.onError(
      new ApiRequestError({
        code: "network_error",
        message: "Could not reach the analysis service.",
      }),
    );
    return;
  }

  if (!response.ok || !response.body) {
    handlers.onError(await toApiError(response));
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let separator = buffer.indexOf("\n\n");
      while (separator !== -1) {
        dispatch(buffer.slice(0, separator), handlers);
        buffer = buffer.slice(separator + 2);
        separator = buffer.indexOf("\n\n");
      }
    }
    if (buffer.trim()) dispatch(buffer, handlers);
  } catch (error) {
    if ((error as Error).name === "AbortError") return;
    handlers.onError(
      new ApiRequestError({
        code: "stream_error",
        message: "The connection dropped while the analysis was running.",
      }),
    );
  } finally {
    reader.releaseLock();
  }
}

function dispatch(chunk: string, handlers: StreamHandlers): void {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of chunk.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return;

  let payload: unknown;
  try {
    payload = JSON.parse(dataLines.join("\n"));
  } catch {
    return;
  }

  if (event === "stage") handlers.onStage(payload as AnalysisStage);
  else if (event === "result") handlers.onResult(payload as AnalysisResult);
  else if (event === "error") handlers.onError(new ApiRequestError(payload as ApiError));
}
