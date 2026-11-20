import type { ChatEvent, DuelEvent } from "./types";

const TOKEN_KEY = "jc_token";
const USER_KEY = "jc_user";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getStoredUser<T>(): T | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function setStoredUser(user: unknown) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export class ApiError extends Error {
  code: number;
  status: number;

  constructor(message: string, code: number, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

interface Envelope<T> {
  code: number;
  data: T;
  message: string;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const isForm = init.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isForm ? {} : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((init.headers as Record<string, string>) || {}),
  };

  let res: Response;
  try {
    res = await fetch(`/api${path}`, { ...init, headers });
  } catch {
    throw new ApiError("网络异常，请确认后端已启动", -1, 0);
  }

  let payload: Envelope<T> | null = null;
  try {
    payload = (await res.json()) as Envelope<T>;
  } catch {
    payload = null;
  }

  if (res.status === 401) {
    clearAuth();
    window.dispatchEvent(new Event("jc:unauthorized"));
  }

  if (!res.ok || payload == null || payload.code !== 0) {
    throw new ApiError(payload?.message || `请求失败（${res.status}）`, payload?.code ?? res.status, res.status);
  }
  return payload.data;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body === undefined ? undefined : JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
};

export async function streamChat(
  sessionId: number,
  content: string,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await openStream(`/api/agent/sessions/${sessionId}/chat`, { content }, signal);
  await readEventStream<ChatEvent>(res, onEvent);
}

export async function streamDuel(
  jobId: number,
  applicationId: number,
  onEvent: (event: DuelEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await openStream("/api/agent/duel", { job_id: jobId, application_id: applicationId }, signal);
  await readEventStream<DuelEvent>(res, onEvent);
}

async function openStream(path: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  const token = getToken();
  const res = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  });

  if (res.status === 401) {
    clearAuth();
    window.dispatchEvent(new Event("jc:unauthorized"));
  }

  if (!res.ok || !res.body) {
    let message = `请求失败（${res.status}）`;
    try {
      const payload = await res.json();
      message = payload.message || message;
    } catch {
      /* ignore */
    }
    throw new ApiError(message, res.status, res.status);
  }
  return res;
}

async function readEventStream<T>(res: Response, onEvent: (event: T) => void): Promise<void> {
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const consume = (block: string) => {
    const trimmed = block.trim();
    if (!trimmed) return;
    const line = trimmed.split(/\r?\n/).find((l) => l.startsWith("data:"));
    if (!line) return;
    try {
      onEvent(JSON.parse(line.slice(5).trim()) as T);
    } catch {
      /* 忽略无法解析的片段 */
    }
  };

  const drain = () => {
    for (;;) {
      const match = buffer.match(/\r?\n\r?\n/);
      if (!match || match.index === undefined) return;
      const block = buffer.slice(0, match.index);
      buffer = buffer.slice(match.index + match[0].length);
      consume(block);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    drain();
  }
  // 处理流结束时没有尾随空行的最后一条事件
  buffer += decoder.decode();
  if (buffer.trim()) consume(buffer);
}
