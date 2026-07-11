import { render, screen } from "@testing-library/react";
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
  },
}));

import { api } from "../api.js";
import App from "../App.jsx";
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

describe("Language toggle", () => {
  it("defaults to English and switches the whole page to Japanese on click", async () => {
    const user = userEvent.setup();
    render(<LangProvider><App /></LangProvider>);
    expect(await screen.findByText("Overall progress")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dashboard" })).toBeInTheDocument();

    await user.click(screen.getByTitle("Switch language"));

    expect(await screen.findByText("全体進捗")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ダッシュボード" })).toBeInTheDocument();
    expect(screen.queryByText("Overall progress")).not.toBeInTheDocument();
    expect(localStorage.getItem("onestatus.lang")).toBe("ja");
  });

  it("persists the saved language across a reload", async () => {
    localStorage.setItem("onestatus.lang", "ja");
    render(<LangProvider><App /></LangProvider>);
    expect(await screen.findByText("全体進捗")).toBeInTheDocument();
  });

  it("translates the Docs tab too", async () => {
    localStorage.setItem("onestatus.lang", "ja");
    const user = userEvent.setup();
    render(<LangProvider><App /></LangProvider>);
    await screen.findByText("全体進捗");

    await user.click(screen.getByRole("button", { name: "ドキュメント" }));
    expect(screen.getByText("OneStatusとは")).toBeInTheDocument();
  });
});
