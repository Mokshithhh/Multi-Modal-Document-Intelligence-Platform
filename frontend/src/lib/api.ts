export type User = { id: string; email: string; created_at: string };

export type DocumentRecord = {
  id: string;
  filename: string;
  file_size: number;
  file_type: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  error_message: string | null;
  created_at: string;
};

export type Citation = {
  document_id: string;
  filename: string;
  page_number: number;
  snippet_text: string;
};

export type Metrics = {
  documents_total: number;
  documents_processing: number;
  documents_completed: number;
  documents_failed: number;
  error_rate: number;
  messages_total: number;
  estimated_tokens: number;
  retrieval_runs: number;
  citation_count: number;
};

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window === "undefined" ? null : localStorage.getItem("vanco.access_token");
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_URL}${path}`, { ...options, headers, cache: "no-store" });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
