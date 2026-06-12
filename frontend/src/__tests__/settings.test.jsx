import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

vi.mock("../api.js", () => ({
  api: {
    getSettings: vi.fn(),
    putSettings: vi.fn(),
    listModels: vi.fn(),
  },
}));

import { api } from "../api.js";
import { SettingsPanel } from "../App.jsx";

const SETTINGS = {
  llm_provider: "ollama", ollama_url: "http://localhost:11434", llm_model: "qwen2.5:7b",
  llm_base_url: "", llm_temperature: 0, llm_timeout: 120, api_key_set: false,
  whisper_model: "medium", whisper_device: "cpu", whisper_compute: "int8",
  whisper_beam: 5, whisper_vad: true,
};

beforeEach(() => {
  vi.clearAllMocks();
  api.getSettings.mockResolvedValue({ ...SETTINGS });
  api.listModels.mockResolvedValue({
    ollama_models: ["llama3.2:3b", "qwen2.5:7b"],
    whisper_sizes: ["tiny", "base", "small", "medium", "large-v2", "large-v3"],
    warning: null,
  });
  // Faithful to the backend: the key is accepted but never returned.
  api.putSettings.mockImplementation(async (diff) => {
    const { llm_api_key, ...rest } = diff;
    return { ...SETTINGS, ...rest, api_key_set: llm_api_key ? true : SETTINGS.api_key_set };
  });
});

describe("SettingsPanel", () => {
  it("renders the current settings and the installed Ollama models", async () => {
    render(<SettingsPanel onSaved={() => {}} onClose={() => {}} />);
    expect(await screen.findByText("Local (Ollama)")).toBeInTheDocument();
    const modelSelect = screen.getByDisplayValue("qwen2.5:7b");
    expect(modelSelect).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "llama3.2:3b" })).toBeInTheDocument();
    // local mode shows no cloud warning
    expect(screen.queryByText(/sent to an external API/)).not.toBeInTheDocument();
  });

  it("shows the data warning and key field when a cloud provider is selected", async () => {
    const user = userEvent.setup();
    render(<SettingsPanel onSaved={() => {}} onClose={() => {}} />);
    await screen.findByText("Local (Ollama)");

    await user.click(screen.getByRole("radio", { name: /OpenAI compatible/ }));
    expect(screen.getByText(/sent to an external API/)).toBeInTheDocument();
    expect(screen.getByText(/API key \(not set\)/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText("https://api.openai.com")).toBeInTheDocument();
  });

  it("saves only the changed fields", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    render(<SettingsPanel onSaved={onSaved} onClose={() => {}} />);
    await screen.findByText("Local (Ollama)");

    await user.selectOptions(screen.getByDisplayValue("qwen2.5:7b"), "llama3.2:3b");
    await user.click(screen.getByRole("button", { name: "Save settings" }));

    expect(api.putSettings).toHaveBeenCalledWith({ llm_model: "llama3.2:3b" });
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ llm_model: "llama3.2:3b" }));
    expect(await screen.findByText(/Saved\./)).toBeInTheDocument();
  });

  it("sends the API key on save but never displays it", async () => {
    const user = userEvent.setup();
    render(<SettingsPanel onSaved={() => {}} onClose={() => {}} />);
    await screen.findByText("Local (Ollama)");

    await user.click(screen.getByRole("radio", { name: /Anthropic/ }));
    const keyInput = screen.getByPlaceholderText("paste the key");
    expect(keyInput).toHaveAttribute("type", "password");
    await user.type(keyInput, "sk-ant-secret");
    await user.click(screen.getByRole("button", { name: "Save settings" }));

    expect(api.putSettings).toHaveBeenCalledWith({
      llm_provider: "anthropic",
      llm_api_key: "sk-ant-secret",
    });
    // after save the field clears; the stored key is reported only as a flag
    expect(keyInput).toHaveValue("");
  });

  it("closes without a request when nothing changed", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<SettingsPanel onSaved={() => {}} onClose={onClose} />);
    await screen.findByText("Local (Ollama)");

    await user.click(screen.getByRole("button", { name: "Save settings" }));
    expect(api.putSettings).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });
});
