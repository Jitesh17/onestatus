import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

vi.mock("../api.js", () => ({
  api: {
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

const DEFAULT_SETTINGS = {
  llm_provider: "ollama", ollama_url: "http://localhost:11434", llm_model: "qwen2.5:7b",
  llm_base_url: "", llm_temperature: 0, llm_timeout: 120, api_key_set: false,
  whisper_model: "medium", whisper_device: "cpu", whisper_compute: "int8",
  whisper_beam: 5, whisper_vad: true,
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  api.listProjects.mockResolvedValue([]);
  api.listTasks.mockResolvedValue([]);
  api.listUpdates.mockResolvedValue([]);
  api.dashboard.mockResolvedValue(EMPTY_DASH);
  api.listViews.mockResolvedValue([]);
  api.listPresets.mockResolvedValue({ teams: [], presets: [] });
  api.getSettings.mockResolvedValue(DEFAULT_SETTINGS);
  api.listModels.mockResolvedValue({ ollama_models: ["qwen2.5:7b"], whisper_sizes: ["medium"], warning: null });
});

describe("App", () => {
  it("starts on the dashboard and switches to Capture and back", async () => {
    const user = userEvent.setup();
    render(<App />);
    // Dashboard is the default view.
    expect(await screen.findByText("Overall progress")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Capture" }));
    expect(await screen.findByText("Add project")).toBeInTheDocument();
    expect(screen.getByText("Add update by voice or text (AI)")).toBeInTheDocument();
    expect(screen.queryByText("Overall progress")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Dashboard" }));
    expect(await screen.findByText("Overall progress")).toBeInTheDocument();
  });

  it("theme toggle flips the document theme and persists it", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(document.documentElement.dataset.theme).toBe("light");

    await user.click(screen.getByTitle("Switch theme"));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("onestatus.theme")).toBe("dark");

    await user.click(screen.getByTitle("Switch theme"));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("onestatus.theme")).toBe("light");
  });

  it("reads the saved theme from localStorage on startup", async () => {
    localStorage.setItem("onestatus.theme", "dark");
    render(<App />);
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("shows an error banner when the API is unreachable", async () => {
    api.listProjects.mockRejectedValue(new Error("ECONNREFUSED"));
    render(<App />);
    expect(await screen.findByText(/Cannot reach the API/)).toBeInTheDocument();
  });
});
