import {supabase} from "./supabase";

export type User = {id: string; email: string; name: string; role: string};
export type Document = {id: string; filename: string; content_type: string; status: "processing" | "ready" | "failed"; page_count: number | null; error: string | null; metadata_: Record<string, string>; created_at: string};
export type Citation = {document_id: string; filename: string; chunk_id: string; page_number: number | null; excerpt: string; relevance: number};
export type Result = {id: string; answer: string; citations: Citation[]; model: string};
export type AuditEvent = {id: string; action: string; resource_type: string; resource_id: string | null; detail: Record<string, unknown>; created_at: string};

const API = import.meta.env.VITE_API_URL || "";

async function accessToken(refresh = false): Promise<string | null> {
  if (refresh) {
    const {data, error} = await supabase.auth.refreshSession();
    if (error) return null;
    return data.session?.access_token || null;
  }
  const {data} = await supabase.auth.getSession();
  return data.session?.access_token || null;
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const token = await accessToken();
  if (!token) throw new Error("Your session has expired. Please sign in again.");
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API}${path}`, {...init, headers});
  if (response.status === 401 && retry) {
    const refreshed = await accessToken(true);
    if (refreshed) return request<T>(path, init, false);
    await supabase.auth.signOut({scope: "local"});
  }
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `Request failed (${response.status})`); }
  return response.status === 204 ? undefined as T : response.json();
}

export const auth = {
  signIn: async (email: string, password: string) => {
    const {data, error} = await supabase.auth.signInWithPassword({email, password});
    if (error) throw error;
    return data.session;
  },
  signUp: async (name: string, email: string, password: string) => {
    const {data, error} = await supabase.auth.signUp({email, password, options: {data: {full_name: name, name}}});
    if (error) throw error;
    return {session: data.session, needsConfirmation: !data.session};
  },
  signInAsGuest: async () => {
    const {data, error} = await supabase.auth.signInAnonymously();
    if (error) throw error;
    return data.session;
  },
  signOut: async () => { const {error} = await supabase.auth.signOut(); if (error) throw error; }
};

export const api = {
  me: () => request<User>("/api/auth/me"),
  documents: () => request<Document[]>("/api/documents"),
  upload: (file: File, portfolio: string) => { const body = new FormData(); body.append("file", file); if (portfolio) body.append("portfolio", portfolio); return request<Document>("/api/documents", {method: "POST", body}); },
  removeDocument: (id: string) => request<void>(`/api/documents/${id}`, {method: "DELETE"}),
  generate: (query: string, mode: string, document_ids: string[]) => request<Result>("/api/generate", {method: "POST", body: JSON.stringify({query, mode, document_ids, top_k: 6})}),
  audit: () => request<AuditEvent[]>("/api/audit")
};
