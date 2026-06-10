import React, { useEffect, useState } from "react";
import { api } from "./api.js";

const STATUS = ["not_started", "in_progress", "blocked", "done"];
const SEVERITY = ["low", "medium", "high"];

export default function App() {
  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [updates, setUpdates] = useState([]);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const [p, t, u] = await Promise.all([api.listProjects(), api.listTasks(), api.listUpdates()]);
      setProjects(p); setTasks(t); setUpdates(u); setError("");
    } catch (e) {
      setError("Cannot reach the API. Is the backend running on port 8000?");
    }
  }
  useEffect(() => { refresh(); }, []);

  return (
    <>
      <div className="bar"><b>Sony OneStatus</b> &nbsp;·&nbsp; Manual entry (week 1, no AI)</div>
      <div className="wrap">
        {error && <div className="card" style={{ borderColor: "#c00", color: "#c00" }}>{error}</div>}
        <ProjectForm onDone={refresh} />
        <TaskForm projects={projects} onDone={refresh} />
        <UpdateForm tasks={tasks} onDone={refresh} />
        <UpdatesTable updates={updates} tasks={tasks} />
      </div>
    </>
  );
}

function ProjectForm({ onDone }) {
  const [name, setName] = useState("");
  const [owner, setOwner] = useState("");
  async function submit() {
    if (!name.trim()) return;
    await api.createProject({ name, owner: owner || null });
    setName(""); setOwner(""); onDone();
  }
  return (
    <div className="card">
      <h2>Add project</h2>
      <div className="row">
        <div><label>Name</label><input value={name} onChange={e => setName(e.target.value)} /></div>
        <div><label>Owner</label><input value={owner} onChange={e => setOwner(e.target.value)} /></div>
      </div>
      <button onClick={submit}>Save project</button>
    </div>
  );
}

function TaskForm({ projects, onDone }) {
  const [form, setForm] = useState({ project_id: "", title: "", assignee: "", status: "not_started", progress_pct: 0 });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  async function submit() {
    if (!form.project_id || !form.title.trim()) return;
    await api.createTask({ ...form, project_id: Number(form.project_id), progress_pct: Number(form.progress_pct) });
    setForm({ project_id: "", title: "", assignee: "", status: "not_started", progress_pct: 0 }); onDone();
  }
  return (
    <div className="card">
      <h2>Add task</h2>
      <div className="row">
        <div><label>Project</label>
          <select value={form.project_id} onChange={e => set("project_id", e.target.value)}>
            <option value="">Select...</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
        <div><label>Title</label><input value={form.title} onChange={e => set("title", e.target.value)} /></div>
        <div><label>Assignee</label><input value={form.assignee} onChange={e => set("assignee", e.target.value)} /></div>
      </div>
      <div className="row">
        <div><label>Status</label>
          <select value={form.status} onChange={e => set("status", e.target.value)}>
            {STATUS.map(s => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div><label>Progress %</label><input type="number" min="0" max="100" value={form.progress_pct} onChange={e => set("progress_pct", e.target.value)} /></div>
      </div>
      <button onClick={submit}>Save task</button>
    </div>
  );
}

function UpdateForm({ tasks, onDone }) {
  const [form, setForm] = useState({ task_id: "", author: "", language: "en", raw_text: "" });
  const [blocker, setBlocker] = useState({ description: "", severity: "medium" });
  const [nextStep, setNextStep] = useState({ description: "", owner: "" });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  async function submit() {
    if (!form.task_id) return;
    const payload = {
      task_id: Number(form.task_id),
      author: form.author || null,
      language: form.language,
      raw_text: form.raw_text || null,
      source: "text",
      blockers: blocker.description.trim() ? [blocker] : [],
      next_steps: nextStep.description.trim() ? [nextStep] : [],
    };
    await api.createUpdate(payload);
    setForm({ task_id: "", author: "", language: "en", raw_text: "" });
    setBlocker({ description: "", severity: "medium" });
    setNextStep({ description: "", owner: "" });
    onDone();
  }

  return (
    <div className="card">
      <h2>Add status update</h2>
      <div className="row">
        <div><label>Task</label>
          <select value={form.task_id} onChange={e => set("task_id", e.target.value)}>
            <option value="">Select...</option>
            {tasks.map(t => <option key={t.id} value={t.id}>{t.title}</option>)}
          </select>
        </div>
        <div><label>Author</label><input value={form.author} onChange={e => set("author", e.target.value)} /></div>
        <div><label>Language</label>
          <select value={form.language} onChange={e => set("language", e.target.value)}>
            <option value="en">English</option><option value="ja">Japanese</option>
          </select>
        </div>
      </div>
      <label>Update text</label>
      <textarea rows="2" value={form.raw_text} onChange={e => set("raw_text", e.target.value)} />
      <div className="row">
        <div><label>Blocker (optional)</label><input value={blocker.description} onChange={e => setBlocker(b => ({ ...b, description: e.target.value }))} /></div>
        <div><label>Severity</label>
          <select value={blocker.severity} onChange={e => setBlocker(b => ({ ...b, severity: e.target.value }))}>
            {SEVERITY.map(s => <option key={s}>{s}</option>)}
          </select>
        </div>
      </div>
      <div className="row">
        <div><label>Next step (optional)</label><input value={nextStep.description} onChange={e => setNextStep(n => ({ ...n, description: e.target.value }))} /></div>
        <div><label>Owner</label><input value={nextStep.owner} onChange={e => setNextStep(n => ({ ...n, owner: e.target.value }))} /></div>
      </div>
      <button className="secondary" onClick={submit}>Save update</button>
    </div>
  );
}

function UpdatesTable({ updates, tasks }) {
  const taskTitle = (id) => tasks.find(t => t.id === id)?.title || "(no task)";
  return (
    <div className="card">
      <h2>Recent updates</h2>
      {updates.length === 0 ? <p className="muted">No updates yet. Add one above.</p> : (
        <table>
          <thead><tr><th>When</th><th>Task</th><th>Author</th><th>Lang</th><th>Text</th><th>Blockers</th><th>Next steps</th></tr></thead>
          <tbody>
            {updates.map(u => (
              <tr key={u.id}>
                <td className="muted">{new Date(u.created_at).toLocaleString()}</td>
                <td>{taskTitle(u.task_id)}</td>
                <td>{u.author || "-"}</td>
                <td>{u.language}</td>
                <td>{u.raw_text || "-"}</td>
                <td>{u.blockers.map(b => <span key={b.id} className={`tag ${b.severity === "high" ? "blocked" : ""}`}>{b.description} ({b.severity})</span>)}</td>
                <td>{u.next_steps.map(n => <span key={n.id} className="tag">{n.description}{n.owner ? ` · ${n.owner}` : ""}</span>)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
