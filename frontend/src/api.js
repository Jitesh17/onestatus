// Thin API client. All calls go through the Vite proxy at /api.
const base = "/api";

async function req(path, options = {}) {
  const res = await fetch(base + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    // Surface FastAPI's `detail` (e.g. the 503 "Ollama unreachable" message) when present.
    let detail = "";
    try { detail = (await res.json())?.detail || ""; } catch { /* non-JSON body */ }
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return res.status === 204 ? null : res.json();
}

// Multipart upload (audio). Do NOT set Content-Type: the browser adds the boundary.
async function upload(path, formData) {
  const res = await fetch(base + path, { method: "POST", body: formData });
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json())?.detail || ""; } catch { /* non-JSON body */ }
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  listProjects: () => req("/projects"),
  createProject: (data) => req("/projects", { method: "POST", body: JSON.stringify(data) }),
  listTasks: (projectId) => req(`/tasks${projectId ? `?project_id=${projectId}` : ""}`),
  createTask: (data) => req("/tasks", { method: "POST", body: JSON.stringify(data) }),
  listUpdates: () => req("/updates"),
  createUpdate: (data) => req("/updates", { method: "POST", body: JSON.stringify(data) }),
  extractUpdate: (data) => req("/extract", { method: "POST", body: JSON.stringify(data) }),
  transcribe: (formData) => upload("/transcribe", formData),
  dashboard: () => req("/dashboard"),
  configureDashboard: (data) => req("/dashboard/configure", { method: "POST", body: JSON.stringify(data) }),
  applyView: (config) => req("/dashboard/apply", { method: "POST", body: JSON.stringify({ config }) }),
  listViews: () => req("/views"),
  saveView: (data) => req("/views", { method: "POST", body: JSON.stringify(data) }),
  deleteView: (id) => req(`/views/${id}`, { method: "DELETE" }),
};
