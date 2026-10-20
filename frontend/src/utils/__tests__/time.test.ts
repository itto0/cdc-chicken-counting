import { describe, it, expect } from "vitest";
import { parseUtcBucketDate, formatBucketHour, formatBucketDate } from "../time";

describe("time utils - Jakarta Timezone Standardization", () => {
  describe("parseUtcBucketDate", () => {
    it("parses UTC ISO string with trailing Z", () => {
      const d = parseUtcBucketDate("2026-04-14T03:00:00Z");
      expect(d).not.toBeNull();
      expect(d?.toISOString()).toBe("2026-04-14T03:00:00.000Z");
    });

    it("parses naive ISO string assuming UTC", () => {
      const d = parseUtcBucketDate("2026-04-14T03:00:00");
      expect(d).not.toBeNull();
      expect(d?.toISOString()).toBe("2026-04-14T03:00:00.000Z");
    });

    it("parses ISO string with positive offset", () => {
      const d = parseUtcBucketDate("2026-04-14T10:00:00+07:00");
      expect(d).not.toBeNull();
      expect(d?.toISOString()).toBe("2026-04-14T03:00:00.000Z");
    });

    it("returns null for null, undefined, empty, or whitespace strings", () => {
      expect(parseUtcBucketDate(null)).toBeNull();
      expect(parseUtcBucketDate(undefined)).toBeNull();
      expect(parseUtcBucketDate("")).toBeNull();
      expect(parseUtcBucketDate("   ")).toBeNull();
    });

    it("returns null for malformed or unparseable strings", () => {
      expect(parseUtcBucketDate("not-a-date")).toBeNull();
      expect(parseUtcBucketDate("invalid-iso-string")).toBeNull();
    });
  });

  describe("formatBucketHour", () => {
    it("formats 2026-04-14T03:00:00Z to 10:00 in WIB (UTC+7)", () => {
      expect(formatBucketHour("2026-04-14T03:00:00Z")).toBe("10:00");
    });

    it("formats 2026-04-14T03:00:00 (naive ISO assumed UTC) to 10:00 in WIB", () => {
      expect(formatBucketHour("2026-04-14T03:00:00")).toBe("10:00");
    });

    it("formats 2026-04-14T17:00:00Z to 00:00 in WIB (next day midnight)", () => {
      expect(formatBucketHour("2026-04-14T17:00:00Z")).toBe("00:00");
    });

    it("formats 2026-04-14T17:00:00 (naive ISO assumed UTC) to 00:00 in WIB", () => {
      expect(formatBucketHour("2026-04-14T17:00:00")).toBe("00:00");
    });

    it("formats bucket with explicit offset 2026-04-14T10:00:00+07:00 to 10:00", () => {
      expect(formatBucketHour("2026-04-14T10:00:00+07:00")).toBe("10:00");
    });

    it("returns empty string for null, undefined, or empty bucket", () => {
      expect(formatBucketHour(null)).toBe("");
      expect(formatBucketHour(undefined)).toBe("");
      expect(formatBucketHour("")).toBe("");
    });

    it("falls back gracefully for malformed strings", () => {
      // String with T but invalid date
      expect(formatBucketHour("badT12:34:56")).toBe("12:34");
      // String without T
      expect(formatBucketHour("malformed")).toBe("malformed");
    });
  });

  describe("formatBucketDate", () => {
    it("formats 2026-04-14T03:00:00Z as date in WIB", () => {
      const formatted = formatBucketDate("2026-04-14T03:00:00Z");
      expect(formatted).toContain("14");
      expect(formatted).toContain("2026");
    });

    it("formats 2026-04-14T17:00:00Z crossing midnight into next day (15 Apr) in WIB", () => {
      const formatted = formatBucketDate("2026-04-14T17:00:00Z");
      expect(formatted).toContain("15");
      expect(formatted).toContain("2026");
    });

    it("formats naive ISO string assuming UTC into WIB date", () => {
      const formatted = formatBucketDate("2026-04-14T03:00:00");
      expect(formatted).toContain("14");
      expect(formatted).toContain("2026");
    });

    it("returns 'Hari Ini' for null, undefined, empty, or malformed strings", () => {
      expect(formatBucketDate(null)).toBe("Hari Ini");
      expect(formatBucketDate(undefined)).toBe("Hari Ini");
      expect(formatBucketDate("")).toBe("Hari Ini");
      expect(formatBucketDate("not-a-date")).toBe("Hari Ini");
    });
  });
});
