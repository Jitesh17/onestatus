import React, { useEffect, useRef, useState } from "react";
import { api } from "./api.js";

const STATUS = ["not_started", "in_progress", "blocked", "done"];
const SEVERITY = ["low", "medium", "high"];
const ROLE_ORDER = { member: 0, manager: 1, admin: 2 };
const isManagerUp = (me) => !!me && ROLE_ORDER[me.role] >= ROLE_ORDER.manager;

export default function App() {
  const [me, setMe] = useState(undefined); // undefined = checking, null = logged out
  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [updates, setUpdates] = useState([]);
  const [people, setPeople] = useState([]);
  const [error, setError] = useState("");
  const [view, setView] = useState("dashboard");
  const [dashTick, setDashTick] = useState(0); // bump to refetch the dashboard after a save
  const [theme, setTheme] = useState(() => localStorage.getItem("onestatus.theme") || "light");
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState(null); // backs the header provider badge

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("onestatus.theme", theme);
  }, [theme]);

  // Session gate: any 401 anywhere drops back to the login screen.
  useEffect(() => {
    api.onUnauthorized = () => setMe(null);
    api.me().then(setMe).catch(() => setMe(null));
    return () => { api.onUnauthorized = null; };
  }, []);

  async function refresh() {
    try {
      const [p, t, u] = await Promise.all([api.listProjects(), api.listTasks(), api.listUpdates()]);
      setProjects(p); setTasks(t); setUpdates(u); setError("");
    } catch (e) {
      setError("Cannot reach the API. Is the backend running?");
    }
    setDashTick(x => x + 1);
  }
  useEffect(() => {
    if (!me) return;
    refresh();
    api.getSettings().then(setSettings).catch(() => { /* badge simply hidden */ });
    api.listPeople().then(setPeople).catch(() => { /* author dropdown simply empty */ });
  }, [me?.id]);

  async function logout() {
    try { await api.logout(); } catch { /* session may already be gone */ }
    setMe(null); setView("dashboard"); setShowSettings(false);
  }

  if (me === undefined) return null; // checking the session; avoid a login flash

  if (me === null) {
    return (
      <>
        <div className="bar" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span><b>OneStatus</b> &nbsp;·&nbsp; Voice-first bilingual status</span>
          <span className="tabs">
            <button className="themetoggle" title="Switch theme"
              onClick={() => setTheme(t => (t === "light" ? "dark" : "light"))}>
              {theme === "light" ? "🌙" : "☀️"}
            </button>
          </span>
        </div>
        <div className="wrap">
          <LoginPage onLogin={setMe} />
        </div>
      </>
    );
  }

  const admin = me.role === "admin";
  return (
    <>
      <div className="bar" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span><b>OneStatus</b> &nbsp;·&nbsp; Voice-first bilingual status</span>
        <span className="tabs">
          <button className={view === "dashboard" ? "on" : ""} onClick={() => setView("dashboard")}>Dashboard</button>
          <button className={view === "capture" ? "on" : ""} onClick={() => setView("capture")}>Capture</button>
          {admin && (
            <button className={view === "admin" ? "on" : ""} onClick={() => setView("admin")}>Admin</button>
          )}
          {settings && (
            <span className={"provbadge" + (settings.llm_provider === "ollama" ? "" : " cloud")}
              title={settings.llm_provider === "ollama" ? "Running on the local model" : "Using a cloud API"}>
              {settings.llm_provider === "ollama" ? "local" : "cloud"}: {settings.llm_model}
            </span>
          )}
          <span className="provbadge" title={`Logged in as ${me.username} (${me.role})`}>
            {me.author} · {me.role}
          </span>
          {admin && (
            <button className="themetoggle" title="Settings" onClick={() => setShowSettings(s => !s)}>⚙️</button>
          )}
          <button className="themetoggle" title="Switch theme"
            onClick={() => setTheme(t => (t === "light" ? "dark" : "light"))}>
            {theme === "light" ? "🌙" : "☀️"}
          </button>
          <button className="themetoggle" title="Log out" onClick={logout}>Log out</button>
        </span>
      </div>
      <div className="wrap">
        {error && <div className="card" style={{ borderColor: "var(--danger)", color: "var(--danger)" }}>{error}</div>}
        {showSettings && (
          <SettingsPanel onSaved={setSettings} onClose={() => setShowSettings(false)} />
        )}
        {view === "dashboard" && <Dashboard tick={dashTick} me={me} />}
        {view === "capture" && (
          <>
            <AiUpdateForm tasks={tasks} onDone={refresh} me={me} people={people} />
            {isManagerUp(me) && <ProjectForm onDone={refresh} />}
            {isManagerUp(me) && <TaskForm projects={projects} onDone={refresh} />}
            <UpdateForm tasks={tasks} onDone={refresh} me={me} people={people} />
            <UpdatesTable updates={updates} tasks={tasks} />
          </>
        )}
        {view === "admin" && admin && (
          <AdminPanel me={me} people={people} onPeopleChanged={() => api.listPeople().then(setPeople).catch(() => {})} />
        )}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Login (auth sprint). The app is unusable until the backend confirms a session;
// any later 401 lands back here via api.onUnauthorized.
// ---------------------------------------------------------------------------
export function LoginPage({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setBusy(true); setErr("");
    try {
      onLogin(await api.login({ username: username.trim(), password }));
    } catch (e2) {
      setErr(e2.message || "Login failed.");
      setBusy(false);
    }
  }

  return (
    <form className="card" style={{ maxWidth: 380, margin: "60px auto" }} onSubmit={submit}>
      <h2 style={{ marginTop: 0 }}>Log in</h2>
      <label htmlFor="login-username">Username</label>
      <input id="login-username" value={username} onChange={e => setUsername(e.target.value)}
        autoFocus autoComplete="username" />
      <label htmlFor="login-password">Password</label>
      <input id="login-password" type="password" value={password} onChange={e => setPassword(e.target.value)}
        autoComplete="current-password" />
      <button type="submit" disabled={busy || !username.trim() || !password}>
        {busy ? "Logging in…" : "Log in"}
      </button>
      {err && <p style={{ color: "var(--danger)", marginBottom: 0 }}>{err}</p>}
      <p className="muted" style={{ marginBottom: 0 }}>No account? Ask an admin to create one.</p>
    </form>
  );
}

// Author control on the capture forms. Members always post as themselves (the
// server enforces it); manager and admin can pick a roster name or type one.
function AuthorField({ me, people, value, onChange }) {
  if (!isManagerUp(me)) {
    return (
      <div><label>Author</label>
        <input value={me?.author || ""} readOnly title="Updates are posted under your name" />
      </div>
    );
  }
  return (
    <div><label>Author (blank = you)</label>
      <input list="people-names" value={value} onChange={e => onChange(e.target.value)}
        placeholder={me.author} />
      <datalist id="people-names">
        {people.map(p => <option key={p.id} value={p.name} />)}
      </datalist>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Admin tab (auth sprint): manage login accounts and the org roster.
// ---------------------------------------------------------------------------
export function AdminPanel({ me, people, onPeopleChanged }) {
  return (
    <>
      <UsersPanel me={me} people={people} />
      <PeoplePanel people={people} onChanged={onPeopleChanged} />
    </>
  );
}

function UsersPanel({ me, people }) {
  const [users, setUsers] = useState([]);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ username: "", password: "", role: "member", person_id: "" });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  async function refresh() {
    try { setUsers(await api.listUsers()); setErr(""); }
    catch (e) { setErr(e.message || "Could not load users."); }
  }
  useEffect(() => { refresh(); }, []);

  const run = (fn) => async (...args) => {
    try { await fn(...args); await refresh(); }
    catch (e) { setErr(e.message || "Action failed."); }
  };

  const create = run(async () => {
    await api.createUser({
      username: form.username.trim(),
      password: form.password,
      role: form.role,
      person_id: form.person_id ? Number(form.person_id) : null,
    });
    setForm({ username: "", password: "", role: "member", person_id: "" });
  });
  const setRole = run((u, role) => api.updateUser(u.id, { role }));
  const setPerson = run((u, pid) => api.updateUser(u.id, pid ? { person_id: Number(pid) } : { clear_person: true }));
  const toggleActive = run((u) => api.updateUser(u.id, { is_active: !u.is_active }));
  const remove = run(async (u) => {
    if (window.confirm(`Delete account "${u.username}"? This cannot be undone.`)) await api.deleteUser(u.id);
  });
  const resetPassword = run(async (u) => {
    const pw = window.prompt(`New password for "${u.username}" (min 8 characters):`);
    if (pw) await api.setUserPassword(u.id, { new_password: pw });
  });

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>User accounts</h2>
      <table>
        <thead><tr><th>Username</th><th>Role</th><th>Person</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>
          {users.map(u => (
            <tr key={u.id}>
              <td>{u.username}{u.id === me.id && <span className="muted"> (you)</span>}</td>
              <td>
                <select value={u.role} onChange={e => setRole(u, e.target.value)} style={{ width: "auto" }}>
                  <option>member</option><option>manager</option><option>admin</option>
                </select>
              </td>
              <td>
                <select value={u.person_id ?? ""} onChange={e => setPerson(u, e.target.value)} style={{ width: "auto" }}
                  title="Roster person this account posts as">
                  <option value="">(none)</option>
                  {people.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </td>
              <td>{u.is_active ? <span className="tag done">active</span> : <span className="tag blocked">disabled</span>}</td>
              <td>
                <button className="link" onClick={() => resetPassword(u)}>set password</button>
                <button className="link" onClick={() => toggleActive(u)}>{u.is_active ? "disable" : "enable"}</button>
                <button className="link" style={{ color: "var(--danger)" }} onClick={() => remove(u)}>delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Add account</h2>
      <div className="row">
        <div><label>Username</label><input value={form.username} onChange={e => set("username", e.target.value)} /></div>
        <div><label>Password (min 8 chars)</label>
          <input type="password" value={form.password} onChange={e => set("password", e.target.value)} /></div>
        <div><label>Role</label>
          <select value={form.role} onChange={e => set("role", e.target.value)}>
            <option>member</option><option>manager</option><option>admin</option>
          </select>
        </div>
        <div><label>Person (optional)</label>
          <select value={form.person_id} onChange={e => set("person_id", e.target.value)}>
            <option value="">(none)</option>
            {people.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
      </div>
      <button onClick={create} disabled={!form.username.trim() || form.password.length < 8}>Add account</button>
      {err && <p style={{ color: "var(--danger)", marginBottom: 0 }}>{err}</p>}
      <p className="muted" style={{ marginBottom: 0 }}>
        Linking a person makes that account post updates under the roster name,
        which feeds the team and person rollups.
      </p>
    </div>
  );
}

function PeoplePanel({ people, onChanged }) {
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ name: "", name_ja: "", team: "", department: "" });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const run = (fn) => async (...args) => {
    try { await fn(...args); onChanged(); setErr(""); }
    catch (e) { setErr(e.message || "Action failed."); }
  };

  const create = run(async () => {
    await api.createPerson({
      name: form.name.trim(),
      name_ja: form.name_ja.trim() || null,
      team: form.team.trim() || null,
      department: form.department.trim() || null,
    });
    setForm({ name: "", name_ja: "", team: "", department: "" });
  });
  const edit = run(async (p) => {
    const team = window.prompt(`Team for ${p.name}:`, p.team || "");
    if (team === null) return;
    const department = window.prompt(`Department for ${p.name}:`, p.department || "");
    if (department === null) return;
    await api.updatePerson(p.id, { name: p.name, name_ja: p.name_ja, team: team || null, department: department || null });
  });
  const remove = run(async (p) => {
    if (window.confirm(`Remove "${p.name}" from the roster?`)) await api.deletePerson(p.id);
  });

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>People (org roster)</h2>
      {people.length === 0 ? <p className="muted">No people yet. Names drive the team and person reports.</p> : (
        <table>
          <thead><tr><th>Name</th><th>Japanese name</th><th>Team</th><th>Department</th><th>Actions</th></tr></thead>
          <tbody>
            {people.map(p => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td className="muted">{p.name_ja || "-"}</td>
                <td>{p.team || "-"}</td>
                <td className="muted">{p.department || "-"}</td>
                <td>
                  <button className="link" onClick={() => edit(p)}>edit</button>
                  <button className="link" style={{ color: "var(--danger)" }} onClick={() => remove(p)}>delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Add person</h2>
      <div className="row">
        <div><label>Name</label><input value={form.name} onChange={e => set("name", e.target.value)} /></div>
        <div><label>Japanese name</label><input value={form.name_ja} onChange={e => set("name_ja", e.target.value)} /></div>
        <div><label>Team</label><input value={form.team} onChange={e => set("team", e.target.value)} /></div>
        <div><label>Department</label><input value={form.department} onChange={e => set("department", e.target.value)} /></div>
      </div>
      <button onClick={create} disabled={!form.name.trim()}>Add person</button>
      {err && <p style={{ color: "var(--danger)", marginBottom: 0 }}>{err}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Settings panel: choose the LLM provider/model and the Whisper model live.
// Reads GET /settings and /settings/models; PUT sends only the changed fields.
// The API key is write-only: typed here, sent once, never echoed back.
// ---------------------------------------------------------------------------
const PROVIDER_LABEL = {
  ollama: "Local (Ollama)",
  openai: "OpenAI compatible API",
  anthropic: "Anthropic API",
};

export function SettingsPanel({ onSaved, onClose }) {
  const [form, setForm] = useState(null);        // editable copy of GET /settings
  const [dirty, setDirty] = useState({});        // only these fields are sent on save
  const [apiKey, setApiKey] = useState("");      // write-only; empty = leave unchanged
  const [models, setModels] = useState({ ollama_models: [], whisper_sizes: [], warning: null });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState(false);

  async function loadModels() {
    try { setModels(await api.listModels()); } catch { /* panel still usable */ }
  }
  useEffect(() => {
    api.getSettings().then(setForm).catch(e => setErr(e.message || "Could not load settings."));
    loadModels();
  }, []);

  const set = (k, v) => {
    setForm(f => ({ ...f, [k]: v }));
    setDirty(d => ({ ...d, [k]: v }));
    setSaved(false);
  };

  async function save() {
    const payload = { ...dirty };
    if (apiKey.trim()) payload.llm_api_key = apiKey.trim();
    if (Object.keys(payload).length === 0) { onClose(); return; }
    setBusy(true); setErr("");
    try {
      const s = await api.putSettings(payload);
      setForm(s); setDirty({}); setApiKey(""); setSaved(true);
      onSaved(s);
    } catch (e) {
      setErr(e.message || "Could not save settings.");
    } finally {
      setBusy(false);
    }
  }

  if (!form) return <div className="card"><p className="muted">{err || "Loading settings…"}</p></div>;

  const cloud = form.llm_provider !== "ollama";
  // The configured model may not be in the installed list (e.g. Ollama down);
  // keep it selectable so the dropdown never silently changes the value.
  const ollamaOptions = models.ollama_models.includes(form.llm_model) || cloud
    ? models.ollama_models
    : [form.llm_model, ...models.ollama_models];

  return (
    <div className="card" style={{ borderColor: "var(--accent)" }}>
      <div className="row" style={{ alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Settings</h2>
        <span style={{ flex: 1 }} />
        <button className="link" onClick={onClose}>close</button>
      </div>

      <label>LLM provider</label>
      <div className="row" role="radiogroup">
        {Object.entries(PROVIDER_LABEL).map(([value, label]) => (
          <label key={value} style={{ fontWeight: 400, display: "flex", alignItems: "center", gap: 6, margin: 0 }}>
            <input type="radio" name="llm_provider" value={value} style={{ width: "auto" }}
              checked={form.llm_provider === value} onChange={() => set("llm_provider", value)} />
            {label}
          </label>
        ))}
      </div>

      {cloud ? (
        <>
          <div className="cloudwarn">
            Cloud mode: update text is sent to an external API for extraction.
            Audio transcription stays on this machine either way.
          </div>
          <div className="row">
            <div><label>Model</label>
              <input value={form.llm_model} onChange={e => set("llm_model", e.target.value)}
                placeholder={form.llm_provider === "openai" ? "gpt-4o-mini" : "claude-haiku-4-5-20251001"} />
            </div>
            <div><label>API key {form.api_key_set ? "(set)" : "(not set)"}</label>
              <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)}
                placeholder={form.api_key_set ? "leave blank to keep the current key" : "paste the key"} />
            </div>
          </div>
          {form.llm_provider === "openai" && (
            <div><label>Base URL (optional, for vLLM or another compatible server)</label>
              <input value={form.llm_base_url} onChange={e => set("llm_base_url", e.target.value)}
                placeholder="https://api.openai.com" />
            </div>
          )}
        </>
      ) : (
        <div className="row">
          <div><label>Model</label>
            <select value={form.llm_model} onChange={e => set("llm_model", e.target.value)}>
              {ollamaOptions.map(m => <option key={m}>{m}</option>)}
            </select>
          </div>
          <div><label>Ollama URL</label>
            <input value={form.ollama_url} onChange={e => set("ollama_url", e.target.value)} />
          </div>
          <div style={{ flex: "0 0 auto", alignSelf: "flex-end" }}>
            <button style={{ marginTop: 0 }} onClick={loadModels} title="Re-list installed models">Refresh</button>
          </div>
        </div>
      )}
      {!cloud && models.warning && <p className="muted" style={{ color: "var(--danger)" }}>{models.warning}</p>}

      <label style={{ marginTop: 14 }}>Speech to text (Whisper, always local)</label>
      <div className="row">
        <div><label>Model size</label>
          <select value={form.whisper_model} onChange={e => set("whisper_model", e.target.value)}>
            {(models.whisper_sizes.length ? models.whisper_sizes : [form.whisper_model]).map(s => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div><label>Device</label>
          <select value={form.whisper_device} onChange={e => set("whisper_device", e.target.value)}>
            <option value="cpu">cpu</option>
            <option value="cuda">cuda (NVIDIA GPU)</option>
          </select>
        </div>
      </div>
      <p className="muted">Changing the size downloads that model on the next transcription (up to ~3 GB for large).</p>

      <details style={{ marginTop: 8 }}>
        <summary className="muted" style={{ cursor: "pointer" }}>Advanced</summary>
        <div className="row">
          <div><label>Temperature (0 = deterministic)</label>
            <input type="number" min="0" max="2" step="0.1" value={form.llm_temperature}
              onChange={e => set("llm_temperature", Number(e.target.value))} />
          </div>
          <div><label>LLM timeout (seconds)</label>
            <input type="number" min="1" max="600" value={form.llm_timeout}
              onChange={e => set("llm_timeout", Number(e.target.value))} />
          </div>
        </div>
      </details>

      <div className="row" style={{ alignItems: "center" }}>
        <button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save settings"}</button>
        {saved && <span className="tag done" style={{ marginTop: 12 }}>Saved. Applies to the next extraction.</span>}
      </div>
      {err && <p style={{ color: "var(--danger)", marginBottom: 0 }}>{err}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Manager dashboard (week 5): fixed KPIs read from GET /dashboard. Read-only.
// ---------------------------------------------------------------------------
const STATUS_SEG = ["not_started", "in_progress", "blocked", "done"];
const STATUS_LABEL = { not_started: "Not started", in_progress: "In progress", blocked: "Blocked", done: "Done" };

export function Dashboard({ tick, me }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [config, setConfig] = useState(null);     // active ViewConfig, null = full view
  const [cmd, setCmd] = useState("");
  const [busy, setBusy] = useState(false);
  const [views, setViews] = useState([]);
  const [saveName, setSaveName] = useState("");
  const [recording, setRecording] = useState(false);
  const [presets, setPresets] = useState({ teams: [], presets: [] });
  const [team, setTeam] = useState("");
  const recRef = useRef(null);

  async function loadFull() {
    try { setD(await api.dashboard()); setConfig(null); setErr(""); }
    catch (e) { setErr(e.message || "Could not load dashboard."); }
  }
  async function refreshViews() {
    try { setViews(await api.listViews()); } catch { /* ignore */ }
  }
  useEffect(() => { loadFull(); refreshViews(); }, [tick]);
  useEffect(() => {
    api.listPresets()
      .then(p => { setPresets(p); setTeam(p.teams[0] || ""); })
      .catch(() => { /* chips simply don't render */ });
  }, []);

  async function runCmd(text) {
    const q = (text ?? cmd).trim();
    if (!q) return;
    setBusy(true); setErr("");
    try {
      const r = await api.configureDashboard({ request: q });
      setConfig(r.config); setD(r.dashboard);
    } catch (e) { setErr(e.message || "Could not interpret that command."); }
    finally { setBusy(false); }
  }
  async function applySaved(v) {
    setBusy(true); setErr("");
    try { const r = await api.applyView(v.config); setConfig(r.config); setD(r.dashboard); setCmd(v.name); }
    catch (e) { setErr(e.message || "Could not apply view."); }
    finally { setBusy(false); }
  }
  // Preset chips: deterministic configs from the backend, applied with no LLM in the
  // loop. The equivalent NL phrase lands in the command box so the typed path is learnable.
  async function applyPreset(p) {
    const fill = (v) => (typeof v === "string" ? v.replaceAll("{team}", team) : v);
    const cfg = Object.fromEntries(Object.entries(p.config).map(([k, v]) => [k, fill(v)]));
    setBusy(true); setErr("");
    try {
      const r = await api.applyView(cfg);
      setConfig(r.config); setD(r.dashboard); setCmd(fill(p.nl_phrase));
    } catch (e) { setErr(e.message || "Could not apply view."); }
    finally { setBusy(false); }
  }
  async function saveCurrent() {
    if (!saveName.trim() || !config) return;
    await api.saveView({ name: saveName.trim(), config });
    setSaveName(""); refreshViews();
  }
  async function removeView(id) { await api.deleteView(id); refreshViews(); }

  async function toggleMic() {
    if (recording) { recRef.current?.stop(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream); const chunks = [];
      rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop()); setRecording(false);
        try {
          const fd = new FormData(); fd.append("file", new Blob(chunks, { type: rec.mimeType || "audio/webm" }), "cmd.webm");
          const r = await api.transcribe(fd); setCmd(r.text); runCmd(r.text);
        } catch (e) { setErr(e.message || "Transcription failed."); }
      };
      recRef.current = rec; rec.start(); setRecording(true);
    } catch (e) { setErr("Microphone unavailable: " + (e.message || e)); }
  }

  if (err && !d) return <div className="card" style={{ borderColor: "var(--danger)", color: "var(--danger)" }}>{err}</div>;
  if (!d) return <div className="card"><p className="muted">Loading dashboard…</p></div>;

  const totalTasks = d.totals.tasks || 0;
  const pct = (n) => (totalTasks ? (n / totalTasks) * 100 : 0);
  const sections = config?.sections || [];
  const hide = config?.hide || [];
  const vis = (s) => (sections.length === 0 || sections.includes(s)) && !hide.includes(s);
  const chipBits = config && [
    config.project, config.status && STATUS_LABEL[config.status], config.severity && `${config.severity} sev`,
    config.team && `team: ${config.team}`, config.person && `person: ${config.person}`,
    config.sort && `by ${config.sort}`, config.limit && `top ${config.limit}`,
    config.days && `last ${config.days} days`,
    !config.days && config.date_from && `from ${config.date_from}`,
    !config.days && config.date_to && `to ${config.date_to}`,
  ].filter(Boolean);

  return (
    <>
      <div className="card cmdbar">
        {presets.presets.length > 0 && (
          <div className="presets">
            <span className="muted">Quick views:</span>
            {presets.teams.length > 0 && (
              <select className="teamsel" value={team} onChange={e => setTeam(e.target.value)} title="Team for the team presets">
                {presets.teams.map(t => <option key={t}>{t}</option>)}
              </select>
            )}
            {presets.presets.map(p => (
              (!p.needs_team || presets.teams.length > 0) &&
              <button key={p.id} className="presetchip" disabled={busy}
                title={p.nl_phrase.replaceAll("{team}", team)}
                onClick={() => applyPreset(p)}>{p.label}</button>
            ))}
          </div>
        )}
        <div className="cmdrow">
          <input value={cmd} onChange={e => setCmd(e.target.value)}
            onKeyDown={e => e.key === "Enter" && runCmd()}
            placeholder='Reconfigure in words: "show only blocked tasks", "hide risks, top 3 blockers"' />
          <button onClick={() => runCmd()} disabled={busy}>{busy ? "…" : "Run"}</button>
          <button onClick={toggleMic} title="Speak a command"
            style={{ background: recording ? "#c0392b" : "#1f3864" }}>{recording ? "■" : "🎙"}</button>
        </div>
        {config && (
          <div className="activecfg">
            <span className="tag view">view: {config.summary || "custom"}</span>
            {chipBits.map((b, i) => <span key={i} className="tag">{b}</span>)}
            <button className="link" onClick={loadFull}>clear</button>
            <span style={{ flex: 1 }} />
            <input className="savein" value={saveName} onChange={e => setSaveName(e.target.value)} placeholder="name this view" />
            <button onClick={saveCurrent} disabled={!saveName.trim()}>Save view</button>
          </div>
        )}
        {views.length > 0 && (
          <div className="savedviews">
            <span className="muted">Saved:</span>
            {views.map(v => (
              <span key={v.id} className="viewchip">
                <button className="vname" onClick={() => applySaved(v)}>{v.name}</button>
                {/* delete: the creator, or manager+ (shared/legacy views have no creator) */}
                {(!me || isManagerUp(me) || v.created_by === me.id) && (
                  <button className="vx" onClick={() => removeView(v.id)} title="Delete">×</button>
                )}
              </span>
            ))}
          </div>
        )}
        {err && <p className="muted" style={{ color: "var(--danger)", margin: "6px 0 0" }}>{err}</p>}
      </div>

      <div className="kpis">
        <div className="kpi"><div className="n">{d.totals.projects}</div><div className="l">Projects</div></div>
        <div className="kpi"><div className="n">{d.totals.tasks}</div><div className="l">Tasks</div></div>
        <div className="kpi"><div className="n">{d.overall_progress}%</div><div className="l">Overall progress</div></div>
        <div className={"kpi" + (d.open_blockers ? " warn" : "")}><div className="n">{d.open_blockers}</div><div className="l">Open blockers</div></div>
        <div className={"kpi" + (d.open_risks ? " warn" : "")}><div className="n">{d.open_risks}</div><div className="l">Open risks</div></div>
      </div>

      {vis("trends") && <div className="row" style={{ alignItems: "stretch" }}>
        <div className="card" style={{ flex: 1 }}>
          <div className="h3">Progress over time</div>
          <TrendChart points={d.trends?.progress} max={100} unit="%" color="var(--trend-good)" />
        </div>
        <div className="card" style={{ flex: 1 }}>
          <div className="h3">Open blockers over time</div>
          <TrendChart points={d.trends?.blockers} unit="" color="var(--danger)" step />
        </div>
      </div>}

      {vis("delivery") && <div className="card">
        <div className="h3">Delivery status</div>
        <div className="segbar">
          {STATUS_SEG.map(s => pct(d.task_status_counts[s]) > 0 &&
            <div key={s} className={"seg s_" + s} style={{ width: pct(d.task_status_counts[s]) + "%" }}
              title={`${STATUS_LABEL[s]}: ${d.task_status_counts[s]}`} />)}
        </div>
        <div className="seglegend">
          {STATUS_SEG.map(s => (
            <span key={s}><span className={"sw seg s_" + s} />{STATUS_LABEL[s]}: {d.task_status_counts[s]}</span>
          ))}
        </div>
      </div>}

      {vis("per_project") && <div className="card">
        <div className="h3">Projects</div>
        <table>
          <thead><tr><th>Project</th><th>Status</th><th>Progress</th><th>Tasks</th><th>Open blockers</th></tr></thead>
          <tbody>
            {d.per_project.map(p => (
              <tr key={p.id}>
                <td>{p.name}{p.name_ja && <div className="muted">{p.name_ja}</div>}</td>
                <td><span className={"st " + p.status}>{STATUS_LABEL[p.status] || p.status}</span></td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div className="progress"><div style={{ width: p.avg_progress + "%" }} /></div>
                    <span className="muted">{p.avg_progress}%</span>
                  </div>
                </td>
                <td>{p.done_task_count}/{p.task_count} done</td>
                <td>{p.open_blocker_count > 0 ? <span className="tag blocked">{p.open_blocker_count}</span> : <span className="muted">0</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}

      {vis("per_team") && (d.per_team?.length > 0) && <div className="card">
        <div className="h3">Teams</div>
        <table>
          <thead><tr><th>Team</th><th>Department</th><th>Members</th><th>Progress</th><th>Tasks</th><th>Open blockers</th></tr></thead>
          <tbody>
            {d.per_team.map(t => (
              <tr key={t.team}>
                <td>{t.team}</td>
                <td className="muted">{t.department || "-"}</td>
                <td className="muted">{t.members.join(", ")}</td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div className="progress"><div style={{ width: t.avg_progress + "%" }} /></div>
                    <span className="muted">{t.avg_progress}%</span>
                  </div>
                </td>
                <td>{t.done_task_count}/{t.task_count} done</td>
                <td>{t.open_blocker_count > 0 ? <span className="tag blocked">{t.open_blocker_count}</span> : <span className="muted">0</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}

      {vis("per_person") && (d.per_person?.length > 0) && <div className="card">
        <div className="h3">People</div>
        <table>
          <thead><tr><th>Person</th><th>Team</th><th>Progress</th><th>Tasks</th><th>Open blockers</th><th>Next steps</th></tr></thead>
          <tbody>
            {d.per_person.map(p => (
              <tr key={p.name}>
                <td>{p.name}</td>
                <td className="muted">{p.team || "-"}</td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div className="progress"><div style={{ width: p.avg_progress + "%" }} /></div>
                    <span className="muted">{p.avg_progress}%</span>
                  </div>
                </td>
                <td>{p.done_task_count}/{p.task_count} done</td>
                <td>{p.open_blocker_count > 0 ? <span className="tag blocked">{p.open_blocker_count}</span> : <span className="muted">0</span>}</td>
                <td>{p.next_step_count > 0 ? p.next_step_count : <span className="muted">0</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}

      {(vis("blockers") || vis("risks")) && <div className="row" style={{ alignItems: "stretch" }}>
        {vis("blockers") && <div className="card" style={{ flex: 1 }}>
          <div className="h3">Open blockers ({d.open_blockers})</div>
          {d.blockers_list.length === 0 ? <p className="muted">None open.</p> : (
            <div className="feed">
              {d.blockers_list.map((b, i) => (
                <div key={i} className="item">
                  <span className={"sevdot " + b.severity} />{b.description}
                  <div className="muted">{b.severity}{b.task ? ` · ${b.task}` : ""}{b.owner ? ` · ${b.owner}` : ""}</div>
                </div>
              ))}
            </div>
          )}
        </div>}
        {vis("risks") && <div className="card" style={{ flex: 1 }}>
          <div className="h3">Risks ({d.open_risks})</div>
          {d.risks_list.length === 0 ? <p className="muted">None flagged.</p> : (
            <div className="feed">
              {d.risks_list.map((r, i) => (
                <div key={i} className="item">
                  {r.description}
                  <div className="muted">{r.impact ? `impact ${r.impact}` : ""}{r.mitigation ? ` · mitigation: ${r.mitigation}` : ""}{r.task ? ` · ${r.task}` : ""}</div>
                </div>
              ))}
            </div>
          )}
        </div>}
      </div>}

      {(vis("activity") || vis("next_steps")) && <div className="row" style={{ alignItems: "stretch" }}>
        {vis("activity") && <div className="card" style={{ flex: 1 }}>
          <div className="h3">Recent activity</div>
          {d.recent_updates.length === 0 ? <p className="muted">No updates yet.</p> : (
            <div className="feed">
              {d.recent_updates.map(u => (
                <div key={u.id} className={"item" + (u.source === "voice" ? " voice" : "")}>
                  {u.snippet || "(no text)"}
                  <div className="muted">
                    {new Date(u.created_at).toLocaleDateString()} · {u.task || "(no task)"}
                    {u.author ? ` · ${u.author}` : ""} · {u.source}{u.language === "ja" ? " · JA" : ""}
                    {u.blocker_count ? ` · ${u.blocker_count} blocker(s)` : ""}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>}
        {vis("next_steps") && <div className="card" style={{ flex: 1 }}>
          <div className="h3">Upcoming next steps</div>
          {d.upcoming_next_steps.length === 0 ? <p className="muted">Nothing queued.</p> : (
            <div className="feed">
              {d.upcoming_next_steps.map((n, i) => (
                <div key={i} className="item">
                  {n.description}
                  <div className="muted">{n.due_date ? `due ${n.due_date}` : "no date"}{n.owner ? ` · ${n.owner}` : ""}{n.task ? ` · ${n.task}` : ""}</div>
                </div>
              ))}
            </div>
          )}
        </div>}
      </div>}
    </>
  );
}

// Dependency-free inline SVG line chart (trends sprint). `step` draws a step line
// (right then down/up) for count series; otherwise a straight polyline. Scales to
// `max` when given (progress 0-100), else to the series peak.
export function TrendChart({ points, max, unit = "", color = "var(--accent)", step = false }) {
  if (!points || points.length === 0) return <p className="muted">No history yet.</p>;
  const W = 320, H = 96, PAD = 6;
  const hi = max ?? Math.max(...points.map(p => p.value), 1);
  const x = (i) => (points.length === 1 ? W / 2 : PAD + (i * (W - 2 * PAD)) / (points.length - 1));
  const y = (v) => H - PAD - (v / hi) * (H - 2 * PAD);
  const coords = [];
  points.forEach((p, i) => {
    if (step && i > 0) coords.push(`${x(i)},${y(points[i - 1].value)}`);
    coords.push(`${x(i)},${y(p.value)}`);
  });
  const last = points[points.length - 1];
  return (
    <div className="trend">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        {/* CSS vars only work reliably in SVG via style, not presentation attributes */}
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} style={{ stroke: "var(--border-soft)" }} />
        <polyline points={coords.join(" ")} fill="none" strokeWidth="2" style={{ stroke: color }} />
        <circle cx={x(points.length - 1)} cy={y(last.value)} r="3" style={{ fill: color }} />
      </svg>
      <div className="trendmeta">
        <span className="muted">{points[0].date}</span>
        <span style={{ color }}><b>{last.value}{unit}</b></span>
        <span className="muted">{last.date}</span>
      </div>
    </div>
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

function UpdateForm({ tasks, onDone, me, people = [] }) {
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
        <AuthorField me={me} people={people} value={form.author} onChange={v => set("author", v)} />
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
function AiUpdateForm({ tasks, onDone, me, people = [] }) {
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
      status: draft.status || null,            // snapshot on the Update; also patches the Task
      progress_pct: draft.progress_pct ?? null,
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
    <div className="card" style={{ borderColor: "var(--accent)" }}>
      <h2>Add update by voice or text (AI)</h2>
      <div className="row" style={{ alignItems: "center", marginBottom: 6 }}>
        <button onClick={toggleRecord} disabled={transcribing}
          style={{ marginTop: 0, background: recording ? "#c0392b" : "#1f3864" }}>
          {recording ? "■ Stop recording" : "● Record"}
        </button>
        <label style={{ margin: 0, fontWeight: 400, color: "var(--muted)" }}>
          or upload audio:&nbsp;
          <input type="file" accept="audio/*" onChange={onPickFile} disabled={transcribing}
            style={{ width: "auto", display: "inline-block", padding: 2, border: 0 }} />
        </label>
        {transcribing && <span className="muted">transcribing…</span>}
        {source === "voice" && !transcribing && <span className="tag done">from voice</span>}
      </div>
      <label>Update text (English, Japanese, or mixed): speak above, or type/edit here</label>
      <textarea rows="3" value={text} onChange={e => setText(e.target.value)}
        placeholder="e.g. Checkout flow rework is about 60% done, wrapping up the payment screens by Friday." />
      <div className="row">
        <div><label>Language</label>
          <select value={language} onChange={e => setLanguage(e.target.value)}>
            <option value="en">English</option><option value="ja">Japanese</option>
          </select>
        </div>
        <AuthorField me={me} people={people} value={author} onChange={setAuthor} />
      </div>
      <button onClick={extract} disabled={busy || !text.trim()}>
        {busy ? "Extracting..." : "Extract"}
      </button>
      {err && <p style={{ color: "var(--danger)", marginBottom: 0 }}>{err}</p>}

      {draft && (
        <div style={{ marginTop: 16, borderTop: "1px solid var(--border-soft)", paddingTop: 12 }}>
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
      <button onClick={onAdd} style={{ background: "var(--chip-bg)", color: "var(--text)", marginTop: 4, padding: "5px 10px" }}>+ add</button>
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
