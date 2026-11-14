/**
 * Mint a short-lived admin access token for E2E runs.
 *
 * The login form's password is not part of the repo (and must not be), so the
 * suite mints a token with the same signer the API uses and injects it as the
 * `access_token` cookie. This is the same trust boundary the real login
 * crosses — it only skips the form, not authentication itself.
 */
import { execFileSync } from "node:child_process";
import path from "node:path";

export async function createAccessTokenForE2E(): Promise<string> {
  const backendDir = path.resolve(__dirname, "../../../../backend");
  const script = `
import asyncio, datetime
import app.tests.conftest  # registers every model module
from app.core.database.session import async_session_factory
from sqlalchemy import select
from app.modules.users.domain.models import User
from app.core.security.jwt import create_access_token

async def main():
    async with async_session_factory() as s:
        u = (await s.execute(select(User).where(User.is_superuser.is_(True)))).scalars().first()
        print(create_access_token(str(u.id), extra_claims={"roles": ["super_admin"], "is_superuser": True, "permissions": ["*"]}, expires_delta=datetime.timedelta(hours=2)))

asyncio.run(main())
`;
  const out = execFileSync("python", ["-c", script], { cwd: backendDir, encoding: "utf8" });
  return out.trim().split("\n").pop()!.trim();
}
