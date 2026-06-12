import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

vi.mock("../api.js", () => ({
  api: {
    dashboard: vi.fn(),
    listViews: vi.fn(),
    listPresets: vi.fn(),
    applyView: vi.fn(),
    configureDashboard: vi.fn(),
    saveView: vi.fn(),
    deleteView: vi.fn(),
    transcribe: vi.fn(),
  },
}));

import { api } from "../api.js";
import { Dashboard } from "../App.jsx";

const DASH = {
  totals: { projects: 3, tasks: 7, updates: 27 },
  task_status_counts: { not_started: 1, in_progress: 4, blocked: 1, done: 1 },
  overall_progress: 46,
  open_blockers: 4,
  open_blockers_by_severity: { low: 0, medium: 3, high: 1 },
  open_risks: 2,
  blockers_list: [{ description: "Tokyo approval pending", severity: "high",
                    owner: null, task: "Review pipeline", project: "BRAVIA" }],
  risks_list: [{ description: "Monsoon delay", impact: "medium", mitigation: null,
                 owner: null, task: null, project: null }],
  recent_updates: [],
  upcoming_next_steps: [],
  per_project: [{ id: 1, name: "BRAVIA Panel Calibration", name_ja: null,
                  status: "in_progress", owner: null, task_count: 3,
                  avg_progress: 42, open_blocker_count: 2, done_task_count: 0 }],
  per_team: [{ team: "Display Systems", department: "ISC", members: ["Neeraj"],
               task_count: 3, done_task_count: 0, avg_progress: 42,
               open_blocker_count: 2 }],
  per_person: [{ name: "Neeraj", team: "Display Systems", task_count: 3,
                 done_task_count: 0, avg_progress: 42, open_blocker_count: 2,
                 next_step_count: 1 }],
  trends: { progress: [{ date: "2026-06-01", value: 40 }], blockers: [] },
};

const PRESETS = {
  teams: ["Display Systems", "Speech & Audio"],
  presets: [
    { id: "exec_summary", label: "Executive summary",
      nl_phrase: "show delivery, projects, trends and top 5 blockers",
      needs_team: false,
      config: { sections: ["delivery", "per_project", "blockers", "trends"],
                sort: "severity", limit: 5, summary: "Executive summary" } },
    { id: "team_view", label: "Team view", nl_phrase: "focus on the {team} team",
      needs_team: true,
      config: { team: "{team}", sections: [], summary: "Team view for {team}" } },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  api.dashboard.mockResolvedValue(DASH);
  api.listViews.mockResolvedValue([]);
  api.listPresets.mockResolvedValue(PRESETS);
});

describe("Dashboard", () => {
  it("renders the KPI numbers from the API", async () => {
    render(<Dashboard tick={0} />);
    expect(await screen.findByText("46%")).toBeInTheDocument();
    // Several labels repeat as section headings, so count instead of getByText.
    expect(screen.getAllByText("Projects").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Open blockers").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Teams").length).toBeGreaterThan(0);
    expect(screen.getAllByText("People").length).toBeGreaterThan(0);
  });

  it("applies a preset chip and substitutes the selected team", async () => {
    api.applyView.mockResolvedValue({
      config: { team: "Display Systems", sections: [], hide: [],
                summary: "Team view for Display Systems" },
      dashboard: DASH,
    });
    const user = userEvent.setup();
    render(<Dashboard tick={0} />);
    await user.click(await screen.findByRole("button", { name: "Team view" }));
    await waitFor(() => expect(api.applyView).toHaveBeenCalledTimes(1));
    expect(api.applyView.mock.calls[0][0].team).toBe("Display Systems");
    // The equivalent NL phrase lands in the command box, team substituted.
    expect(screen.getByDisplayValue("focus on the Display Systems team")).toBeInTheDocument();
  });

  it("hides sections listed in the applied config", async () => {
    api.applyView.mockResolvedValue({
      config: { sections: [], hide: ["risks"], summary: "no risks" },
      dashboard: DASH,
    });
    const user = userEvent.setup();
    render(<Dashboard tick={0} />);
    expect(await screen.findByText(/Risks \(2\)/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Executive summary" }));
    await waitFor(() =>
      expect(screen.queryByText(/Risks \(2\)/)).not.toBeInTheDocument());
  });

  it("applies a saved view chip", async () => {
    api.listViews.mockResolvedValue([
      { id: 1, name: "Blocked in BRAVIA",
        config: { project: "BRAVIA Panel Calibration", status: "blocked" } },
    ]);
    api.applyView.mockResolvedValue({
      config: { project: "BRAVIA Panel Calibration", status: "blocked",
                sections: [], hide: [], summary: "blocked in BRAVIA" },
      dashboard: DASH,
    });
    const user = userEvent.setup();
    render(<Dashboard tick={0} />);
    await user.click(await screen.findByRole("button", { name: "Blocked in BRAVIA" }));
    await waitFor(() => expect(api.applyView).toHaveBeenCalledWith(
      { project: "BRAVIA Panel Calibration", status: "blocked" }));
    expect(screen.getByText("view: blocked in BRAVIA")).toBeInTheDocument();
  });

  it("still renders when the presets endpoint fails", async () => {
    api.listPresets.mockRejectedValue(new Error("boom"));
    render(<Dashboard tick={0} />);
    expect(await screen.findByText("46%")).toBeInTheDocument();
    expect(screen.queryByText("Quick views:")).not.toBeInTheDocument();
  });
});
