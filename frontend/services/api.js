const API_BASE =
  import.meta.env.VITE_API_BASE ??
  (import.meta.env.DEV ? "" : "http://127.0.0.1:9090");

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return data;
}

export const health = () => request("/healthz");
export const listProviders = () => request("/api/providers");
export const listCatalog = () => request("/api/catalog");
export const getCatalogItem = (id) => request(`/api/catalog/${encodeURIComponent(id)}`);
export const chat = (prompt, provider, model) =>
  request("/api/chat", {
    method: "POST",
    body: JSON.stringify({ prompt, provider, model }),
  });
export const generateBpmn = (process) =>
  request("/api/generate-bpmn", { method: "POST", body: JSON.stringify({ process }) });
export const validate = (process) =>
  request("/api/validate", { method: "POST", body: JSON.stringify({ process }) });
export const deploy = (processId, bpmn) =>
  request("/api/deploy", {
    method: "POST",
    body: JSON.stringify({ process_id: processId, bpmn }),
  });
