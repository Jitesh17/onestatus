import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

vi.mock("../api.js", () => ({
  api: {
    onUnauthorized: null,
    me: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    changePassword: vi.fn(),
    listUsers: vi.fn(),
    createUser: vi.fn(),
    updateUser: vi.fn(),
    setUserPassword: vi.fn(),
    deleteUser: vi.fn(),
    listPeople: vi.fn(),
    createPerson: vi.fn(),
    updatePerson: vi.fn(),
    deletePerson: vi.fn(),
    listProjects: vi.fn(),
    createProject: vi.fn(),
    listTasks: vi.fn(),
    createTask: vi.fn(),
    listUpdates: vi.fn(),
    createUpdate: vi.fn(),
    extractUpdate: vi.fn(),
    transcribe: vi.fn(),
    dashboard: vi.fn(),
    configureDashboard: vi.fn(),
    applyView: vi.fn(),
    listPresets: vi.fn(),
    listViews: vi.fn(),
    saveView: vi.fn(),
    deleteView: vi.fn(),
    getSettings: vi.fn(),
    putSettings: vi.fn(),
    listModels: vi.fn(),
  },
}));

import { api } from "../api.js";
import App from "../App.jsx";

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
const MEMBER_ME = { id: 4, username: "sam", role: "member", person_id: 2, author: "Sam" };

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  api.me.mockResolvedValue(ADMIN_ME);
  api.listPeople.mockResolvedValue([]);
  api.listProjects.mockResolvedValue([]);
  api.listTasks.mockResolvedValue([]);
  api.listUpdates.mockResolvedValue([]);
  api.dashboard.mockResolvedValue(EMPTY_DASH);
  api.listViews.mockResolvedValue([]);
  api.listPresets.mockResolvedValue({ teams: [], presets: [] });
  api.getSettings.mockResolvedValue({ llm_provider: "ollama", llm_model: "qwen2.5:7b" });
});

describe("Docs page", () => {
  it("opens from the Docs tab and explains the pipeline", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("Overall progress")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Docs" }));
    expect(screen.getByText("How an update becomes a status")).toBeInTheDocument();
    expect(screen.getByText("Architecture")).toBeInTheDocument();
    expect(screen.getByText("Running on a machine with no GPU")).toBeInTheDocument();
    // The dashboard is gone while docs are shown.
    expect(screen.queryByText("Overall progress")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Dashboard" }));
    expect(await screen.findByText("Overall progress")).toBeInTheDocument();
  });

  it("is visible to members, not just admins", async () => {
    api.me.mockResolvedValue(MEMBER_ME);
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("Overall progress")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Admin" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Docs" }));
    expect(screen.getByText("What OneStatus is")).toBeInTheDocument();
  });
});
