/**
 * Utility functions for Jakarta Timezone (WIB, UTC+7) parsing and formatting.
 */

/**
 * Parses an ISO UTC timestamp or naive ISO string (assumed to be UTC) into a Date object.
 * Returns null if the string is empty or invalid.
 */
export function parseUtcBucketDate(bucket?: string | null): Date | null {
  if (!bucket || typeof bucket !== "string") {
    return null;
  }
  const trimmed = bucket.trim();
  if (!trimmed) {
    return null;
  }
  try {
    let isoStr = trimmed;
    if (
      isoStr.includes("T") &&
      !isoStr.endsWith("Z") &&
      !/(?:[+-]\d{2}(?::\d{2})?)$/.test(isoStr)
    ) {
      isoStr = `${isoStr}Z`;
    }
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) {
      return null;
    }
    return d;
  } catch {
    return null;
  }
}

/**
 * Formats an aggregate bucket string to "HH:mm" in Jakarta Timezone (Asia/Jakarta).
 * Handles strings with or without trailing 'Z' or timezone offsets.
 * Normalizes '.' to ':' if id-ID locale produces dot separators.
 */
export function formatBucketHour(bucket?: string | null): string {
  if (!bucket || typeof bucket !== "string") {
    return "";
  }
  const d = parseUtcBucketDate(bucket);
  if (d) {
    return d
      .toLocaleTimeString("id-ID", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
        hourCycle: "h23",
        timeZone: "Asia/Jakarta",
      })
      .replace(/\./g, ":");
  }
  // Fallback to substring slicing if contains 'T'
  if (bucket.includes("T")) {
    const afterT = bucket.split("T")[1];
    return afterT ? afterT.slice(0, 5) : "";
  }
  return bucket;
}

/**
 * Formats an aggregate bucket string to Indonesian date format (e.g., "14 Apr 2026") in Jakarta Timezone.
 * Returns "Hari Ini" if bucket cannot be parsed.
 */
export function formatBucketDate(bucket?: string | null): string {
  if (!bucket || typeof bucket !== "string") {
    return "Hari Ini";
  }
  const d = parseUtcBucketDate(bucket);
  if (d) {
    return d.toLocaleDateString("id-ID", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone: "Asia/Jakarta",
    });
  }
  return "Hari Ini";
}
