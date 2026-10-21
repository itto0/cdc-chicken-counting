import { describe, it, expect, vi, beforeEach } from "vitest";
import { overviewApi } from "../overview.api";
import { http } from "@/lib/http";

vi.mock("@/lib/http", () => ({
  http: vi.fn(),
}));

describe("overviewApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getCounts", () => {
    it("passes expected query string with granularity=hourly and period=today", async () => {
      const mockResponse = {
        line_id: "line-1",
        aggregates: [],
        events: [],
        pagination: { total: 0, page: 1, limit: 50 },
      };
      vi.mocked(http).mockResolvedValueOnce(mockResponse);

      const result = await overviewApi.getCounts("line-1", {
        granularity: "hourly",
        period: "today",
      });

      expect(http).toHaveBeenCalledTimes(1);
      expect(http).toHaveBeenCalledWith(
        "/api/v1/lines/line-1/counts?period=today&granularity=hourly"
      );
      expect(result).toEqual(mockResponse);
    });

    it("handles call without params", async () => {
      vi.mocked(http).mockResolvedValueOnce({});

      await overviewApi.getCounts("line-1");

      expect(http).toHaveBeenCalledWith("/api/v1/lines/line-1/counts");
    });

    it("encodes lineId in counts endpoint", async () => {
      vi.mocked(http).mockResolvedValueOnce({});

      await overviewApi.getCounts("line 1/special", { period: "shift" });

      expect(http).toHaveBeenCalledWith(
        "/api/v1/lines/line%201%2Fspecial/counts?period=shift"
      );
    });
  });

  describe("getSummary", () => {
    it("calls summary endpoint with default period=today", async () => {
      vi.mocked(http).mockResolvedValueOnce({});

      await overviewApi.getSummary("line-1");

      expect(http).toHaveBeenCalledWith("/api/v1/lines/line-1/summary?period=today");
    });

    it("calls summary endpoint with custom period", async () => {
      vi.mocked(http).mockResolvedValueOnce({});

      await overviewApi.getSummary("line-1", "week");

      expect(http).toHaveBeenCalledWith("/api/v1/lines/line-1/summary?period=week");
    });
  });
});
