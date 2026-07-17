import React, { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import DocsPage from "./Docs.jsx";
import { useLang } from "./i18n.js";

const STATUS = ["not_started", "in_progress", "blocked", "done"];
const SEVERITY = ["low", "medium", "high"];
const ROLE_ORDER = { member: 0, manager: 1, admin: 2 };
const isManagerUp = (me) => !!me && ROLE_ORDER[me.role] >= ROLE_ORDER.manager;

export default function App() {
  const { lang, t, setLang } = useLang();
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
      setError(t("error.cannotReachApi"));
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

  const langToggle = (
    <button className="themetoggle" title={t("nav.switchLang")}
      onClick={() => setLang(l => (l === "en" ? "ja" : "en"))}>
      {lang === "en" ? "日本語" : "English"}
    </button>
  );

  if (me === null) {
    return (
      <>
        <div className="bar" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span><b>OneStatus</b> &nbsp;·&nbsp; {t("header.tagline")}</span>
          <span className="tabs">
            {langToggle}
            <button className="themetoggle" title={t("nav.switchTheme")}
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
        <span><b>OneStatus</b> &nbsp;·&nbsp; {t("header.tagline")}</span>
        <span className="tabs">
          <button className={view === "dashboard" ? "on" : ""} onClick={() => setView("dashboard")}>{t("nav.dashboard")}</button>
          <button className={view === "capture" ? "on" : ""} onClick={() => setView("capture")}>{t("nav.capture")}</button>
          <button className={view === "docs" ? "on" : ""} onClick={() => setView("docs")}>{t("nav.docs")}</button>
          {admin && (
            <button className={view === "admin" ? "on" : ""} onClick={() => setView("admin")}>{t("nav.admin")}</button>
          )}
          {settings && (
            <span className={"provbadge" + (settings.llm_provider === "ollama" ? "" : " cloud")}
              title={settings.llm_provider === "ollama" ? t("nav.providerTitleLocal") : t("nav.providerTitleCloud")}>
              {settings.llm_provider === "ollama" ? t("nav.local") : t("nav.cloud")}: {settings.llm_model}
            </span>
          )}
          <span className="provbadge" title={t("nav.loggedInAs", { username: me.username, role: t(`role.${me.role}`) })}>
            {me.author} · {t(`role.${me.role}`)}
          </span>
          {admin && (
            <button className="themetoggle" title={t("nav.settingsTitle")} onClick={() => setShowSettings(s => !s)}>⚙️</button>
          )}
          {langToggle}
          <button className="themetoggle" title={t("nav.switchTheme")}
            onClick={() => setTheme(t => (t === "light" ? "dark" : "light"))}>
            {theme === "light" ? "🌙" : "☀️"}
          </button>
          <button className="themetoggle" title={t("nav.logout")} onClick={logout}>{t("nav.logout")}</button>
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
        {view === "docs" && <DocsPage />}
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
  const { t } = useLang();
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
      setErr(e2.message || t("login.failed"));
      setBusy(false);
    }
  }

  return (
    <form className="card" style={{ maxWidth: 380, margin: "60px auto" }} onSubmit={submit}>
      <h2 style={{ marginTop: 0 }}>{t("login.title")}</h2>
      <label htmlFor="login-username">{t("login.username")}</label>
      <input id="login-username" value={username} onChange={e => setUsername(e.target.value)}
        autoFocus autoComplete="username" />
      <label htmlFor="login-password">{t("login.password")}</label>
      <input id="login-password" type="password" value={password} onChange={e => setPassword(e.target.value)}
        autoComplete="current-password" />
      <button type="submit" disabled={busy || !username.trim() || !password}>
        {busy ? t("login.buttonBusy") : t("login.button")}
      </button>
      {err && <p style={{ color: "var(--danger)", marginBottom: 0 }}>{err}</p>}
      <p className="muted" style={{ marginBottom: 0 }}>{t("login.noAccount")}</p>
    </form>
  );
}

// Author control on the capture forms. Members always post as themselves (the
// server enforces it); manager and admin can pick a roster name or type one.
function AuthorField({ me, people, value, onChange }) {
  const { t } = useLang();
  if (!isManagerUp(me)) {
    return (
      <div><label>{t("author.label")}</label>
        <input value={me?.author || ""} readOnly title={t("author.readonlyTitle")} />
      </div>
    );
  }
  return (
    <div><label>{t("author.labelManager")}</label>
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

const ROLES = ["member", "manager", "admin"];

function UsersPanel({ me, people }) {
  const { t } = useLang();
  const [users, setUsers] = useState([]);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ username: "", password: "", role: "member", person_id: "" });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  async function refresh() {
    try { setUsers(await api.listUsers()); setErr(""); }
    catch (e) { setErr(e.message || t("error.loadUsers")); }
  }
  useEffect(() => { refresh(); }, []);

  const run = (fn) => async (...args) => {
    try { await fn(...args); await refresh(); }
    catch (e) { setErr(e.message || t("error.actionFailed")); }
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
    if (window.confirm(t("confirm.deleteUser", { username: u.username }))) await api.deleteUser(u.id);
  });
  const resetPassword = run(async (u) => {
    const pw = window.prompt(t("prompt.newPassword", { username: u.username }));
    if (pw) await api.setUserPassword(u.id, { new_password: pw });
  });

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>{t("admin.users.title")}</h2>
      <table>
        <thead><tr><th>{t("table.username")}</th><th>{t("table.role")}</th><th>{t("table.person")}</th><th>{t("table.status")}</th><th>{t("table.actions")}</th></tr></thead>
        <tbody>
          {users.map(u => (
            <tr key={u.id}>
              <td>{u.username}{u.id === me.id && <span className="muted"> {t("common.you")}</span>}</td>
              <td>
                <select value={u.role} onChange={e => setRole(u, e.target.value)} style={{ width: "auto" }}>
                  {ROLES.map(r => <option key={r} value={r}>{t(`role.${r}`)}</option>)}
                </select>
              </td>
              <td>
                <select value={u.person_id ?? ""} onChange={e => setPerson(u, e.target.value)} style={{ width: "auto" }}
                  title={t("admin.users.personSelectTitle")}>
                  <option value="">{t("common.none")}</option>
                  {people.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </td>
              <td>{u.is_active ? <span className="tag done">{t("status.active")}</span> : <span className="tag blocked">{t("status.disabled")}</span>}</td>
              <td>
                <button className="link" onClick={() => resetPassword(u)}>{t("action.setPassword")}</button>
                <button className="link" onClick={() => toggleActive(u)}>{u.is_active ? t("action.disable") : t("action.enable")}</button>
                <button className="link" style={{ color: "var(--danger)" }} onClick={() => remove(u)}>{t("action.delete")}</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>{t("admin.users.add")}</h2>
      <div className="row">
        <div><label>{t("table.username")}</label><input value={form.username} onChange={e => set("username", e.target.value)} /></div>
        <div><label>{t("admin.users.passwordLabel")}</label>
          <input type="password" value={form.password} onChange={e => set("password", e.target.value)} /></div>
        <div><label>{t("table.role")}</label>
          <select value={form.role} onChange={e => set("role", e.target.value)}>
            {ROLES.map(r => <option key={r} value={r}>{t(`role.${r}`)}</option>)}
          </select>
        </div>
        <div><label>{t("admin.users.personLabel")}</label>
          <select value={form.person_id} onChange={e => set("person_id", e.target.value)}>
            <option value="">{t("common.none")}</option>
            {people.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
      </div>
      <button onClick={create} disabled={!form.username.trim() || form.password.length < 8}>{t("admin.users.add")}</button>
      {err && <p style={{ color: "var(--danger)", marginBottom: 0 }}>{err}</p>}
      <p className="muted" style={{ marginBottom: 0 }}>{t("admin.users.hint")}</p>
    </div>
  );
}

function PeoplePanel({ people, onChanged }) {
  const { t } = useLang();
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ name: "", name_ja: "", team: "", department: "" });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const run = (fn) => async (...args) => {
    try { await fn(...args); onChanged(); setErr(""); }
    catch (e) { setErr(e.message || t("error.actionFailed")); }
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
    const team = window.prompt(t("prompt.teamFor", { name: p.name }), p.team || "");
    if (team === null) return;
    const department = window.prompt(t("prompt.departmentFor", { name: p.name }), p.department || "");
    if (department === null) return;
    await api.updatePerson(p.id, { name: p.name, name_ja: p.name_ja, team: team || null, department: department || null });
  });
  const remove = run(async (p) => {
    if (window.confirm(t("confirm.removePerson", { name: p.name }))) await api.deletePerson(p.id);
  });

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>{t("admin.people.title")}</h2>
      {people.length === 0 ? <p className="muted">{t("admin.people.empty")}</p> : (
        <table>
          <thead><tr><th>{t("table.name")}</th><th>{t("table.nameJa")}</th><th>{t("table.team")}</th><th>{t("table.department")}</th><th>{t("table.actions")}</th></tr></thead>
          <tbody>
            {people.map(p => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td className="muted">{p.name_ja || "-"}</td>
                <td>{p.team || "-"}</td>
                <td className="muted">{p.department || "-"}</td>
                <td>
                  <button className="link" onClick={() => edit(p)}>{t("action.edit")}</button>
                  <button className="link" style={{ color: "var(--danger)" }} onClick={() => remove(p)}>{t("action.delete")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>{t("admin.people.add")}</h2>
      <div className="row">
        <div><label>{t("table.name")}</label><input value={form.name} onChange={e => set("name", e.target.value)} /></div>
        <div><label>{t("table.nameJa")}</label><input value={form.name_ja} onChange={e => set("name_ja", e.target.value)} /></div>
        <div><label>{t("table.team")}</label><input value={form.team} onChange={e => set("team", e.target.value)} /></div>
        <div><label>{t("table.department")}</label><input value={form.department} onChange={e => set("department", e.target.value)} /></div>
      </div>
      <button onClick={create} disabled={!form.name.trim()}>{t("admin.people.add")}</button>
      {err && <p style={{ color: "var(--danger)", marginBottom: 0 }}>{err}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Settings panel: choose the LLM provider/model and the Whisper model live.
// Reads GET /settings and /settings/models; PUT sends only the changed fields.
// The API key is write-only: typed here, sent once, never echoed back.
// ---------------------------------------------------------------------------
const PROVIDER_KEYS = {
  ollama: "settings.providerLocal",
  openai: "settings.providerOpenAI",
  anthropic: "settings.providerAnthropic",
};

export function SettingsPanel({ onSaved, onClose }) {
  const { t } = useLang();
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
    api.getSettings().then(setForm).catch(e => setErr(e.message || t("error.loadSettings")));
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
      setErr(e.message || t("error.saveSettings"));
    } finally {
      setBusy(false);
    }
  }

  if (!form) return <div className="card"><p className="muted">{err || t("settings.loading")}</p></div>;

  const cloud = form.llm_provider !== "ollama";
  // The configured model may not be in the installed list (e.g. Ollama down);
  // keep it selectable so the dropdown never silently changes the value.
  const ollamaOptions = models.ollama_models.includes(form.llm_model) || cloud
    ? models.ollama_models
    : [form.llm_model, ...models.ollama_models];

  return (
    <div className="card" style={{ borderColor: "var(--accent)" }}>
      <div className="row" style={{ alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>{t("settings.title")}</h2>
        <span style={{ flex: 1 }} />
        <button className="link" onClick={onClose}>{t("settings.close")}</button>
      </div>

      <label>{t("settings.providerLabel")}</label>
      <div className="row" role="radiogroup">
        {Object.entries(PROVIDER_KEYS).map(([value, key]) => (
          <label key={value} style={{ fontWeight: 400, display: "flex", alignItems: "center", gap: 6, margin: 0 }}>
            <input type="radio" name="llm_provider" value={value} style={{ width: "auto" }}
              checked={form.llm_provider === value} onChange={() => set("llm_provider", value)} />
            {t(key)}
          </label>
        ))}
      </div>

      {cloud ? (
        <>
          <div className="cloudwarn">
            {t("settings.cloudWarning")}
          </div>
          <div className="row">
            <div><label>{t("settings.model")}</label>
              <input value={form.llm_model} onChange={e => set("llm_model", e.target.value)}
                placeholder={form.llm_provider === "openai" ? "gpt-4o-mini" : "claude-haiku-4-5-20251001"} />
            </div>
            <div><label>{form.api_key_set ? t("settings.apiKeySet") : t("settings.apiKeyNotSet")}</label>
              <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)}
                placeholder={form.api_key_set ? t("settings.apiKeyPlaceholderSet") : t("settings.apiKeyPlaceholderUnset")} />
            </div>
          </div>
          {form.llm_provider === "openai" && (
            <div><label>{t("settings.baseUrl")}</label>
              <input value={form.llm_base_url} onChange={e => set("llm_base_url", e.target.value)}
                placeholder="https://api.openai.com" />
            </div>
          )}
        </>
      ) : (
        <div className="row">
          <div><label>{t("settings.model")}</label>
            <select value={form.llm_model} onChange={e => set("llm_model", e.target.value)}>
              {ollamaOptions.map(m => <option key={m}>{m}</option>)}
            </select>
          </div>
          <div><label>{t("settings.ollamaUrl")}</label>
            <input value={form.ollama_url} onChange={e => set("ollama_url", e.target.value)} />
          </div>
          <div style={{ flex: "0 0 auto", alignSelf: "flex-end" }}>
            <button style={{ marginTop: 0 }} onClick={loadModels} title={t("settings.refreshTitle")}>{t("settings.refresh")}</button>
          </div>
        </div>
      )}
      {!cloud && models.warning && <p className="muted" style={{ color: "var(--danger)" }}>{models.warning}</p>}

      <label style={{ marginTop: 14 }}>{t("settings.whisperLabel")}</label>
      <div className="row">
        <div><label>{t("settings.modelSize")}</label>
          <select value={form.whisper_model} onChange={e => set("whisper_model", e.target.value)}>
            {(models.whisper_sizes.length ? models.whisper_sizes : [form.whisper_model]).map(s => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div><label>{t("settings.device")}</label>
          <select value={form.whisper_device} onChange={e => set("whisper_device", e.target.value)}>
            <option value="cpu">cpu</option>
            <option value="cuda">cuda (NVIDIA GPU)</option>
          </select>
        </div>
      </div>
      <p className="muted">{t("settings.whisperHint")}</p>

      <details style={{ marginTop: 8 }}>
        <summary className="muted" style={{ cursor: "pointer" }}>{t("settings.advanced")}</summary>
        <div className="row">
          <div><label>{t("settings.temperature")}</label>
            <input type="number" min="0" max="2" step="0.1" value={form.llm_temperature}
              onChange={e => set("llm_temperature", Number(e.target.value))} />
          </div>
          <div><label>{t("settings.timeout")}</label>
            <input type="number" min="1" max="600" value={form.llm_timeout}
              onChange={e => set("llm_timeout", Number(e.target.value))} />
          </div>
        </div>
      </details>

      <div className="row" style={{ alignItems: "center" }}>
        <button onClick={save} disabled={busy}>{busy ? t("settings.saving") : t("settings.save")}</button>
        {saved && <span className="tag done" style={{ marginTop: 12 }}>{t("settings.saved")}</span>}
      </div>
      {err && <p style={{ color: "var(--danger)", marginBottom: 0 }}>{err}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Manager dashboard (week 5): fixed KPIs read from GET /dashboard. Read-only.
// ---------------------------------------------------------------------------
const STATUS_SEG = ["not_started", "in_progress", "blocked", "done"];

export function Dashboard({ tick, me }) {
  const { t } = useLang();
  const statusLabel = (s) => (STATUS.includes(s) ? t(`status.${s}`) : s);
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
    catch (e) { setErr(e.message || t("error.loadDashboard")); }
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
    } catch (e) { setErr(e.message || t("error.command")); }
    finally { setBusy(false); }
  }
  async function applySaved(v) {
    setBusy(true); setErr("");
    try { const r = await api.applyView(v.config); setConfig(r.config); setD(r.dashboard); setCmd(v.name); }
    catch (e) { setErr(e.message || t("error.applyView")); }
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
    } catch (e) { setErr(e.message || t("error.applyView")); }
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
        } catch (e) { setErr(e.message || t("error.transcribe")); }
      };
      recRef.current = rec; rec.start(); setRecording(true);
    } catch (e) { setErr(t("ai.micUnavailable", { err: e.message || e })); }
  }

  if (err && !d) return <div className="card" style={{ borderColor: "var(--danger)", color: "var(--danger)" }}>{err}</div>;
  if (!d) return <div className="card"><p className="muted">{t("dash.loading")}</p></div>;

  const totalTasks = d.totals.tasks || 0;
  const pct = (n) => (totalTasks ? (n / totalTasks) * 100 : 0);
  const sections = config?.sections || [];
  const hide = config?.hide || [];
  const vis = (s) => (sections.length === 0 || sections.includes(s)) && !hide.includes(s);
  const chipBits = config && [
    config.project, config.status && statusLabel(config.status), config.severity && `${config.severity} sev`,
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
            <span className="muted">{t("dash.quickViews")}</span>
            {presets.teams.length > 0 && (
              <select className="teamsel" value={team} onChange={e => setTeam(e.target.value)} title={t("dash.teamSelTitle")}>
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
            placeholder={t("dash.cmdPlaceholder")} />
          <button onClick={() => runCmd()} disabled={busy}>{busy ? "…" : t("dash.run")}</button>
          <button onClick={toggleMic} title={t("dash.micTitle")}
            style={{ background: recording ? "#c0392b" : "#1f3864" }}>{recording ? "■" : "🎙"}</button>
        </div>
        {config && (
          <div className="activecfg">
            <span className="tag view">{t("dash.viewLabel", { summary: config.summary || t("dash.custom") })}</span>
            {chipBits.map((b, i) => <span key={i} className="tag">{b}</span>)}
            <button className="link" onClick={loadFull}>{t("dash.clear")}</button>
            <span style={{ flex: 1 }} />
            <input className="savein" value={saveName} onChange={e => setSaveName(e.target.value)} placeholder={t("dash.savePlaceholder")} />
            <button onClick={saveCurrent} disabled={!saveName.trim()}>{t("dash.saveView")}</button>
          </div>
        )}
        {views.length > 0 && (
          <div className="savedviews">
            <span className="muted">{t("dash.saved")}</span>
            {views.map(v => (
              <span key={v.id} className="viewchip">
                <button className="vname" onClick={() => applySaved(v)}>{v.name}</button>
                {/* delete: the creator, or manager+ (shared/legacy views have no creator) */}
                {(!me || isManagerUp(me) || v.created_by === me.id) && (
                  <button className="vx" onClick={() => removeView(v.id)} title={t("dash.deleteViewTitle")}>×</button>
                )}
              </span>
            ))}
          </div>
        )}
        {err && <p className="muted" style={{ color: "var(--danger)", margin: "6px 0 0" }}>{err}</p>}
      </div>

      <div className="kpis">
        <div className="kpi"><div className="n">{d.totals.projects}</div><div className="l">{t("kpi.projects")}</div></div>
        <div className="kpi"><div className="n">{d.totals.tasks}</div><div className="l">{t("kpi.tasks")}</div></div>
        <div className="kpi"><div className="n">{d.overall_progress}%</div><div className="l">{t("kpi.overallProgress")}</div></div>
        <div className={"kpi" + (d.open_blockers ? " warn" : "")}><div className="n">{d.open_blockers}</div><div className="l">{t("kpi.openBlockers")}</div></div>
        <div className={"kpi" + (d.open_risks ? " warn" : "")}><div className="n">{d.open_risks}</div><div className="l">{t("kpi.openRisks")}</div></div>
      </div>

      {vis("trends") && <div className="row" style={{ alignItems: "stretch" }}>
        <div className="card" style={{ flex: 1 }}>
          <div className="h3">{t("dash.progressOverTime")}</div>
          <TrendChart points={d.trends?.progress} max={100} unit="%" color="var(--trend-good)" />
        </div>
        <div className="card" style={{ flex: 1 }}>
          <div className="h3">{t("dash.blockersOverTime")}</div>
          <TrendChart points={d.trends?.blockers} unit="" color="var(--danger)" step />
        </div>
      </div>}

      {vis("delivery") && <div className="card">
        <div className="h3">{t("dash.deliveryStatus")}</div>
        <div className="segbar">
          {STATUS_SEG.map(s => pct(d.task_status_counts[s]) > 0 &&
            <div key={s} className={"seg s_" + s} style={{ width: pct(d.task_status_counts[s]) + "%" }}
              title={`${statusLabel(s)}: ${d.task_status_counts[s]}`} />)}
        </div>
        <div className="seglegend">
          {STATUS_SEG.map(s => (
            <span key={s}><span className={"sw seg s_" + s} />{statusLabel(s)}: {d.task_status_counts[s]}</span>
          ))}
        </div>
      </div>}

      {vis("per_project") && <div className="card">
        <div className="h3">{t("dash.projectsTitle")}</div>
        <table>
          <thead><tr><th>{t("table.project")}</th><th>{t("table.status")}</th><th>{t("table.progress")}</th><th>{t("table.tasks")}</th><th>{t("table.openBlockers")}</th></tr></thead>
          <tbody>
            {d.per_project.map(p => (
              <tr key={p.id}>
                <td>{p.name}{p.name_ja && <div className="muted">{p.name_ja}</div>}</td>
                <td><span className={"st " + p.status}>{statusLabel(p.status) || p.status}</span></td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div className="progress"><div style={{ width: p.avg_progress + "%" }} /></div>
                    <span className="muted">{p.avg_progress}%</span>
                  </div>
                </td>
                <td>{t("table.doneOfTotal", { done: p.done_task_count, total: p.task_count })}</td>
                <td>{p.open_blocker_count > 0 ? <span className="tag blocked">{p.open_blocker_count}</span> : <span className="muted">0</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}

      {vis("plan") && d.plan && <div className="card">
        <div className="h3">{t("dash.planTitle")}</div>
        <table>
          <thead><tr><th>{t("table.project")}</th><th>{t("table.expected")}</th><th>{t("table.actual")}</th><th>{t("table.delta")}</th><th>{t("table.targetDate")}</th></tr></thead>
          <tbody>
            {d.plan.per_project.map(p => (
              <tr key={p.id}>
                <td>{p.name}{p.name_ja && <div className="muted">{p.name_ja}</div>}</td>
                <td>{p.expected_pct == null ? <span className="muted">{t("plan.noDates")}</span> : `${p.expected_pct}%`}</td>
                <td>{p.actual_pct}%</td>
                <td>{p.delta == null ? <span className="muted">-</span> : (
                  <span className={"tag" + (p.delta < 0 ? " blocked" : "")}
                    style={p.delta >= 0 ? { color: "var(--trend-good)" } : undefined}>
                    {p.delta > 0 ? `+${p.delta}` : p.delta}%
                  </span>
                )}</td>
                <td className="muted">
                  {p.target_date || "-"}
                  {p.days_left != null && ` (${p.days_left >= 0 ? t("plan.daysLeft", { n: p.days_left }) : t("plan.daysOver", { n: -p.days_left })})`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {(d.plan.overdue?.length || d.plan.at_risk?.length || d.plan.stale?.length) ? (
          <div className="row" style={{ alignItems: "stretch", marginTop: 10 }}>
            {d.plan.overdue?.length > 0 && <div style={{ flex: 1 }}>
              <div className="h3">{t("plan.overdue", { n: d.plan.overdue.length })}</div>
              <div className="feed">
                {d.plan.overdue.map(t2 => (
                  <div key={t2.id} className="item">
                    <span className="sevdot high" />{t2.title}
                    <div className="muted">{t2.project}{t2.assignee ? ` · ${t2.assignee}` : ""} · {t2.progress_pct}% · {t("plan.daysOver", { n: -t2.days_left })}</div>
                  </div>
                ))}
              </div>
            </div>}
            {d.plan.at_risk?.length > 0 && <div style={{ flex: 1 }}>
              <div className="h3">{t("plan.atRisk", { n: d.plan.at_risk.length })}</div>
              <div className="feed">
                {d.plan.at_risk.map(t2 => (
                  <div key={t2.id} className="item">
                    <span className="sevdot medium" />{t2.title}
                    <div className="muted">{t2.project}{t2.assignee ? ` · ${t2.assignee}` : ""} · {t2.progress_pct}% · {t("dash.due", { date: t2.due_date })}</div>
                  </div>
                ))}
              </div>
            </div>}
            {d.plan.stale?.length > 0 && <div style={{ flex: 1 }}>
              <div className="h3">{t("plan.stale", { n: d.plan.stale.length })}</div>
              <div className="feed">
                {d.plan.stale.map(t2 => (
                  <div key={t2.id} className="item">
                    {t2.title}
                    <div className="muted">{t2.project}{t2.assignee ? ` · ${t2.assignee}` : ""} · {t2.days_since_update == null ? t("plan.neverReported") : t("plan.lastUpdate", { n: t2.days_since_update })}</div>
                  </div>
                ))}
              </div>
            </div>}
          </div>
        ) : <p className="muted">{t("plan.allOnTrack")}</p>}
      </div>}

      {vis("per_team") && (d.per_team?.length > 0) && <div className="card">
        <div className="h3">{t("dash.teams")}</div>
        <table>
          <thead><tr><th>{t("table.team")}</th><th>{t("table.department")}</th><th>{t("table.members")}</th><th>{t("table.progress")}</th><th>{t("table.tasks")}</th><th>{t("table.openBlockers")}</th></tr></thead>
          <tbody>
            {d.per_team.map(t2 => (
              <tr key={t2.team}>
                <td>{t2.team}</td>
                <td className="muted">{t2.department || "-"}</td>
                <td className="muted">{t2.members.join(", ")}</td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div className="progress"><div style={{ width: t2.avg_progress + "%" }} /></div>
                    <span className="muted">{t2.avg_progress}%</span>
                  </div>
                </td>
                <td>{t("table.doneOfTotal", { done: t2.done_task_count, total: t2.task_count })}</td>
                <td>{t2.open_blocker_count > 0 ? <span className="tag blocked">{t2.open_blocker_count}</span> : <span className="muted">0</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}

      {vis("per_person") && (d.per_person?.length > 0) && <div className="card">
        <div className="h3">{t("dash.people")}</div>
        <table>
          <thead><tr><th>{t("table.person")}</th><th>{t("table.team")}</th><th>{t("table.progress")}</th><th>{t("table.tasks")}</th><th>{t("table.openBlockers")}</th><th>{t("table.nextSteps")}</th></tr></thead>
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
                <td>{t("table.doneOfTotal", { done: p.done_task_count, total: p.task_count })}</td>
                <td>{p.open_blocker_count > 0 ? <span className="tag blocked">{p.open_blocker_count}</span> : <span className="muted">0</span>}</td>
                <td>{p.next_step_count > 0 ? p.next_step_count : <span className="muted">0</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}

      {(vis("blockers") || vis("risks")) && <div className="row" style={{ alignItems: "stretch" }}>
        {vis("blockers") && <div className="card" style={{ flex: 1 }}>
          <div className="h3">{t("dash.openBlockersCount", { n: d.open_blockers })}</div>
          {d.blockers_list.length === 0 ? <p className="muted">{t("dash.noneOpen")}</p> : (
            <div className="feed">
              {d.blockers_list.map((b, i) => (
                <div key={i} className="item">
                  <span className={"sevdot " + b.severity} />{b.description}
                  <div className="muted">{b.severity ? t(`severity.${b.severity}`) : ""}{b.task ? ` · ${b.task}` : ""}{b.owner ? ` · ${b.owner}` : ""}</div>
                </div>
              ))}
            </div>
          )}
        </div>}
        {vis("risks") && <div className="card" style={{ flex: 1 }}>
          <div className="h3">{t("dash.risksCount", { n: d.open_risks })}</div>
          {d.risks_list.length === 0 ? <p className="muted">{t("dash.noneFlagged")}</p> : (
            <div className="feed">
              {d.risks_list.map((r, i) => (
                <div key={i} className="item">
                  {r.description}
                  <div className="muted">{r.impact ? t("risk.impact", { impact: r.impact }) : ""}{r.mitigation ? ` · ${t("risk.mitigation", { mitigation: r.mitigation })}` : ""}{r.task ? ` · ${r.task}` : ""}</div>
                </div>
              ))}
            </div>
          )}
        </div>}
      </div>}

      {(vis("activity") || vis("next_steps")) && <div className="row" style={{ alignItems: "stretch" }}>
        {vis("activity") && <div className="card" style={{ flex: 1 }}>
          <div className="h3">{t("dash.recentActivity")}</div>
          {d.recent_updates.length === 0 ? <p className="muted">{t("dash.noUpdates")}</p> : (
            <div className="feed">
              {d.recent_updates.map(u => (
                <div key={u.id} className={"item" + (u.source === "voice" ? " voice" : "")}>
                  {u.snippet || t("dash.noText")}
                  <div className="muted">
                    {new Date(u.created_at).toLocaleDateString()} · {u.task || t("dash.noTask")}
                    {u.author ? ` · ${u.author}` : ""} · {u.source ? t(`source.${u.source}`) : u.source}{u.language === "ja" ? " · JA" : ""}
                    {u.blocker_count ? ` · ${t("dash.blockerCount", { n: u.blocker_count })}` : ""}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>}
        {vis("next_steps") && <div className="card" style={{ flex: 1 }}>
          <div className="h3">{t("dash.upcomingNextSteps")}</div>
          {d.upcoming_next_steps.length === 0 ? <p className="muted">{t("dash.nothingQueued")}</p> : (
            <div className="feed">
              {d.upcoming_next_steps.map((n, i) => (
                <div key={i} className="item">
                  {n.description}
                  <div className="muted">{n.due_date ? t("dash.due", { date: n.due_date }) : t("dash.noDate")}{n.owner ? ` · ${n.owner}` : ""}{n.task ? ` · ${n.task}` : ""}</div>
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
  const { t } = useLang();
  if (!points || points.length === 0) return <p className="muted">{t("dash.noHistory")}</p>;
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
  const { t } = useLang();
  const [name, setName] = useState("");
  const [owner, setOwner] = useState("");
  async function submit() {
    if (!name.trim()) return;
    await api.createProject({ name, owner: owner || null });
    setName(""); setOwner(""); onDone();
  }
  return (
    <div className="card">
      <h2>{t("form.addProject")}</h2>
      <div className="row">
        <div><label>{t("form.name")}</label><input value={name} onChange={e => setName(e.target.value)} /></div>
        <div><label>{t("form.owner")}</label><input value={owner} onChange={e => setOwner(e.target.value)} /></div>
      </div>
      <button onClick={submit}>{t("form.saveProject")}</button>
    </div>
  );
}

function TaskForm({ projects, onDone }) {
  const { t } = useLang();
  const [form, setForm] = useState({ project_id: "", title: "", assignee: "", status: "not_started", progress_pct: 0, due_date: "" });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  async function submit() {
    if (!form.project_id || !form.title.trim()) return;
    await api.createTask({ ...form, project_id: Number(form.project_id), progress_pct: Number(form.progress_pct),
                           due_date: form.due_date || null });
    setForm({ project_id: "", title: "", assignee: "", status: "not_started", progress_pct: 0, due_date: "" }); onDone();
  }
  return (
    <div className="card">
      <h2>{t("form.addTask")}</h2>
      <div className="row">
        <div><label>{t("form.project")}</label>
          <select value={form.project_id} onChange={e => set("project_id", e.target.value)}>
            <option value="">{t("form.selectEllipsis")}</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
        <div><label>{t("form.title")}</label><input value={form.title} onChange={e => set("title", e.target.value)} /></div>
        <div><label>{t("form.assignee")}</label><input value={form.assignee} onChange={e => set("assignee", e.target.value)} /></div>
      </div>
      <div className="row">
        <div><label>{t("form.status")}</label>
          <select value={form.status} onChange={e => set("status", e.target.value)}>
            {STATUS.map(s => <option key={s} value={s}>{t(`status.${s}`)}</option>)}
          </select>
        </div>
        <div><label>{t("form.progressPct")}</label><input type="number" min="0" max="100" value={form.progress_pct} onChange={e => set("progress_pct", e.target.value)} /></div>
        <div><label>{t("form.dueDate")}</label><input type="date" value={form.due_date} onChange={e => set("due_date", e.target.value)} /></div>
      </div>
      <button onClick={submit}>{t("form.saveTask")}</button>
    </div>
  );
}

function UpdateForm({ tasks, onDone, me, people = [] }) {
  const { t } = useLang();
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
      <h2>{t("form.addUpdate")}</h2>
      <div className="row">
        <div><label>{t("form.task")}</label>
          <select value={form.task_id} onChange={e => set("task_id", e.target.value)}>
            <option value="">{t("form.selectEllipsis")}</option>
            {tasks.map(t2 => <option key={t2.id} value={t2.id}>{t2.title}</option>)}
          </select>
        </div>
        <AuthorField me={me} people={people} value={form.author} onChange={v => set("author", v)} />
        <div><label>{t("form.language")}</label>
          <select value={form.language} onChange={e => set("language", e.target.value)}>
            <option value="en">{t("lang.english")}</option><option value="ja">{t("lang.japanese")}</option>
          </select>
        </div>
      </div>
      <label>{t("form.updateText")}</label>
      <textarea rows="2" value={form.raw_text} onChange={e => set("raw_text", e.target.value)} />
      <div className="row">
        <div><label>{t("form.blockerOptional")}</label><input value={blocker.description} onChange={e => setBlocker(b => ({ ...b, description: e.target.value }))} /></div>
        <div><label>{t("form.severity")}</label>
          <select value={blocker.severity} onChange={e => setBlocker(b => ({ ...b, severity: e.target.value }))}>
            {SEVERITY.map(s => <option key={s} value={s}>{t(`severity.${s}`)}</option>)}
          </select>
        </div>
      </div>
      <div className="row">
        <div><label>{t("form.nextStepOptional")}</label><input value={nextStep.description} onChange={e => setNextStep(n => ({ ...n, description: e.target.value }))} /></div>
        <div><label>{t("form.owner")}</label><input value={nextStep.owner} onChange={e => setNextStep(n => ({ ...n, owner: e.target.value }))} /></div>
      </div>
      <button className="secondary" onClick={submit}>{t("form.saveUpdate")}</button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AI flow (week 2-4): speak OR type a free-form update -> (week 4) transcribe via
// local Whisper -> local LLM proposes a structured draft -> human edits the
// confirmation blocks -> save through the existing POST /updates. Nothing is saved
// until "Confirm & save".
// ---------------------------------------------------------------------------
// Guided capture (review sprint): what a draft is missing that would make the update
// more useful downstream. Pure derivation from the extract response; the person can
// dismiss the hints and confirm anyway. Returns i18n keys.
export function captureHints(draft) {
  if (!draft) return [];
  const isISO = (s) => /^\d{4}-\d{2}-\d{2}$/.test(s || "");
  const hints = [];
  if (draft.progress_pct == null) hints.push("hint.progress");
  if (!draft.status) hints.push("hint.status");
  if (!draft.next_steps?.length) hints.push("hint.nextStep");
  if (draft.blockers?.some(b => !b.owner)) hints.push("hint.blockerOwner");
  if (draft.next_steps?.length && draft.next_steps.every(n => !isISO(n.due_date))) hints.push("hint.dueDate");
  if ((draft.confidence ?? 1) < 0.6) hints.push("hint.lowConfidence");
  return hints;
}

function AiUpdateForm({ tasks, onDone, me, people = [] }) {
  const { t } = useLang();
  const [text, setText] = useState("");
  const [language, setLanguage] = useState("en");
  const [author, setAuthor] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [draft, setDraft] = useState(null); // null = no proposal yet
  const [hideHints, setHideHints] = useState(false);
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
      setText(t2 => (t2 ? t2 + " " : "") + r.text);
      if (r.language === "en" || r.language === "ja") setLanguage(r.language);
      setSource("voice");
    } catch (e) {
      setErr(e.message || t("error.transcribe"));
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
        stream.getTracks().forEach(t2 => t2.stop());
        setRecording(false);
        sendAudio(new Blob(chunks, { type: rec.mimeType || "audio/webm" }));
      };
      recorderRef.current = rec;
      rec.start();
      setRecording(true);
    } catch (e) {
      setErr(t("ai.micUnavailable", { err: e.message || e }));
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
      setDraft(d); setHideHints(false);
    } catch (e) {
      setErr(e.message || t("error.extract"));
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
      <h2>{t("ai.title")}</h2>
      <div className="row" style={{ alignItems: "center", marginBottom: 6 }}>
        <button onClick={toggleRecord} disabled={transcribing}
          style={{ marginTop: 0, background: recording ? "#c0392b" : "#1f3864" }}>
          {recording ? t("ai.stopRecording") : t("ai.record")}
        </button>
        <label style={{ margin: 0, fontWeight: 400, color: "var(--muted)" }}>
          {t("ai.orUpload")}&nbsp;
          <input type="file" accept="audio/*" onChange={onPickFile} disabled={transcribing}
            style={{ width: "auto", display: "inline-block", padding: 2, border: 0 }} />
        </label>
        {transcribing && <span className="muted">{t("ai.transcribing")}</span>}
        {source === "voice" && !transcribing && <span className="tag done">{t("ai.fromVoice")}</span>}
      </div>
      <label>{t("ai.updateTextLabel")}</label>
      <textarea rows="3" value={text} onChange={e => setText(e.target.value)}
        placeholder={t("ai.updateTextPlaceholder")} />
      <div className="row">
        <div><label>{t("form.language")}</label>
          <select value={language} onChange={e => setLanguage(e.target.value)}>
            <option value="en">{t("lang.english")}</option><option value="ja">{t("lang.japanese")}</option>
          </select>
        </div>
        <AuthorField me={me} people={people} value={author} onChange={setAuthor} />
      </div>
      <button onClick={extract} disabled={busy || !text.trim()}>
        {busy ? t("ai.extracting") : t("ai.extract")}
      </button>
      {err && <p style={{ color: "var(--danger)", marginBottom: 0 }}>{err}</p>}

      {draft && (
        <div style={{ marginTop: 16, borderTop: "1px solid var(--border-soft)", paddingTop: 12 }}>
          <div className="row" style={{ alignItems: "center" }}>
            <h3 style={{ margin: 0, fontSize: 15 }}>{t("ai.confirmTitle")}</h3>
            <span className="muted">{t("ai.confidence", { pct: Math.round((draft.confidence || 0) * 100) })}</span>
          </div>

          {draft.unknown_project &&
            <p className="tag blocked">{t("ai.unknownProject")}</p>}
          {draft.unknown_task && !draft.unknown_project &&
            <p className="tag blocked">{t("ai.unknownTask", { task: draft.task })}</p>}

          {!hideHints && captureHints(draft).length > 0 && (
            <div style={{ border: "1px solid var(--border-soft)", borderLeft: "3px solid var(--accent)",
                          borderRadius: 6, padding: "8px 12px", margin: "8px 0" }}>
              <div className="row" style={{ alignItems: "center" }}>
                <b style={{ fontSize: 13 }}>{t("hint.title")}</b>
                <span style={{ flex: 1 }} />
                <button className="link" onClick={() => setHideHints(true)}>{t("hint.dismiss")}</button>
              </div>
              <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                {captureHints(draft).map(k => <li key={k} className="muted" style={{ fontSize: 13 }}>{t(k)}</li>)}
              </ul>
            </div>
          )}

          <div className="row">
            <div><label>{t("ai.projectMatched")}</label>
              <input value={draft.project === "unknown" ? t("ai.unknown") : draft.project} readOnly />
            </div>
            <div><label>{t("form.task")}</label>
              <select value={draft.task_id ?? ""} onChange={e => setField("task_id", e.target.value ? Number(e.target.value) : null)}>
                <option value="">{t("ai.noTaskOption")}</option>
                {tasks.map(t2 => <option key={t2.id} value={t2.id}>{t2.title}</option>)}
              </select>
            </div>
          </div>
          <div className="row">
            <div><label>{t("form.status")}</label>
              <select value={draft.status ?? ""} onChange={e => setField("status", e.target.value || null)}>
                <option value="">{t("common.none")}</option>
                {STATUS.map(s => <option key={s} value={s}>{t(`status.${s}`)}</option>)}
              </select>
            </div>
            <div><label>{t("form.progressPct")}</label>
              <input type="number" min="0" max="100" value={draft.progress_pct ?? ""}
                onChange={e => setField("progress_pct", e.target.value === "" ? null : Number(e.target.value))} />
            </div>
            <div><label>{t("ai.period")}</label>
              <input value={draft.period ?? ""} onChange={e => setField("period", e.target.value || null)} />
            </div>
          </div>
          {draft.owners?.length > 0 &&
            <p className="muted">{t("ai.ownersDetected", { names: draft.owners.join(", ") })}</p>}

          <DraftList title={t("ai.blockers")} items={draft.blockers}
            onAdd={() => addItem("blockers", { description: "", severity: "medium", owner: "", status: "open" })}
            onDrop={i => dropItem("blockers", i)}
            render={(b, i) => (
              <div className="row">
                <div style={{ flex: 3 }}><input placeholder={t("draftlist.descPlaceholder")} value={b.description}
                  onChange={e => editItem("blockers", i, { description: e.target.value })} /></div>
                <div><select value={b.severity ?? "medium"} onChange={e => editItem("blockers", i, { severity: e.target.value })}>
                  {SEVERITY.map(s => <option key={s} value={s}>{t(`severity.${s}`)}</option>)}</select></div>
                <div><input placeholder={t("draftlist.ownerPlaceholder")} value={b.owner ?? ""} onChange={e => editItem("blockers", i, { owner: e.target.value })} /></div>
                <div><select value={b.status ?? "open"} onChange={e => editItem("blockers", i, { status: e.target.value })}>
                  <option value="open">{t("draftlist.open")}</option><option value="resolved">{t("draftlist.resolved")}</option></select></div>
              </div>
            )} />

          <DraftList title={t("ai.risks")} items={draft.risks}
            onAdd={() => addItem("risks", { description: "", likelihood: "", impact: "", mitigation: "", owner: "" })}
            onDrop={i => dropItem("risks", i)}
            render={(r, i) => (
              <>
                <div className="row">
                  <div style={{ flex: 2 }}><input placeholder={t("draftlist.descPlaceholder")} value={r.description}
                    onChange={e => editItem("risks", i, { description: e.target.value })} /></div>
                  <div><input placeholder={t("draftlist.likelihoodPlaceholder")} value={r.likelihood ?? ""} onChange={e => editItem("risks", i, { likelihood: e.target.value })} /></div>
                  <div><input placeholder={t("draftlist.impactPlaceholder")} value={r.impact ?? ""} onChange={e => editItem("risks", i, { impact: e.target.value })} /></div>
                </div>
                <div className="row">
                  <div><input placeholder={t("draftlist.mitigationPlaceholder")} value={r.mitigation ?? ""} onChange={e => editItem("risks", i, { mitigation: e.target.value })} /></div>
                  <div><input placeholder={t("draftlist.ownerPlaceholder")} value={r.owner ?? ""} onChange={e => editItem("risks", i, { owner: e.target.value })} /></div>
                </div>
              </>
            )} />

          <DraftList title={t("ai.nextSteps")} items={draft.next_steps}
            onAdd={() => addItem("next_steps", { description: "", owner: "", due_date: "" })}
            onDrop={i => dropItem("next_steps", i)}
            render={(n, i) => (
              <div className="row">
                <div style={{ flex: 3 }}><input placeholder={t("draftlist.descPlaceholder")} value={n.description}
                  onChange={e => editItem("next_steps", i, { description: e.target.value })} /></div>
                <div><input placeholder={t("draftlist.ownerPlaceholder")} value={n.owner ?? ""} onChange={e => editItem("next_steps", i, { owner: e.target.value })} /></div>
                <div><input placeholder={t("draftlist.duePlaceholder")} value={n.due_date ?? ""} onChange={e => editItem("next_steps", i, { due_date: e.target.value || null })} /></div>
              </div>
            )} />

          <div className="row" style={{ marginTop: 8 }}>
            <button className="secondary" onClick={confirm}>{t("ai.confirmSave")}</button>
            <button onClick={() => setDraft(null)} style={{ background: "#888" }}>{t("ai.discard")}</button>
          </div>
        </div>
      )}
    </div>
  );
}

function DraftList({ title, items, render, onAdd, onDrop }) {
  const { t } = useLang();
  return (
    <div style={{ marginTop: 10 }}>
      <label>{title}</label>
      {items.length === 0 && <p className="muted" style={{ margin: "2px 0" }}>{t("draftlist.none")}</p>}
      {items.map((it, i) => (
        <div key={i} style={{ display: "flex", gap: 6, alignItems: "flex-start", marginBottom: 6 }}>
          <div style={{ flex: 1 }}>{render(it, i)}</div>
          <button onClick={() => onDrop(i)} style={{ background: "#c0392b", marginTop: 0, padding: "7px 10px" }}>×</button>
        </div>
      ))}
      <button onClick={onAdd} style={{ background: "var(--chip-bg)", color: "var(--text)", marginTop: 4, padding: "5px 10px" }}>{t("draftlist.add")}</button>
    </div>
  );
}

function UpdatesTable({ updates, tasks }) {
  const { lang, t } = useLang();
  const taskTitle = (id) => tasks.find(t2 => t2.id === id)?.title || t("dash.noTask");
  // On-demand translation into the current UI language. Nothing is stored: the
  // original stays the record, the translation renders underneath it.
  const [translations, setTranslations] = useState({});
  const [busyId, setBusyId] = useState(null);
  async function translate(u) {
    setBusyId(u.id);
    try {
      const r = await api.translateUpdate(u.id, lang);
      setTranslations(m => ({ ...m, [u.id]: r.text }));
    } catch {
      setTranslations(m => ({ ...m, [u.id]: t("updates.translateFailed") }));
    } finally {
      setBusyId(null);
    }
  }
  return (
    <div className="card">
      <h2>{t("updates.title")}</h2>
      {updates.length === 0 ? <p className="muted">{t("updates.empty")}</p> : (
        <table>
          <thead><tr><th>{t("table.when")}</th><th>{t("table.task")}</th><th>{t("table.author")}</th><th>{t("table.lang")}</th><th>{t("table.text")}</th><th>{t("table.blockers")}</th><th>{t("table.nextSteps")}</th></tr></thead>
          <tbody>
            {updates.map(u => (
              <tr key={u.id}>
                <td className="muted">{new Date(u.created_at).toLocaleString()}</td>
                <td>{taskTitle(u.task_id)}</td>
                <td>{u.author || "-"}</td>
                <td>{u.language}</td>
                <td>
                  {u.raw_text || "-"}
                  {u.raw_text && u.language !== lang && !translations[u.id] && (
                    <div><button className="link" disabled={busyId === u.id} onClick={() => translate(u)}>
                      {busyId === u.id ? t("updates.translating") : t("updates.translate")}
                    </button></div>
                  )}
                  {translations[u.id] && <div className="muted">{translations[u.id]}</div>}
                </td>
                <td>{u.blockers.map(b => <span key={b.id} className={`tag ${b.severity === "high" ? "blocked" : ""}`}>{b.description} ({t(`severity.${b.severity}`)})</span>)}</td>
                <td>{u.next_steps.map(n => <span key={n.id} className="tag">{n.description}{n.owner ? ` · ${n.owner}` : ""}</span>)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
