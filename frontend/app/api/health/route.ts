import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  // Read BUILD_ID from disk (.next/BUILD_ID)
  let buildId = "development";
  try {
    const cwd = process.cwd();
    const candidatePaths = [
      path.join(cwd, ".next", "BUILD_ID"),
      path.join(cwd, "frontend", ".next", "BUILD_ID"),
    ];
    for (const p of candidatePaths) {
      if (fs.existsSync(p)) {
        buildId = fs.readFileSync(p, "utf8").trim();
        break;
      }
    }
  } catch {
    buildId = "unknown";
  }

  // Probe backend connection: /api/v1/content/themes/active
  const apiBase =
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:8000/api/v1";

  let backendHealthy = false;
  let backendStatusCode: number | null = null;

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2500);
    const res = await fetch(`${apiBase}/content/themes/active`, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    clearTimeout(timeout);
    backendStatusCode = res.status;
    backendHealthy = res.ok || res.status === 401 || res.status === 404; // backend is reachable and responding
  } catch {
    backendHealthy = false;
    backendStatusCode = null;
  }

  const responseBody = {
    status: backendHealthy ? "ok" : "degraded",
    buildId,
    backend: {
      ok: backendHealthy,
      statusCode: backendStatusCode,
      endpoint: `${apiBase}/content/themes/active`,
    },
    timestamp: new Date().toISOString(),
  };

  return NextResponse.json(responseBody, {
    status: 200,
    headers: {
      "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
      Pragma: "no-cache",
      Expires: "0",
    },
  });
}
