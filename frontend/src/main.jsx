import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";

// All styling lives in this injected block on purpose (no CSS build step).
// Theming: 11 custom properties, light values on :root, dark overrides scoped to
// [data-theme="dark"] on <html>. App.jsx flips the attribute; nothing re-injects.
// Navy-as-background (#1f3864), gold (#ffc000), orange (#ed7d31), seg fills and
// severity dots are deliberately theme-invariant: they read fine on both.
const style = document.createElement("style");
style.textContent = `
  :root {
    --bg: #f7f7f8; --text: #1a1a1a; --card: #fff;
    --border: #e2e2e6; --border-soft: #ececf0; --muted: #777;
    --input-border: #c9c9cf; --chip-bg: #f0f1f5;
    --accent: #1f3864; --danger: #c0392b; --trend-good: #2e7d32;
    color-scheme: light;
  }
  [data-theme="dark"] {
    --bg: #0f1115; --text: #e8eaf0; --card: #171a21;
    --border: #262b36; --border-soft: #232834; --muted: #8b91a0;
    --input-border: #353c4a; --chip-bg: #222735;
    --accent: #8fb0e8; --danger: #ef6461; --trend-good: #3ecf8e;
    color-scheme: dark;
  }

  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, sans-serif; color: var(--text); background: var(--bg); }
  .wrap { max-width: 1000px; margin: 0 auto; padding: 24px; }
  h1 { font-size: 22px; } h2 { font-size: 17px; margin-top: 28px; }
  .bar { background: #1f3864; color: #fff; padding: 12px 24px; }
  .bar b { color: #ffc000; font-size: 15px; letter-spacing: .01em; }
  [data-theme="dark"] .bar { border-bottom: 1px solid var(--border); }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
  label { display: block; font-size: 13px; font-weight: 600; margin: 8px 0 3px; }
  input, select, textarea { width: 100%; padding: 7px 9px; border: 1px solid var(--input-border); border-radius: 5px; font: inherit; background: var(--card); color: var(--text); }
  .row { display: flex; gap: 12px; flex-wrap: wrap; }
  .row > div { flex: 1; min-width: 140px; }
  button { background: #1f3864; color: #fff; border: 0; border-radius: 5px; padding: 9px 16px; font: inherit; cursor: pointer; margin-top: 12px; }
  button.secondary { background: #ed7d31; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border-soft); vertical-align: top; }
  th { background: var(--chip-bg); font-size: 12px; text-transform: uppercase; letter-spacing: .03em; }
  .tag { display: inline-block; font-size: 11px; padding: 2px 7px; border-radius: 10px; background: #eef; margin: 1px; }
  .tag.blocked { background: #fde2e2; } .tag.done { background: #e2f3e5; }
  .tag.view { background: #ffe9c2; color: #7a5b16; }
  .muted { color: var(--muted); font-size: 12px; }

  /* dark variants for the pastel pills (they carry explicit light text colors) */
  [data-theme="dark"] .tag { background: #232838; color: var(--text); }
  [data-theme="dark"] .tag.blocked { background: #3a1d1f; color: #ef6461; }
  [data-theme="dark"] .tag.done { background: #1d3326; color: #3ecf8e; }
  [data-theme="dark"] .tag.view { background: #3a2f18; color: #ffc000; }

  /* nav tabs + theme toggle */
  .tabs { display: flex; gap: 4px; align-items: center; }
  .tabs button { margin: 0; background: transparent; color: #cdd6ea; padding: 6px 14px; border-radius: 6px; }
  .tabs button.on { background: #ffc000; color: #1f3864; font-weight: 700; }
  .tabs button.themetoggle { padding: 6px 10px; font-size: 14px; }

  /* dashboard */
  .kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
  .kpi { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
  .kpi .n { font-size: 26px; font-weight: 800; color: var(--accent); letter-spacing: -.02em; }
  .kpi .l { font-size: 12px; color: var(--muted); margin-top: 2px; }
  .kpi.warn .n { color: var(--danger); }
  .h3 { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin: 0 0 10px; }
  .segbar { display: flex; height: 16px; border-radius: 6px; overflow: hidden; background: var(--chip-bg); }
  .seg { height: 100%; }
  .seg.s_not_started { background: #c9ced9; } .seg.s_in_progress { background: #2b4a82; }
  .seg.s_blocked { background: #d2603a; } .seg.s_done { background: #2e9e5b; }
  [data-theme="dark"] .seg.s_not_started { background: #3a4150; }
  .seglegend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12px; color: var(--muted); margin-top: 8px; }
  .seglegend .sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: 0; }
  .progress { background: var(--chip-bg); border-radius: 6px; height: 10px; overflow: hidden; min-width: 70px; }
  .progress > div { height: 100%; background: linear-gradient(#2b4a82, #1f3864); }
  [data-theme="dark"] .progress > div { background: linear-gradient(#3f6cb8, #2b4a82); }
  .st { font-size: 11px; padding: 2px 7px; border-radius: 10px; }
  .st.in_progress { background: #e7edf7; color: #1f3864; } .st.blocked { background: #fde2e2; color: #b53; }
  .st.done { background: #e2f3e5; color: #2e7d46; } .st.not_started { background: #eee; color: #666; }
  [data-theme="dark"] .st.in_progress { background: #1d2738; color: #8fb0e8; }
  [data-theme="dark"] .st.blocked { background: #3a1d1f; color: #ef6461; }
  [data-theme="dark"] .st.done { background: #1d3326; color: #3ecf8e; }
  [data-theme="dark"] .st.not_started { background: #2a2f3a; color: var(--muted); }
  .feed { display: flex; flex-direction: column; gap: 8px; }
  .feed .item { border-left: 3px solid var(--border); padding: 2px 0 2px 10px; }
  .feed .item.voice { border-color: #ed7d31; }
  .sevdot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: 1px; }
  .sevdot.high { background: #c0392b; } .sevdot.medium { background: #e0a400; } .sevdot.low { background: #999; }

  /* trends sprint: inline SVG charts */
  .trend svg { width: 100%; height: 96px; display: block; }
  .trendmeta { display: flex; justify-content: space-between; align-items: baseline; font-size: 12px; margin-top: 4px; }

  /* week 6: NL command bar + saved views */
  .cmdbar { border-color: var(--accent); }
  .cmdrow { display: flex; gap: 8px; align-items: center; }
  .cmdrow input { flex: 1; }
  .cmdrow button { margin: 0; padding: 8px 14px; }
  .activecfg { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
  .activecfg .savein { width: auto; flex: 0 1 160px; padding: 5px 8px; }
  .activecfg button { margin: 0; padding: 6px 12px; }
  button.link { background: transparent; color: var(--accent); text-decoration: underline; padding: 2px 4px; margin: 0; }
  .savedviews { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
  .viewchip { display: inline-flex; align-items: center; border: 1px solid var(--input-border); border-radius: 16px; overflow: hidden; }
  .viewchip .vname { background: var(--chip-bg); color: var(--accent); border: 0; margin: 0; padding: 4px 10px; font-size: 13px; border-radius: 0; }
  .viewchip .vx { background: var(--card); color: var(--danger); border: 0; margin: 0; padding: 4px 9px; font-size: 14px; border-radius: 0; }

  /* small screens: stack the KPI grid and loosen the header */
  @media (max-width: 768px) {
    .kpis { grid-template-columns: repeat(2, 1fr); }
    .bar { padding: 10px 14px; }
    .wrap { padding: 14px; }
  }
`;
document.head.appendChild(style);

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
