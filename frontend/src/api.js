// Thin API client. All calls go through the Vite proxy at /api.
const base = "/api";

async function req(path, options = {}) {
  const res = await fetch(base + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.status === 204 ? null : res.json();
}

export const api = {
  listProjects: () => req("/projects"),
  createProject: (data) => req("/projects", { method: "POST", body: JSON.stringify(data) }),
  listTasks: (projectId) => req(`/tasks${projectId ? `?project_id=${projectId}` : ""}`),
  createTask: (data) => req("/tasks", { method: "POST", body: JSON.stringify(data) }),
  listUpdates: () => req("/updates"),
  createUpdate: (data) => req("/updates", { method: "POST", body: JSON.stringify(data) }),
};
