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
});
