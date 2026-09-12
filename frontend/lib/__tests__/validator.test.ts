import { describe, it, expect } from "vitest";
import { SecurityValidator } from "../validator";

describe("SecurityValidator (Validator.js)", () => {
  it("should validate emails correctly", () => {
    expect(SecurityValidator.isValidEmail("admin@site.com")).toBe(true);
    expect(SecurityValidator.isValidEmail("invalid-email")).toBe(false);
    expect(SecurityValidator.isValidEmail("")).toBe(false);
  });

  it("should validate passwords with strength criteria", () => {
    expect(SecurityValidator.isStrongPassword("SecurePass123")).toBe(true);
    expect(SecurityValidator.isStrongPassword("123")).toBe(false);
  });

  it("should escape unsafe HTML strings", () => {
    const raw = `<script>alert("hack")</script>&'`;
    const escaped = SecurityValidator.escape(raw);
    expect(escaped).not.toContain("<script>");
    expect(escaped).toContain("&lt;script&gt;");
  });

  it("should detect unsafe control characters and scripts", () => {
    expect(SecurityValidator.isSafeString("کاربر تست ۱۲۳")).toBe(true);
    expect(SecurityValidator.isSafeString("user\x00malicious")).toBe(false);
  });
});
