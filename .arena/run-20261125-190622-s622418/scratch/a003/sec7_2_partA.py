target = r".arena/run-20261125-190622-s622418/r0/a003.md"
lines = [
    "### 7.2 Playwright E2E Suite: `frontend/tests/e2e/builder-gym-weight2.spec.ts`",
    "Strict adherence to gym quality gates: zero .skip(), zero .only(), zero { force: true }, complete authentic assertions.",
    "",
    "```typescript",
    "import { test, expect } from \"@playwright/test\";",
    "import path from \"node:path\";",
    "import fs from \"node:fs\";",
    "import { execSync } from \"node:child_process\";",
    "",
    "const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || \"http://127.0.0.1:3000\";",
    "const BACKEND_DIR = path.resolve(\"C:/Users/Administrator/Desktop/site/backend\");",
    "const ARTIFACTS_DIR = path.resolve(\".loop/artifacts/builder-gym/round-079/after\");",
    "",
    "fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });",
    ""
]
with open(target, "a", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("sec7_2_partA written")
