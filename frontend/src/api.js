// Thin API client. All calls go through the Vite proxy at /api.
// The session cookie rides along automatically (fetch sends same-origin
// cookies by default). When any call comes back 401, api.onUnauthorized
// fires so the app can drop to the login screen; the login call itself is
// excluded since a wrong password is handled inline on the form.
const base = "/api";

async function req(path, options = {}) {
  const res = await fetch(base + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/auth/login")) api.onUnauthorized?.();
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
    if (res.status === 401) api.onUnauthorized?.();
    let detail = "";
    try { detail = (await res.json())?.detail || ""; } catch { /* non-JSON body */ }
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  onUnauthorized: null, // assigned by App; called on any 401 outside login
  login: (data) => req("/auth/login", { method: "POST", body: JSON.stringify(data) }),
  logout: () => req("/auth/logout", { method: "POST" }),
  me: () => req("/auth/me"),
  changePassword: (data) => req("/auth/me/password", { method: "PUT", body: JSON.stringify(data) }),
  listUsers: () => req("/auth/users"),
  createUser: (data) => req("/auth/users", { method: "POST", body: JSON.stringify(data) }),
  updateUser: (id, data) => req(`/auth/users/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  setUserPassword: (id, data) => req(`/auth/users/${id}/password`, { method: "PUT", body: JSON.stringify(data) }),
  deleteUser: (id) => req(`/auth/users/${id}`, { method: "DELETE" }),
  listPeople: () => req("/people"),
  createPerson: (data) => req("/people", { method: "POST", body: JSON.stringify(data) }),
  updatePerson: (id, data) => req(`/people/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deletePerson: (id) => req(`/people/${id}`, { method: "DELETE" }),
  listProjects: () => req("/projects"),
  createProject: (data) => req("/projects", { method: "POST", body: JSON.stringify(data) }),
  listTasks: (projectId) => req(`/tasks${projectId ? `?project_id=${projectId}` : ""}`),
  createTask: (data) => req("/tasks", { method: "POST", body: JSON.stringify(data) }),
  listUpdates: () => req("/updates"),
  createUpdate: (data) => req("/updates", { method: "POST", body: JSON.stringify(data) }),
  translateUpdate: (id, target) => req(`/updates/${id}/translate`, { method: "POST", body: JSON.stringify({ target }) }),
  extractUpdate: (data) => req("/extract", { method: "POST", body: JSON.stringify(data) }),
  transcribe: (formData) => upload("/transcribe", formData),
  dashboard: () => req("/dashboard"),
  configureDashboard: (data) => req("/dashboard/configure", { method: "POST", body: JSON.stringify(data) }),
  applyView: (config) => req("/dashboard/apply", { method: "POST", body: JSON.stringify({ config }) }),
  listPresets: () => req("/dashboard/presets"),
  getSettings: () => req("/settings"),
  putSettings: (data) => req("/settings", { method: "PUT", body: JSON.stringify(data) }),
  listModels: () => req("/settings/models"),
  listViews: () => req("/views"),
  saveView: (data) => req("/views", { method: "POST", body: JSON.stringify(data) }),
  deleteView: (id) => req(`/views/${id}`, { method: "DELETE" }),
};
