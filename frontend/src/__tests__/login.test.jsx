import { act, render, screen } from "@testing-library/react";
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

const MEMBER = { id: 3, username: "sam", role: "member", person_id: null, author: "Sam S" };
const MANAGER = { id: 2, username: "alex", role: "manager", person_id: null, author: "Alex" };
const ADMIN = { id: 1, username: "admin", role: "admin", person_id: null, author: "admin" };

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  api.listProjects.mockResolvedValue([]);
  api.listTasks.mockResolvedValue([]);
  api.listUpdates.mockResolvedValue([]);
  api.listPeople.mockResolvedValue([]);
  api.listUsers.mockResolvedValue([]);
  api.dashboard.mockResolvedValue(EMPTY_DASH);
  api.listViews.mockResolvedValue([]);
  api.listPresets.mockResolvedValue({ teams: [], presets: [] });
  api.getSettings.mockResolvedValue({ llm_provider: "ollama", llm_model: "qwen2.5:7b" });
});

describe("Login flow", () => {
  it("shows the login page without a session, then the app after logging in", async () => {
    api.me.mockRejectedValue(new Error("Not logged in"));
    api.login.mockResolvedValue(MEMBER);
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dashboard" })).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("Username"), "sam");
    await user.type(screen.getByLabelText("Password"), "password1");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(api.login).toHaveBeenCalledWith({ username: "sam", password: "password1" });
    expect(await screen.findByText("Overall progress")).toBeInTheDocument();
    expect(screen.getByTitle("Logged in as sam (member)")).toBeInTheDocument();
  });

  it("shows the backend error on a failed login", async () => {
    api.me.mockRejectedValue(new Error("Not logged in"));
    api.login.mockRejectedValue(new Error("Invalid username or password"));
    const user = userEvent.setup();
    render(<App />);

    await screen.findByRole("heading", { name: "Log in" });
    await user.type(screen.getByLabelText("Username"), "sam");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByText("Invalid username or password")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dashboard" })).not.toBeInTheDocument();
  });

  it("hides the create forms and Admin tab from members; author is read-only", async () => {
    api.me.mockResolvedValue(MEMBER);
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Capture" }));
    expect(await screen.findByText("Add status update")).toBeInTheDocument();
    expect(screen.queryByText("Add project")).not.toBeInTheDocument();
    expect(screen.queryByText("Add task")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Admin" })).not.toBeInTheDocument();
    expect(screen.queryByTitle("Settings")).not.toBeInTheDocument();

    const authorInputs = screen.getAllByDisplayValue("Sam S");
    expect(authorInputs.length).toBeGreaterThan(0);
    expect(authorInputs[0]).toHaveAttribute("readonly");
  });

  it("shows the create forms to managers with an editable author", async () => {
    api.me.mockResolvedValue(MANAGER);
    api.listPeople.mockResolvedValue([{ id: 1, name: "Suzuki Taro", name_ja: null, team: null, department: null }]);
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Capture" }));
    expect(await screen.findByText("Add project")).toBeInTheDocument();
    expect(screen.getByText("Add task")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Admin" })).not.toBeInTheDocument();
    // Manager author field: editable, placeholder shows their own name.
    expect(screen.getAllByPlaceholderText("Alex").length).toBeGreaterThan(0);
  });

  it("shows the Admin tab with users and roster panels to admins", async () => {
    api.me.mockResolvedValue(ADMIN);
    api.listUsers.mockResolvedValue([
      { id: 1, username: "admin", role: "admin", person_id: null, is_active: true, created_at: "2026-06-01T00:00:00" },
    ]);
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Admin" }));
    expect(await screen.findByText("User accounts")).toBeInTheDocument();
    expect(screen.getByText("People (org roster)")).toBeInTheDocument();
    expect(screen.getByText("(you)")).toBeInTheDocument();
  });

  it("logs out and returns to the login screen", async () => {
    api.me.mockResolvedValue(MEMBER);
    api.logout.mockResolvedValue(null);
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByTitle("Log out"));
    expect(api.logout).toHaveBeenCalled();
    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
  });

  it("drops to the login screen when any call later returns 401", async () => {
    api.me.mockResolvedValue(MEMBER);
    render(<App />);
    await screen.findByText("Overall progress");

    // Simulate the api layer reporting an expired session.
    act(() => api.onUnauthorized());
    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
  });
});
