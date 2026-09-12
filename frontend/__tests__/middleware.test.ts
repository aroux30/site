import { describe, it, expect } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "../middleware";

describe("Next.js Security Middleware", () => {
  it("should redirect unauthenticated guest visiting /admin/dashboard to /login", () => {
    const req = new NextRequest("https://site.arouxpingg.com/admin/dashboard");
    const res = middleware(req);

    expect(res).toBeDefined();
    expect(res.status).toBe(307);
    const location = res.headers.get("location");
    expect(location).toContain("/login");
    expect(location).toContain("redirect=%2Fadmin%2Fdashboard");
  });

  it("should redirect unauthenticated guest visiting /account/orders to /login", () => {
    const req = new NextRequest("https://site.arouxpingg.com/account/orders");
    const res = middleware(req);

    expect(res).toBeDefined();
    expect(res.status).toBe(307);
    const location = res.headers.get("location");
    expect(location).toContain("/login");
    expect(location).toContain("redirect=%2Faccount%2Forders");
  });

  it("should allow public routes like / or /products to proceed without redirect", () => {
    const req = new NextRequest("https://site.arouxpingg.com/products");
    const res = middleware(req);

    expect(res.status).not.toBe(307);
    expect(res.headers.get("location")).toBeNull();
  });
});
