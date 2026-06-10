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
`;
document.head.appendChild(style);

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
