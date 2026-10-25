/** Dunne API-client. Alle businesslogica zit in de API, niet hier. */

export class ApiError extends Error {
  /** `detail` is de ruwe foutinhoud; publiceren levert daar {message, issues, conflict} in. */
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { credentials: "same-origin", ...init });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const raw = body.detail;
    const message =
      typeof raw === "string"
        ? raw
        : raw && typeof raw === "object" && "message" in raw && typeof raw.message === "string"
          ? raw.message
          : JSON.stringify(raw ?? response.statusText);
    throw new ApiError(response.status, message, raw);
  }
  return response.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown = {}) => request<T>(path, json("POST", body)),
  put: <T>(path: string, body: unknown) => request<T>(path, json("PUT", body)),
  patch: <T>(path: string, body: unknown) => request<T>(path, json("PATCH", body)),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
};
