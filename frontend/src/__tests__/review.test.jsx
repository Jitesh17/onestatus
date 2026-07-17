// Review-sprint features: plan-vs-actual dashboard section, guided capture hints,
// and on-demand update translation.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

vi.mock("../api.js", () => ({
  api: {
    onUnauthorized: null,
    me: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    listUsers: vi.fn(),
    listPeople: vi.fn(),
    listProjects: vi.fn(),
    listTasks: vi.fn(),
    listUpdates: vi.fn(),
    dashboard: vi.fn(),
    configureDashboard: vi.fn(),
    listPresets: vi.fn(),
    listViews: vi.fn(),
    getSettings: vi.fn(),
    listModels: vi.fn(),
    extractUpdate: vi.fn(),
    translateUpdate: vi.fn(),
    applyView: vi.fn(),
  },
}));

import { api } from "../api.js";
import App, { Dashboard, captureHints } from "../App.jsx";
import { LangProvider } from "../i18n.js";

const EMPTY_DASH = {
  totals: { projects: 0, tasks: 0, updates: 0 },
  task_status_counts: { not_started: 0, in_progress: 0, blocked: 0, done: 0 },
  overall_progress: 0,
  open_blockers: 0,
  open_blockers_by_severity: { low: 0, medium: 0, high: 0 },
  open_risks: 0,
  blockers_list: [],
  risks_list: [],
  recent_updates: [],
  upcoming_next_steps: [],
  per_project: [],
  per_team: [],
  per_person: [],
  trends: { progress: [], blockers: [] },
};

const PLAN_DASH = {
  ...EMPTY_DASH,
  plan: {
    per_project: [
      { id: 1, name: "Website Redesign", name_ja: null, start_date: "2026-06-01",
        target_date: "2026-09-30", expected_pct: 38, actual_pct: 42, delta: 4, days_left: 75 },
      { id: 2, name: "Mobile App v2", name_ja: null, start_date: "2026-05-15",
        target_date: "2026-08-31", expected_pct: 58, actual_pct: 40, delta: -18, days_left: 45 },
    ],
    overdue: [
      { id: 3, title: "Content migration", title_ja: null, project: "Website Redesign",
        assignee: "Sam", status: "in_progress", progress_pct: 45,
        due_date: "2026-07-14", days_left: -3, days_since_update: 4 },
    ],
    at_risk: [
      { id: 4, title: "Design review pipeline", title_ja: null, project: "Website Redesign",
        assignee: "Jordan", status: "blocked", progress_pct: 20,
        due_date: "2026-07-21", days_left: 4, days_since_update: 3 },
    ],
    stale: [
      { id: 5, title: "Legacy data validation", title_ja: null, project: "Data Pipeline Migration",
        assignee: "Jordan", status: "not_started", progress_pct: 0,
        due_date: null, days_left: null, days_since_update: null },
    ],
  },
};

const ADMIN_ME = { id: 1, username: "admin", role: "admin", person_id: null, author: "admin" };

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  api.me.mockResolvedValue(ADMIN_ME);
  api.listPeople.mockResolvedValue([]);
  api.listUsers.mockResolvedValue([ADMIN_ME]);
  api.listProjects.mockResolvedValue([]);
  api.listTasks.mockResolvedValue([]);
  api.listUpdates.mockResolvedValue([]);
  api.dashboard.mockResolvedValue(EMPTY_DASH);
  api.listViews.mockResolvedValue([]);
  api.listPresets.mockResolvedValue({ teams: [], presets: [] });
  api.getSettings.mockResolvedValue({ llm_provider: "ollama", llm_model: "qwen2.5:7b" });
});

describe("Plan vs actual section", () => {
  it("renders expected vs actual with delta badges and the three task lists", async () => {
    api.dashboard.mockResolvedValue(PLAN_DASH);
    render(<Dashboard tick={0} />);
    expect(await screen.findByText("Plan vs actual")).toBeInTheDocument();
    expect(screen.getByText("38%")).toBeInTheDocument();
    expect(screen.getByText("+4%")).toBeInTheDocument();
    expect(screen.getByText("-18%")).toBeInTheDocument();
    expect(screen.getByText("Overdue (1)")).toBeInTheDocument();
    expect(screen.getByText("Content migration")).toBeInTheDocument();
    expect(screen.getByText("At risk (1)")).toBeInTheDocument();
    expect(screen.getByText("No recent update (1)")).toBeInTheDocument();
    expect(screen.getByText(/never reported on/)).toBeInTheDocument();
  });

  it("shows the all-on-track line when the lists are empty", async () => {
    api.dashboard.mockResolvedValue({
      ...PLAN_DASH,
      plan: { ...PLAN_DASH.plan, overdue: [], at_risk: [], stale: [] },
    });
    render(<Dashboard tick={0} />);
    expect(await screen.findByText("Nothing overdue, at risk, or stale.")).toBeInTheDocument();
  });

  it("stays silent when the API has no plan block (older mocks and saved views)", async () => {
    render(<Dashboard tick={0} />);
    await screen.findByText("0%");
    expect(screen.queryByText("Plan vs actual")).not.toBeInTheDocument();
  });
});

describe("Guided capture hints", () => {
  it("captureHints flags what a sparse draft is missing and stays quiet on a full one", () => {
    const sparse = {
      progress_pct: null, status: null, next_steps: [],
      blockers: [{ description: "x", severity: "medium", owner: null }],
      confidence: 0.4,
    };
    expect(captureHints(sparse)).toEqual([
      "hint.progress", "hint.status", "hint.nextStep", "hint.blockerOwner", "hint.lowConfidence",
    ]);
    const full = {
      progress_pct: 60, status: "in_progress",
      next_steps: [{ description: "ship", owner: "Sam", due_date: "2026-07-24" }],
      blockers: [{ description: "x", severity: "medium", owner: "Alex" }],
      confidence: 0.9,
    };
    expect(captureHints(full)).toEqual([]);
    expect(captureHints(null)).toEqual([]);
  });

  it("shows the hints after extraction and hides them on dismiss", async () => {
    api.extractUpdate.mockResolvedValue({
      project: "unknown", task: null, task_id: null,
      unknown_project: false, unknown_task: false,
      status: "in_progress", progress_pct: null,
      blockers: [], risks: [], next_steps: [], owners: [], period: null,
      confidence: 0.9,
    });
    const user = userEvent.setup();
    render(<LangProvider><App /></LangProvider>);
    await user.click(await screen.findByRole("button", { name: "Capture" }));
    await user.type(screen.getByPlaceholderText(/Checkout flow rework/), "vague words");
    await user.click(screen.getByRole("button", { name: "Extract" }));
    expect(await screen.findByText("This update would be more useful with:")).toBeInTheDocument();
    expect(screen.getByText(/a progress percent/)).toBeInTheDocument();
    expect(screen.getByText(/a next step/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "dismiss" }));
    expect(screen.queryByText("This update would be more useful with:")).not.toBeInTheDocument();
  });
});

describe("Update translation", () => {
  it("offers Translate on updates in the other language and shows the result inline", async () => {
    api.listUpdates.mockResolvedValue([{
      id: 7, task_id: null, author: "Casey", language: "ja", source: "voice",
      created_at: "2026-07-16T10:00:00", confirmed: true,
      raw_text: "ETLカットオーバーモジュールは40パーセントです。",
      blockers: [], risks: [], next_steps: [],
    }]);
    api.translateUpdate.mockResolvedValue({
      update_id: 7, target: "en", text: "ETL cutover module is at 40 percent.",
    });
    const user = userEvent.setup();
    render(<LangProvider><App /></LangProvider>);
    await user.click(await screen.findByRole("button", { name: "Capture" }));
    await user.click(await screen.findByRole("button", { name: "Translate" }));
    await waitFor(() => expect(api.translateUpdate).toHaveBeenCalledWith(7, "en"));
    expect(await screen.findByText("ETL cutover module is at 40 percent.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Translate" })).not.toBeInTheDocument();
  });

  it("does not offer Translate when the update already matches the UI language", async () => {
    api.listUpdates.mockResolvedValue([{
      id: 8, task_id: null, author: "Sam", language: "en", source: "text",
      created_at: "2026-07-16T10:00:00", confirmed: true,
      raw_text: "Checkout rework at 60 percent.",
      blockers: [], risks: [], next_steps: [],
    }]);
    const user = userEvent.setup();
    render(<LangProvider><App /></LangProvider>);
    await user.click(await screen.findByRole("button", { name: "Capture" }));
    expect(await screen.findByText("Checkout rework at 60 percent.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Translate" })).not.toBeInTheDocument();
  });
});
