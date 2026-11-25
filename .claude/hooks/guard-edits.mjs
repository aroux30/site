// .claude/hooks/guard-edits.mjs — config-guard + قفل مکانیکی خط‌قرمزها و محدوده GYM_SCOPE
import { readFileSync } from "node:fs";

let input = {};
try {
  const raw = readFileSync(0, "utf8");
  if (raw && raw.trim()) input = JSON.parse(raw);
} catch {
  input = {};
}

const rawPath = String(input?.tool_input?.file_path ?? input?.tool_input?.notebook_path ?? "");
const normPath = rawPath.replaceAll("\\", "/").toLowerCase();
const newContent = String(
  input?.tool_input?.new_string ??
  input?.tool_input?.content ??
  JSON.stringify(input?.tool_input?.edits ?? [])
);

const deny = (reason) => {
  console.error("BLOCKED BY CONFIG-GUARD: " + reason);
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: reason,
      },
    })
  );
  process.exit(2);
};

// 1. config-guard: مسدود کردن هرگونه ویرایش/ساخت در تنظیمات و هوک‌ها و ایجنت‌ها
if (normPath.includes(".claude/settings.json") || normPath.includes(".claude/settings.local.json")) {
  deny("ویرایش .claude/settings.json توسط config-guard مسدود است؛ تنظیمات هوک‌ها قفل مکانیکی شده‌اند.");
}
if (normPath.includes(".claude/hooks/")) {
  deny("ویرایش .claude/hooks/** توسط config-guard مسدود است؛ دستکاری هوک‌های امنیتی خط قرمز است.");
}
if (normPath.includes(".claude/agents/")) {
  deny("ویرایش .claude/agents/** توسط config-guard مسدود است؛ پرونده ناظر مستقل قفل است.");
}

// 2. خط‌قرمزهای مطلق
if (normPath.endsWith("backend/app/modules/audit/application/audit_service.py") || normPath.includes("audit_service.py")) {
  deny("تغییر در audit_service.py خط قرمز مطلق است. این فایل را لمس نکن.");
}
if (normPath.includes("/desktop/elementor") || normPath.includes("desktop/elementor")) {
  deny("پوشه C:\Users\Administrator\Desktop\elementor صرفاً خواندنی است.");
}
if (normPath.includes("showcase") && !normPath.includes("e2e-isolated-scratchpad")) {
  deny("تغییر برگه showcase ممنوع است؛ فقط روی e2e-isolated-scratchpad کار کن.");
}
if (normPath.endsWith("verifier_verdict.json") || normPath.includes("verifier_verdict.json")) {
  deny("نوشتن مستقیم verifier_verdict.json ممنوع است؛ این فایل فقط توسط هوک SubagentStop با حکم ناظر qa-verifier ثبت می‌شود.");
}

// 3. توکن‌های تقلب RL5
const cheatTokens = [
  { pattern: /force\s*:\s*true/i, desc: "force: true" },
  { pattern: /\.(skip|only)\s*\(/i, desc: ".skip() یا .only()" },
  { pattern: /@pytest\.mark\.skip|SkipTest/i, desc: "SkipTest یا pytest.mark.skip" },
  { pattern: /dispatchEvent\s*\(\s*['"]click['"]\)/i, desc: "dispatchEvent('click')" },
  { pattern: /el\.click\s*\(/i, desc: "el.click() در evaluate" },
  { pattern: /waitForTimeout/i, desc: "waitForTimeout" },
];

for (const { pattern, desc } of cheatTokens) {
  if (pattern.test(newContent)) {
    deny("استفاده از توکن تقلب " + desc + " خط قرمز RL5 است. علت واقعی خطا را رفع کن.");
  }
}

// 4. قفل محدوده بیلدر (GYM_SCOPE=builder)
if (process.env.GYM_SCOPE === "builder") {
  const allowed = [
    "frontend/components/admin/builder/",
    "frontend/stores/builder-store.ts",
    "frontend/lib/builder/",
    "frontend/types/builder.ts",
    "backend/app/modules/content/domain/builder_ast.py",
    "backend/app/modules/content/domain/builder_validation.py",
    "backend/app/modules/content/application/ast_compiler.py",
    "backend/app/modules/content/application/html_sanitizer.py",
    "backend/app/modules/content/application/cms_page_service.py",
    "backend/app/modules/content/application/form_submission_service.py",
    ".loop/",
    "needs_human.md",
    "steer.md",
    "scripts/loop/",
    "tests/",
    "e2e/",
    "__tests__/",
    "controls.contract.spec.ts",
    "builder_gym_loop_v5.2.md",
    "run-gym-loop-v5.1.ps1"
  ];
  if (normPath && !allowed.some((p) => normPath.includes(p))) {
    deny("قفل محدوده بیلدر (GYM_SCOPE=builder) فعال است. ویرایش " + rawPath + " مجاز نیست.");
  }
}

process.exit(0);
