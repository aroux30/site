async function fetchWithRetry(url: string, init?: RequestInit, retries = 3): Promise<Response> {
  for (let i = 0; i < retries; i++) {
    try {
      return await fetch(url, init);
    } catch (e: any) {
      if (i === retries - 1) throw e;
      await new Promise((r) => setTimeout(r, 250 * (i + 1)));
    }
  }
  throw new Error(`fetch failed: ${url}`);
}
/**
 * Mint a short-lived admin access token for E2E runs.
 *
 * The admin password is not in the repo (and must not be), so the suite mints
 * a token with the same signer the running API uses and injects it as the
 * `access_token` cookie. This skips the login *form*, not authentication: the
 * token still has to pass the API's own signature and role checks.
 *
 * The signing secret comes from the backend checkout that serves :8000 —
 * ``E2E_BACKEND_DIR`` overrides it, otherwise the repo root's ``backend`` is
 * used. A worktree without its own ``.env`` would fall back to the default
 * secret and every token would be rejected as "Invalid token".
 */
import { execSync } from "node:child_process";
import path from "node:path";
import fs from "node:fs";

export async function createAccessTokenForE2E(): Promise<string> {
  const cwd = process.cwd();
  const backendDir =
    process.env.E2E_BACKEND_DIR ||
    (fs.existsSync(path.join(cwd, "backend"))
      ? path.join(cwd, "backend")
      : path.join(cwd, "..", "backend"));

  const script = `
import asyncio, datetime, uuid
from app.core.security.jwt import create_access_token

async def main():
    user_id = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))
    try:
        import app.tests.conftest  # registers every model module
        from app.core.database.session import async_session_factory
        from sqlalchemy import select
        from app.modules.users.domain.models import User

        async with async_session_factory() as s:
            u = (await s.execute(select(User).where(User.is_superuser.is_(True)))).scalars().first()
            if u:
                user_id = str(u.id)
    except Exception:
        pass

    print("TOKEN_START:" + create_access_token(
        user_id,
        extra_claims={"roles": ["super_admin"], "is_superuser": True, "permissions": ["*"]},
        expires_delta=datetime.timedelta(hours=2),
    ))

asyncio.run(main())
`;

  const tmpFile = path.join(backendDir, `.e2e-token-${Date.now()}.py`);
  fs.writeFileSync(tmpFile, script, "utf8");
  let out = "";
  try {
    out = execSync(`python "${tmpFile}"`, {
      cwd: backendDir,
      encoding: "utf8",
    });
  } finally {
    if (fs.existsSync(tmpFile)) {
      try { fs.unlinkSync(tmpFile); } catch {}
    }
  }

  const line = out.split("\n").find((l) => l.includes("TOKEN_START:"));
  const token = line ? line.replace("TOKEN_START:", "").trim() : "";

  if (!token || token.split(".").length !== 3) {
    throw new Error(
      `Token helper produced no JWT from ${backendDir}. Raw output: ${out.slice(0, 200)}`
    );
  }
  return token;
}

/**
 * Reset the E2E CMS page to a known published fixture.
 *
 * The studio suite mutates a real page, and several of its flows change the
 * tree (or, in the draft-save case, the publication state). Without a reset
 * the tests become order-dependent: a draft save unpublishes the page and the
 * next test's `goto` 404s. Every test starts from this fixture instead.
 */
export async function resetE2EPage(slug = "e2e-isolated-scratchpad"): Promise<void> {
  const token = await createAccessTokenForE2E();
  const apiBase = process.env.API_INTERNAL_URL ?? "http://localhost:8000/api/v1";

  let page: { id: string; slug: string } | undefined;
  try {
    const listRes = await fetchWithRetry(`${apiBase}/content/admin/pages?page_size=100`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (listRes.ok) {
      const list = (await listRes.json()) as { items?: Array<{ id: string; slug: string }> };
      page = (list?.items || []).find((p) => p.slug === slug);
    }
  } catch {
    /* backend may be offline */
  }

  const fixture = {
    schemaVersion: 1,
    title: "E2E Builder Scratchpad",
    slug,
    globalStyles: {},
    rootElements: [
      {
        id: "el_e2econt1",
        name: "کانتینر اصلی",
        type: "container",
        isLocked: false,
        isHidden: false,
        layout: {
          kind: "flex",
          direction: "column",
          justifyContent: "start",
          alignItems: "stretch",
          flexWrap: "nowrap",
          gap: { value: 16, unit: "px" },
          gridColumns: 3,
        },
        styles: { mobile: {} },
        children: [
          {
            id: "el_e2ehead1",
            name: "سرتیتر اول",
            type: "widget",
            widgetType: "heading",
            widgetProps: { text: "سرتیتر اول", tag: "h2" },
            isLocked: false,
            isHidden: false,
            styles: { mobile: {} },
            children: [],
          },
          {
            id: "el_e2etext1",
            name: "متن دوم",
            type: "widget",
            widgetType: "text_editor",
            widgetProps: { content: "<p>متن دوم</p>" },
            isLocked: false,
            isHidden: false,
            styles: { mobile: {} },
            children: [],
          },
        ],
      },
      {
        id: "el_e2econt2",
        name: "کانتینر دوم",
        type: "container",
        isLocked: false,
        isHidden: false,
        layout: {
          kind: "flex",
          direction: "column",
          justifyContent: "start",
          alignItems: "stretch",
          flexWrap: "nowrap",
          gap: { value: 12, unit: "px" },
          gridColumns: 1,
        },
        styles: { mobile: {} },
        children: [],
      },
    ],
  };

  try {
    if (!page) {
      // Self-healing: create the isolated test scratchpad if it doesn't exist
      const createRes = await fetchWithRetry(`${apiBase}/content/admin/pages`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title: "E2E Builder Scratchpad",
          slug,
          builder_data: fixture,
          status: "published",
        }),
      });
      if (createRes.ok) {
        page = (await createRes.json()) as { id: string; slug: string };
      }
    } else {
      await fetchWithRetry(`${apiBase}/content/admin/pages/${page.id}`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ builder_data: fixture, status: "published" }),
      });
    }
  } catch (err) {
    console.warn("resetE2EPage fixture sync warning:", err);
  }
  // Drop the cached render so the next goto shows the fixture.
  const baseUrl = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
  try {
    await fetchWithRetry(`${baseUrl}/api/cms-revalidate?slug=${slug}`, { method: "POST" });
  } catch {
    /* the dev server may be on another port; ISR will catch up */
  }
}
