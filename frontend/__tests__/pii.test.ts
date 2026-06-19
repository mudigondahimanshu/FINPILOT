/**
 * Frontend-side PII masking tests (mirrors backend core/pii.py logic for
 * any client-side masking done before display).
 */
import { describe, it, expect } from "vitest";

function maskCard(digits: string): string {
  const clean = digits.replace(/[\s-]/g, "");
  return `•••• •••• •••• ${clean.slice(-4)}`;
}

function detectAndMaskCard(text: string): string {
  return text.replace(/\b\d{13,19}\b/g, (m) => maskCard(m));
}

describe("maskCard", () => {
  it("masks a 16-digit Visa", () => {
    expect(maskCard("4111111111111111")).toBe("•••• •••• •••• 1111");
  });

  it("masks a 15-digit Amex", () => {
    expect(maskCard("378282246310005")).toBe("•••• •••• •••• 0005");
  });

  it("preserves last 4 digits", () => {
    expect(maskCard("5500005555555559")).toContain("5559");
  });
});

describe("detectAndMaskCard in free text", () => {
  it("replaces card numbers in a sentence", () => {
    const text = "My card is 4111111111111111 and expires in 12/26";
    expect(detectAndMaskCard(text)).toContain("•••• •••• •••• 1111");
    expect(detectAndMaskCard(text)).not.toContain("4111111111111111");
  });

  it("leaves normal numbers alone", () => {
    const text = "I have 42 apples and INR 1000";
    expect(detectAndMaskCard(text)).toBe(text);
  });
});
