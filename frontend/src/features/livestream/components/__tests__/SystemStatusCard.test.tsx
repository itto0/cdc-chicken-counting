import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SystemStatusCard } from "../SystemStatusCard";

describe("SystemStatusCard", () => {
  it("defaults to 0 FPS, - Latensi, and Offline when no props are provided", () => {
    render(<SystemStatusCard />);
    expect(screen.getByText("0")).toBeDefined();
    expect(screen.getByText("-")).toBeDefined();
    expect(screen.getByText("Offline")).toBeDefined();
    expect(screen.queryByText("42")).toBeNull();
    expect(screen.queryByText("30")).toBeNull();
  });

  it("renders genuine FPS and latency when stream is online", () => {
    render(<SystemStatusCard fps={25} latencyMs={18} streamState="online" />);
    expect(screen.getByText("25")).toBeDefined();
    expect(screen.getByText("18")).toBeDefined();
    expect(screen.getByText("Online")).toBeDefined();
  });

  it("renders latency when streamState is degraded", () => {
    render(<SystemStatusCard fps={15} latencyMs={120} streamState="degraded" />);
    expect(screen.getByText("15")).toBeDefined();
    expect(screen.getByText("120")).toBeDefined();
    expect(screen.getByText("Degraded")).toBeDefined();
  });

  it("hides latency with '-' when streamState is offline even if latencyMs > 0", () => {
    render(<SystemStatusCard fps={0} latencyMs={50} streamState="offline" />);
    expect(screen.getByText("-")).toBeDefined();
    expect(screen.queryByText("50")).toBeNull();
    expect(screen.getByText("Offline")).toBeDefined();
  });
});
