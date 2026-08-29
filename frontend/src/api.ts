export type User = {id: string; email: string; name: string; role: string};
export type Document = {id: string; filename: string; content_type: string; status: "processing" | "ready" | "failed"; page_count: number | null; error: string | null; metadata_: Record<string, string>; created_at: string};
export type Citation = {document_id: string; filename: string; chunk_id: string; page_number: number | null; excerpt: string; relevance: number};
export type Result = {id: string; answer: string; citations: Citation[]; model: string};
export type AuditEvent = {id: string; action: string; resource_type: string; resource_id: string | null; detail: Record<string, unknown>; created_at: string};

const API = import.meta.env.VITE_API_URL || "";
const tokenKey = "finsight_access_token";
const refreshKey = "finsight_refresh_token";

export const session = {
  get token() { return sessionStorage.getItem(tokenKey); },
  set(access: string, refresh: string) { sessionStorage.setItem(tokenKey, access); localStorage.setItem(refreshKey, refresh); },
  clear() { sessionStorage.removeItem(tokenKey); localStorage.removeItem(refreshKey); }
};

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (session.token) headers.set("Authorization", `Bearer ${session.token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API}${path}`, {...init, headers});
  if (response.status === 401 && retry && localStorage.getItem(refreshKey)) {
    const refreshed = await fetch(`${API}/api/auth/refresh`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({refresh_token: localStorage.getItem(refreshKey)})});
    if (refreshed.ok) { const pair = await refreshed.json(); session.set(pair.access_token, pair.refresh_token); return request<T>(path, init, false); }
    session.clear();
  }
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `Request failed (${response.status})`); }
  return response.status === 204 ? undefined as T : response.json();
}

export const api = {
  login: async (email: string, password: string) => { const body = new URLSearchParams({username: email, password}); const pair = await request<{access_token: string; refresh_token: string}>("/api/auth/login", {method: "POST", body}); session.set(pair.access_token, pair.refresh_token); return pair; },
  register: (name: string, email: string, password: string) => request<User>("/api/auth/register", {method: "POST", body: JSON.stringify({name, email, password})}),
  me: () => request<User>("/api/auth/me"),
  documents: () => request<Document[]>("/api/documents"),
  upload: (file: File, portfolio: string) => { const body = new FormData(); body.append("file", file); if (portfolio) body.append("portfolio", portfolio); return request<Document>("/api/documents", {method: "POST", body}); },
  removeDocument: (id: string) => request<void>(`/api/documents/${id}`, {method: "DELETE"}),
  generate: (query: string, mode: string, document_ids: string[]) => request<Result>("/api/generate", {method: "POST", body: JSON.stringify({query, mode, document_ids, top_k: 6})}),
  audit: () => request<AuditEvent[]>("/api/audit")
};
