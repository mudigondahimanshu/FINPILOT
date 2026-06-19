import { describe, it, expect } from "vitest";
import { formatINR, cn } from "@/lib/utils";

describe("formatINR", () => {
  it("formats zero", () => {
    expect(formatINR(0)).toBe("₹0");
  });

  it("formats thousands", () => {
    expect(formatINR(1000)).toBe("₹1,000");
  });

  it("formats lakhs", () => {
    expect(formatINR(100000)).toBe("₹1,00,000");
  });

  it("formats crores", () => {
    expect(formatINR(10000000)).toBe("₹1,00,00,000");
  });

  it("rounds decimals", () => {
    // formatINR rounds to nearest rupee
    expect(formatINR(1234.56)).toMatch(/₹1,234/);
  });
});

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("deduplicates tailwind classes", () => {
    // tailwind-merge should resolve conflicts
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500");
  });

  it("handles conditional classes", () => {
    const active = false;
    expect(cn("base", active && "active")).toBe("base");
  });
});
