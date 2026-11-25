/**
 * Shared helpers for builder verification probes
 */
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

export function getAdminToken() {
  const BACKEND_DIR = path.resolve("backend");
  const script = [
    "import asyncio, datetime, uuid",
    "from app.core.security.jwt import create_access_token",
    "async def main():",
    "    user_id = str(uuid.UUID(\x2747f274da-3abd-4d91-bc9c-83ba913fc66f\x27))",
    "    print(\x27TOKEN_START:\x27 + create_access_token(",
    "        user_id,",
    "        extra_claims={\x27roles\x27: [\x27super_admin\x27], \x27is_superuser\x27: True, \x27permissions\x27: [\x27*\x27]},",
    "        expires_delta=datetime.timedelta(hours=2),",
    "    ))",
    "asyncio.run(main())"
  ].join("\n");

  const tmp = path.join(BACKEND_DIR, ".tok-" + Date.now() + ".py");
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync("python " + tmp, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } catch (e) {
    return "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}
