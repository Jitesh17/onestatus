import { render, screen } from "@testing-library/react";
import { TrendChart } from "../App.jsx";

const POINTS = [
  { date: "2026-06-01", value: 10 },
  { date: "2026-06-02", value: 30 },
  { date: "2026-06-03", value: 50 },
];

describe("TrendChart", () => {
  it("renders a polyline with one coordinate per point", () => {
    const { container } = render(<TrendChart points={POINTS} max={100} unit="%" />);
    const poly = container.querySelector("polyline");
    expect(poly).not.toBeNull();
    expect(poly.getAttribute("points").trim().split(/\s+/)).toHaveLength(3);
  });

  it("step mode inserts a corner coordinate between points", () => {
    const { container } = render(<TrendChart points={POINTS} step />);
    const poly = container.querySelector("polyline");
    // n points -> n + (n - 1) coordinates when stepping
    expect(poly.getAttribute("points").trim().split(/\s+/)).toHaveLength(5);
  });

  it("shows first and last date plus the latest value", () => {
    render(<TrendChart points={POINTS} max={100} unit="%" />);
    expect(screen.getByText("2026-06-01")).toBeInTheDocument();
    expect(screen.getByText("2026-06-03")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("renders the empty message when there are no points", () => {
    render(<TrendChart points={[]} />);
    expect(screen.getByText("No history yet.")).toBeInTheDocument();
    render(<TrendChart points={null} />);
    expect(screen.getAllByText("No history yet.").length).toBeGreaterThan(0);
  });
});
