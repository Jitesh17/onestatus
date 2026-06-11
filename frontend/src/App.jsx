import React, { useEffect, useRef, useState } from "react";
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
        <AiUpdateForm tasks={tasks} onDone={refresh} />
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

// ---------------------------------------------------------------------------
// AI flow (week 2-4): speak OR type a free-form update -> (week 4) transcribe via
// local Whisper -> local LLM proposes a structured draft -> human edits the
// confirmation blocks -> save through the existing POST /updates. Nothing is saved
// until "Confirm & save".
// ---------------------------------------------------------------------------
function AiUpdateForm({ tasks, onDone }) {
  const [text, setText] = useState("");
  const [language, setLanguage] = useState("en");
  const [author, setAuthor] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [draft, setDraft] = useState(null); // null = no proposal yet
  const [source, setSource] = useState("text"); // flips to "voice" when text came from audio
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const recorderRef = useRef(null);

  // Send an audio Blob/File to /transcribe and load the transcript into the textarea.
  async function sendAudio(blob) {
    setTranscribing(true); setErr("");
    try {
      const fd = new FormData();
      fd.append("file", blob, blob.name || "clip.webm");
      const r = await api.transcribe(fd);
      setText(t => (t ? t + " " : "") + r.text);
      if (r.language === "en" || r.language === "ja") setLanguage(r.language);
      setSource("voice");
    } catch (e) {
      setErr(e.message || "Transcription failed.");
    } finally {
      setTranscribing(false);
    }
  }

  async function toggleRecord() {
    if (recording) { recorderRef.current?.stop(); return; }
    setErr("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks = [];
      rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      rec.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        setRecording(false);
        sendAudio(new Blob(chunks, { type: rec.mimeType || "audio/webm" }));
      };
      recorderRef.current = rec;
      rec.start();
      setRecording(true);
    } catch (e) {
      setErr("Microphone unavailable: " + (e.message || e));
    }
  }

  function onPickFile(e) {
    const f = e.target.files?.[0];
    if (f) sendAudio(f);
    e.target.value = ""; // allow re-picking the same file
  }

  async function extract() {
    if (!text.trim()) return;
    setBusy(true); setErr("");
    try {
      const d = await api.extractUpdate({ raw_text: text, language });
      setDraft(d);
    } catch (e) {
      setErr(e.message || "Extraction failed.");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setText(""); setAuthor(""); setDraft(null); setErr(""); setSource("text");
  }

  async function confirm() {
    // The draft is lenient; the strict /updates save needs a real severity and an ISO date
    // (or null). The vague due_date stays visible in the editor but is dropped on save.
    const isISO = (s) => /^\d{4}-\d{2}-\d{2}$/.test(s || "");
    const payload = {
      task_id: draft.task_id ?? null,
      author: author || null,
      language,
      raw_text: text,
      source, // "voice" if the text came from audio, else "text"
      blockers: draft.blockers.map(b => ({ ...b, severity: b.severity || "medium", status: b.status || "open" })),
      risks: draft.risks,
      next_steps: draft.next_steps.map(n => ({ ...n, due_date: isISO(n.due_date) ? n.due_date : null })),
    };
    await api.createUpdate(payload);
    reset();
    onDone();
  }

  // Generic helpers to edit a row, add a row, or drop a row in a draft list field.
  const setField = (k, v) => setDraft(d => ({ ...d, [k]: v }));
  const editItem = (key, i, patch) =>
    setDraft(d => ({ ...d, [key]: d[key].map((it, j) => (j === i ? { ...it, ...patch } : it)) }));
  const addItem = (key, blank) => setDraft(d => ({ ...d, [key]: [...d[key], blank] }));
  const dropItem = (key, i) => setDraft(d => ({ ...d, [key]: d[key].filter((_, j) => j !== i) }));

  return (
    <div className="card" style={{ borderColor: "#1f3864" }}>
      <h2>Add update by voice or text (AI)</h2>
      <div className="row" style={{ alignItems: "center", marginBottom: 6 }}>
        <button onClick={toggleRecord} disabled={transcribing}
          style={{ marginTop: 0, background: recording ? "#c0392b" : "#1f3864" }}>
          {recording ? "■ Stop recording" : "● Record"}
        </button>
        <label style={{ margin: 0, fontWeight: 400, color: "#777" }}>
          or upload audio:&nbsp;
          <input type="file" accept="audio/*" onChange={onPickFile} disabled={transcribing}
            style={{ width: "auto", display: "inline-block", padding: 2, border: 0 }} />
        </label>
        {transcribing && <span className="muted">transcribing…</span>}
        {source === "voice" && !transcribing && <span className="tag done">from voice</span>}
      </div>
      <label>Update text (English, Japanese, or mixed) — speak above, or type/edit here</label>
      <textarea rows="3" value={text} onChange={e => setText(e.target.value)}
        placeholder="e.g. Color uniformity test rig is about 60% done, wrapping up sensor mounts by Friday." />
      <div className="row">
        <div><label>Language</label>
          <select value={language} onChange={e => setLanguage(e.target.value)}>
            <option value="en">English</option><option value="ja">Japanese</option>
          </select>
        </div>
        <div><label>Author</label><input value={author} onChange={e => setAuthor(e.target.value)} /></div>
      </div>
      <button onClick={extract} disabled={busy || !text.trim()}>
        {busy ? "Extracting..." : "Extract"}
      </button>
      {err && <p style={{ color: "#c00", marginBottom: 0 }}>{err}</p>}

      {draft && (
        <div style={{ marginTop: 16, borderTop: "1px solid #ececf0", paddingTop: 12 }}>
          <div className="row" style={{ alignItems: "center" }}>
            <h3 style={{ margin: 0, fontSize: 15 }}>Confirm the extracted update</h3>
            <span className="muted">model confidence: {Math.round((draft.confidence || 0) * 100)}%</span>
          </div>

          {draft.unknown_project &&
            <p className="tag blocked">Project not recognized. Pick the right task below, or add the project/task first.</p>}
          {draft.unknown_task && !draft.unknown_project &&
            <p className="tag blocked">Task "{draft.task}" did not match a known task. Pick it below.</p>}

          <div className="row">
            <div><label>Project (matched)</label>
              <input value={draft.project === "unknown" ? "(unknown)" : draft.project} readOnly />
            </div>
            <div><label>Task</label>
              <select value={draft.task_id ?? ""} onChange={e => setField("task_id", e.target.value ? Number(e.target.value) : null)}>
                <option value="">(no task)</option>
                {tasks.map(t => <option key={t.id} value={t.id}>{t.title}</option>)}
              </select>
            </div>
          </div>
          <div className="row">
            <div><label>Status</label>
              <select value={draft.status ?? ""} onChange={e => setField("status", e.target.value || null)}>
                <option value="">(none)</option>
                {STATUS.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div><label>Progress %</label>
              <input type="number" min="0" max="100" value={draft.progress_pct ?? ""}
                onChange={e => setField("progress_pct", e.target.value === "" ? null : Number(e.target.value))} />
            </div>
            <div><label>Period</label>
              <input value={draft.period ?? ""} onChange={e => setField("period", e.target.value || null)} />
            </div>
          </div>
          {draft.owners?.length > 0 &&
            <p className="muted">Owners detected: {draft.owners.join(", ")}</p>}

          <DraftList title="Blockers" items={draft.blockers}
            onAdd={() => addItem("blockers", { description: "", severity: "medium", owner: "", status: "open" })}
            onDrop={i => dropItem("blockers", i)}
            render={(b, i) => (
              <div className="row">
                <div style={{ flex: 3 }}><input placeholder="description" value={b.description}
                  onChange={e => editItem("blockers", i, { description: e.target.value })} /></div>
                <div><select value={b.severity ?? "medium"} onChange={e => editItem("blockers", i, { severity: e.target.value })}>
                  {SEVERITY.map(s => <option key={s}>{s}</option>)}</select></div>
                <div><input placeholder="owner" value={b.owner ?? ""} onChange={e => editItem("blockers", i, { owner: e.target.value })} /></div>
                <div><select value={b.status ?? "open"} onChange={e => editItem("blockers", i, { status: e.target.value })}>
                  <option>open</option><option>resolved</option></select></div>
              </div>
            )} />

          <DraftList title="Risks" items={draft.risks}
            onAdd={() => addItem("risks", { description: "", likelihood: "", impact: "", mitigation: "", owner: "" })}
            onDrop={i => dropItem("risks", i)}
            render={(r, i) => (
              <>
                <div className="row">
                  <div style={{ flex: 2 }}><input placeholder="description" value={r.description}
                    onChange={e => editItem("risks", i, { description: e.target.value })} /></div>
                  <div><input placeholder="likelihood" value={r.likelihood ?? ""} onChange={e => editItem("risks", i, { likelihood: e.target.value })} /></div>
                  <div><input placeholder="impact" value={r.impact ?? ""} onChange={e => editItem("risks", i, { impact: e.target.value })} /></div>
                </div>
                <div className="row">
                  <div><input placeholder="mitigation" value={r.mitigation ?? ""} onChange={e => editItem("risks", i, { mitigation: e.target.value })} /></div>
                  <div><input placeholder="owner" value={r.owner ?? ""} onChange={e => editItem("risks", i, { owner: e.target.value })} /></div>
                </div>
              </>
            )} />

          <DraftList title="Next steps" items={draft.next_steps}
            onAdd={() => addItem("next_steps", { description: "", owner: "", due_date: "" })}
            onDrop={i => dropItem("next_steps", i)}
            render={(n, i) => (
              <div className="row">
                <div style={{ flex: 3 }}><input placeholder="description" value={n.description}
                  onChange={e => editItem("next_steps", i, { description: e.target.value })} /></div>
                <div><input placeholder="owner" value={n.owner ?? ""} onChange={e => editItem("next_steps", i, { owner: e.target.value })} /></div>
                <div><input placeholder="due (YYYY-MM-DD)" value={n.due_date ?? ""} onChange={e => editItem("next_steps", i, { due_date: e.target.value || null })} /></div>
              </div>
            )} />

          <div className="row" style={{ marginTop: 8 }}>
            <button className="secondary" onClick={confirm}>Confirm &amp; save</button>
            <button onClick={() => setDraft(null)} style={{ background: "#888" }}>Discard</button>
          </div>
        </div>
      )}
    </div>
  );
}

function DraftList({ title, items, render, onAdd, onDrop }) {
  return (
    <div style={{ marginTop: 10 }}>
      <label>{title}</label>
      {items.length === 0 && <p className="muted" style={{ margin: "2px 0" }}>none</p>}
      {items.map((it, i) => (
        <div key={i} style={{ display: "flex", gap: 6, alignItems: "flex-start", marginBottom: 6 }}>
          <div style={{ flex: 1 }}>{render(it, i)}</div>
          <button onClick={() => onDrop(i)} style={{ background: "#c0392b", marginTop: 0, padding: "7px 10px" }}>×</button>
        </div>
      ))}
      <button onClick={onAdd} style={{ background: "#eee", color: "#333", marginTop: 4, padding: "5px 10px" }}>+ add</button>
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
