import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SystemStatusCard } from "../SystemStatusCard";

describe("SystemStatusCard", () => {
  it("defaults to 0 FPS, - Latensi, - Akurasi, and Offline when no props are provided", () => {
    render(<SystemStatusCard />);
    expect(screen.getByText("0")).toBeDefined();
    expect(screen.getAllByText("-").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Offline")).toBeDefined();
  });

  it("renders genuine FPS, latency, and accuracy when stream is online", () => {
    render(<SystemStatusCard fps={25} latencyMs={18} accuracyPct={99.25} streamState="online" />);
    expect(screen.getByText("25")).toBeDefined();
    expect(screen.getByText("18")).toBeDefined();
    expect(screen.getByText("99.3%")).toBeDefined();
    expect(screen.getByText("Online")).toBeDefined();
  });

  it("renders latency and accuracy when streamState is degraded", () => {
    render(<SystemStatusCard fps={15} latencyMs={120} accuracyPct={97.8} streamState="degraded" />);
    expect(screen.getByText("15")).toBeDefined();
    expect(screen.getByText("120")).toBeDefined();
    expect(screen.getByText("97.8%")).toBeDefined();
    expect(screen.getByText("Degraded")).toBeDefined();
  });

  it("hides latency and accuracy with '-' when streamState is offline even if values provided", () => {
    render(<SystemStatusCard fps={0} latencyMs={50} accuracyPct={98.5} streamState="offline" />);
    const dashes = screen.getAllByText("-");
    expect(dashes.length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("98.5%")).toBeNull();
    expect(screen.getByText("Offline")).toBeDefined();
  });

  it("displays '-' for accuracy when accuracyPct is 0 or null", () => {
    render(<SystemStatusCard fps={25} latencyMs={18} accuracyPct={0} streamState="online" />);
    expect(screen.getByText("-")).toBeDefined();
    expect(screen.queryByText("0.0%")).toBeNull();
  });
});
