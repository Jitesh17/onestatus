import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";

// Minimal, plain styling on purpose. Week 1 is about the data path, not visuals.
const style = document.createElement("style");
style.textContent = `
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, sans-serif; color: #1a1a1a; background: #f7f7f8; }
  .wrap { max-width: 1000px; margin: 0 auto; padding: 24px; }
  h1 { font-size: 22px; } h2 { font-size: 17px; margin-top: 28px; }
  .bar { background: #1f3864; color: #fff; padding: 12px 24px; }
  .bar b { color: #ffc000; }
  .card { background: #fff; border: 1px solid #e2e2e6; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
  label { display: block; font-size: 13px; font-weight: 600; margin: 8px 0 3px; }
  input, select, textarea { width: 100%; padding: 7px 9px; border: 1px solid #c9c9cf; border-radius: 5px; font: inherit; }
  .row { display: flex; gap: 12px; flex-wrap: wrap; }
  .row > div { flex: 1; min-width: 140px; }
  button { background: #1f3864; color: #fff; border: 0; border-radius: 5px; padding: 9px 16px; font: inherit; cursor: pointer; margin-top: 12px; }
  button.secondary { background: #ed7d31; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #ececf0; vertical-align: top; }
  th { background: #f0f1f5; font-size: 12px; text-transform: uppercase; letter-spacing: .03em; }
  .tag { display: inline-block; font-size: 11px; padding: 2px 7px; border-radius: 10px; background: #eef; margin: 1px; }
  .tag.blocked { background: #fde2e2; } .tag.done { background: #e2f3e5; }
  .muted { color: #777; font-size: 12px; }

  /* nav tabs */
  .tabs { display: flex; gap: 4px; }
  .tabs button { margin: 0; background: transparent; color: #cdd6ea; padding: 6px 14px; border-radius: 6px; }
  .tabs button.on { background: #ffc000; color: #1f3864; font-weight: 700; }

  /* dashboard */
  .kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
  .kpi { background: #fff; border: 1px solid #e2e2e6; border-radius: 10px; padding: 14px 16px; }
  .kpi .n { font-size: 26px; font-weight: 800; color: #1f3864; letter-spacing: -.02em; }
  .kpi .l { font-size: 12px; color: #777; margin-top: 2px; }
  .kpi.warn .n { color: #c0392b; }
  .h3 { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; color: #777; margin: 0 0 10px; }
  .segbar { display: flex; height: 16px; border-radius: 6px; overflow: hidden; background: #eceef3; }
  .seg { height: 100%; }
  .seg.s_not_started { background: #c9ced9; } .seg.s_in_progress { background: #2b4a82; }
  .seg.s_blocked { background: #d2603a; } .seg.s_done { background: #2e9e5b; }
  .seglegend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12px; color: #555; margin-top: 8px; }
  .seglegend .sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: 0; }
  .progress { background: #eceef3; border-radius: 6px; height: 10px; overflow: hidden; min-width: 70px; }
  .progress > div { height: 100%; background: linear-gradient(#2b4a82, #1f3864); }
  .st { font-size: 11px; padding: 2px 7px; border-radius: 10px; }
  .st.in_progress { background: #e7edf7; color: #1f3864; } .st.blocked { background: #fde2e2; color: #b53; }
  .st.done { background: #e2f3e5; color: #2e7d46; } .st.not_started { background: #eee; color: #666; }
  .feed { display: flex; flex-direction: column; gap: 8px; }
  .feed .item { border-left: 3px solid #e2e2e6; padding: 2px 0 2px 10px; }
  .feed .item.voice { border-color: #ed7d31; }
  .sevdot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: 1px; }
  .sevdot.high { background: #c0392b; } .sevdot.medium { background: #e0a400; } .sevdot.low { background: #999; }

  /* week 6: NL command bar + saved views */
  .cmdbar { border-color: #1f3864; }
  .cmdrow { display: flex; gap: 8px; align-items: center; }
  .cmdrow input { flex: 1; }
  .cmdrow button { margin: 0; padding: 8px 14px; }
  .activecfg { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
  .activecfg .savein { width: auto; flex: 0 1 160px; padding: 5px 8px; }
  .activecfg button { margin: 0; padding: 6px 12px; }
  button.link { background: transparent; color: #1f3864; text-decoration: underline; padding: 2px 4px; margin: 0; }
  .savedviews { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
  .viewchip { display: inline-flex; align-items: center; border: 1px solid #c9c9cf; border-radius: 16px; overflow: hidden; }
  .viewchip .vname { background: #f0f1f5; color: #1f3864; border: 0; margin: 0; padding: 4px 10px; font-size: 13px; border-radius: 0; }
  .viewchip .vx { background: #fff; color: #c0392b; border: 0; margin: 0; padding: 4px 9px; font-size: 14px; border-radius: 0; }
`;
document.head.appendChild(style);

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
