import { describe, it, expect } from "vitest";
import { sanitizeHtml } from "../sanitize";

describe("sanitizeHtml security utility", () => {
  it("should return empty string for null or undefined input", () => {
    expect(sanitizeHtml(null)).toBe("");
    expect(sanitizeHtml(undefined)).toBe("");
  });

  it("should strip malicious script tags in server and client contexts", () => {
    const malicious = `<p>سلام</p><script>alert('xss')</script><b>خوش آمدید</b>`;
    const clean = sanitizeHtml(malicious);
    expect(clean).not.toContain("<script>");
    expect(clean).not.toContain("alert('xss')");
    expect(clean).toContain("سلام");
  });

  it("should strip event handlers like onerror and onclick", () => {
    const malicious = `<img src="x" onerror="alert(1)" /><a href="#" onclick="doEvil()">لینک</a>`;
    const clean = sanitizeHtml(malicious);
    expect(clean).not.toContain("onerror");
    expect(clean).not.toContain("onclick");
  });
});
