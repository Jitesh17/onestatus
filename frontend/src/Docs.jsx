import React from "react";

// Static in-app documentation. No API calls; safe to render for every role.
// Content rule: plain sentences, no em dashes, numbers match TESTING.md.
export default function DocsPage() {
  return (
    <>
      <div className="card">
        <h2>What OneStatus is</h2>
        <p>
          OneStatus turns spoken or typed status updates into a live project dashboard.
          A team member says what they did, in English, Japanese, or a mix. The app
          extracts the structured facts (task, progress, blockers, risks, next steps),
          shows them for review, and only saves after the person confirms. Managers read
          the dashboard instead of chasing updates.
        </p>
        <p className="muted">
          Everything runs on one server on the office network. The only optional outside
          call is a cloud LLM API, and the app labels it clearly when that mode is on.
        </p>
      </div>

      <div className="card">
        <h2>How an update becomes a status</h2>
        <ol>
          <li>
            <b>Voice to text (local).</b> Audio recorded in the browser is sent to the
            backend and transcribed by Whisper (faster-whisper on CTranslate2). This
            always runs on the server itself, on CPU by default. Audio never goes to
            any external service. Typed updates skip this step.
          </li>
          <li>
            <b>Grounding.</b> Before asking the language model anything, the backend
            builds a "world": the list of known projects (English and Japanese names),
            their tasks, and the people roster. The model is told to match against these
            exact names and to answer "unknown" rather than invent a project.
          </li>
          <li>
            <b>Extraction.</b> The update text plus the world go to the configured LLM
            with a fixed rulebook prompt and JSON-only output. The rules cover the hard
            cases: inferring status from phrasing, telling blockers (happening now) from
            risks (might happen), keeping descriptions in the original language, and
            never inventing calendar dates. Vague dates like "Friday" or "金曜日" are
            kept as written.
          </li>
          <li>
            <b>Validation.</b> The model's answer is not trusted as-is. Code checks every
            field: project and task must be known names (with a fuzzy match to rescue
            near-miss spellings), status and severity must come from fixed lists,
            progress must be 0 to 100, and a person is only credited as an owner if
            their name literally appears in the update text. Anything else is dropped.
          </li>
          <li>
            <b>Human review.</b> The cleaned draft is shown in an editor with a
            confidence score. Nothing is saved yet. The person fixes anything the model
            got wrong, or discards the draft.
          </li>
          <li>
            <b>Save.</b> On confirm, the update is stored, the task's status and progress
            move with it, and the dashboard reflects it immediately. The update is signed
            by the logged-in account.
          </li>
        </ol>
      </div>

      <div className="card">
        <h2>The dashboard</h2>
        <p>
          The dashboard is computed from saved updates on every load: task counts,
          overall progress, open blockers by severity, risks, per-project and per-team
          and per-person tables, recent activity, and trend charts built from the update
          history.
        </p>
        <p>There are three ways to shape it:</p>
        <ul>
          <li>
            <b>Quick views.</b> Preset buttons (executive summary, team view, per-person
            workload). These are fixed configurations, no AI involved, so they always do
            the same thing.
          </li>
          <li>
            <b>The command bar.</b> Type a request like "only blocked tasks in Website
            Redesign" or "先週のブロッカーを見せて". The same LLM turns it into a view
            configuration (filters, sections, sort, time window), which is validated
            against the known projects, teams, and people before it is applied. A summary
            line shows what it understood, and Clear resets everything.
          </li>
          <li>
            <b>Saved views.</b> Any configuration can be saved under a name and reopened
            with one click.
          </li>
        </ul>
      </div>

      <div className="card">
        <h2>Architecture</h2>
        <table>
          <thead><tr><th>Part</th><th>What it is</th><th>Where it runs</th></tr></thead>
          <tbody>
            <tr><td>Frontend</td><td>React single-page app, served by nginx</td><td>Office server</td></tr>
            <tr><td>Backend</td><td>FastAPI (Python), one process</td><td>Office server</td></tr>
            <tr><td>Database</td><td>SQLite file (Postgres supported)</td><td>Office server</td></tr>
            <tr><td>Speech to text</td><td>Whisper via faster-whisper</td><td>Office server, always</td></tr>
            <tr><td>Language model</td><td>Ollama (local), or OpenAI compatible, or Anthropic</td><td>Server GPU/CPU, or a cloud API</td></tr>
          </tbody>
        </table>
        <p>
          The pieces run as Docker containers behind nginx, which serves the frontend and
          proxies <code>/api/</code> to the backend. There is no external identity
          service, no telemetry, and no data sync. The database is a single file on the
          server.
        </p>
        <h3>Accounts and roles</h3>
        <p>
          Login is handled by the app itself: local accounts, bcrypt password hashes, and
          server-side sessions in an HttpOnly cookie. Roles are enforced by the server on
          every endpoint, not hidden by the UI.
        </p>
        <table>
          <thead><tr><th>Role</th><th>Can do</th></tr></thead>
          <tbody>
            <tr><td>Member</td><td>Post updates as themselves, use the dashboard</td></tr>
            <tr><td>Manager</td><td>Also create projects and tasks, post on behalf of others</td></tr>
            <tr><td>Admin</td><td>Also manage accounts, the people roster, and settings</td></tr>
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Features at a glance</h2>
        <ul>
          <li>Voice or text input, English and Japanese, including mixed sentences</li>
          <li>Review-before-save editor with a confidence score on every draft</li>
          <li>Live KPIs, blocker and progress trend charts, per-project / team / person views</li>
          <li>Natural-language dashboard commands in both languages, plus one-click preset views</li>
          <li>Saved custom views, dark mode</li>
          <li>Per-user login with roles; every update signed by its author</li>
          <li>Admin panel for accounts and the team roster, no database access needed</li>
          <li>Switch the language model or provider live from Settings, no restart</li>
        </ul>
      </div>

      <div className="card">
        <h2>Choosing where the language model runs</h2>
        <p>
          The extraction and command-bar steps need a language model. Three options, all
          switchable in Settings (admin only). The badge in the header always shows the
          current mode, so nobody is confused about where text goes.
        </p>
        <table>
          <thead><tr><th>Mode</th><th>Typical speed per update</th><th>Data note</th></tr></thead>
          <tbody>
            <tr><td>Local (Ollama) on CPU</td><td>3 to 10 seconds</td><td>Nothing leaves the server</td></tr>
            <tr><td>Local (Ollama) on GPU</td><td>1 to 3 seconds</td><td>Nothing leaves the server</td></tr>
            <tr><td>Cloud API (OpenAI compatible or Anthropic)</td><td>1 to 2 seconds</td><td>Update text is sent to the API; audio and the database stay local</td></tr>
          </tbody>
        </table>
        <h3>Running on a machine with no GPU</h3>
        <p>
          A CPU-only Linux machine works out of the box. Whisper transcription runs on
          CPU either way. For extraction you can stay local and accept the 3 to 10 second
          wait, or point the app at a cloud API:
        </p>
        <ol>
          <li>Get an API key (for Anthropic: console.anthropic.com).</li>
          <li>Open Settings (gear icon, admin only) and pick "Anthropic API".</li>
          <li>Enter the model, for example <code>claude-haiku-4-5-20251001</code>, and paste the key.</li>
          <li>Save. The next extraction uses it, and the header badge switches to "cloud".</li>
        </ol>
        <p className="muted">
          The key is write-only: it is kept in the backend's memory (or its environment),
          never stored in the database, and never shown again in the UI. Switching back
          to local is the same two clicks.
        </p>
      </div>
    </>
  );
}
