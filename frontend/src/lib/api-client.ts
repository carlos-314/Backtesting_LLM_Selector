/**
 * Cliente HTTP del backend (ADR-0007 Bearer JWT en memoria).
 *
 * Política:
 * - Bearer leído de `getAccessToken()` (inyectado por `app/session/`).
 * - El backend devuelve siempre el shape uniforme `{error:{code,message,details}}`
 *   (F2 §6.1); el cliente lo traduce a `ApiError`.
 * - 401 dispara `onUnauthorized` (limpiar sesión global — F3 §6.3 C5).
 */
import { ApiError, type ApiErrorBody } from "@/lib/api-error";

let getToken: () => string | null = () => null;
let onUnauthorized: () => void = () => {};

/** Llama al boot de la app para inyectar el accessor del token (en memoria). */
export function configureAuth(
  provider: () => string | null,
  onAuthError?: () => void,
) {
  getToken = provider;
  if (onAuthError) onUnauthorized = onAuthError;
}

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

interface RequestOptions extends Omit<RequestInit, "body" | "method"> {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | undefined | null>;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, query, headers, ...rest } = options;
  const url = new URL(BASE + path, window.location.origin);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
    }
  }

  const init: RequestInit = {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(headers ?? {}),
    },
    ...rest,
  };
  const token = getToken();
  if (token) {
    (init.headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  const res = await fetch(url.toString(), init);

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const parsed = text ? safeJson(text) : null;

  if (!res.ok) {
    if (res.status === 401) onUnauthorized();
    const body = parsed as ApiErrorBody | null;
    if (body && body.error) {
      throw new ApiError(
        res.status,
        body.error.code,
        body.error.message,
        body.error.details ?? null,
      );
    }
    throw new ApiError(res.status, "unknown_error", `HTTP ${res.status}`, null);
  }
  return parsed as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
