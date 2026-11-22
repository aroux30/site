// .claude/hooks/guard-edits.mjs — قفل مکانیکی خط قرمزها، Scope Lock و ممنوعیت دستکاری تست
import { readFileSync } from "node:fs";

const input = JSON.parse(readFileSync(0, "utf8"));
const rawPath = String(input?.tool_input?.file_path ?? "");
const normPath = rawPath.replace(/\\/g, "/").toLowerCase();
const newContent = String(
  input?.tool_input?.new_string ?? input?.tool_input?.content ?? ""
);

const deny = (reason) => {
  console.error(`BLOCKED BY GUARD-EDITS: ${reason}`);
  process.exit(2);
};

if (normPath.endsWith("backend/app/modules/audit/application/audit_service.py")) {
  deny("تغییر در audit_service.py خط قرمز مطلق است. این فایل را لمس نکن.");
}
if (normPath.includes("/desktop/elementor")) {
  deny("پوشه C:\\Users\\Administrator\\Desktop\\elementor صرفاً خواندنی است.");
}
if (normPath.includes("showcase") && !normPath.includes("e2e-isolated-scratchpad")) {
  deny("تغییر برگه showcase ممنوع است؛ فقط روی e2e-isolated-scratchpad کار کن.");
}
if (normPath.endsWith("/verifier_verdict.json")) {
  deny("نوشتن مستقیم verifier_verdict.json توسط عامل اصلی ممنوع است؛ این فایل فقط توسط هوک SubagentStop از خروجی ساب‌ایجنت qa-verifier ثبت می‌شود.");
}
if (
  (normPath.includes("test") || normPath.includes("spec") || normPath.includes("e2e")) &&
  /(\.skip\s*\(|\.only\s*\(|force\s*:\s*true)/i.test(newContent)
) {
  deny("افزودن force:true یا .skip() یا .only() در تست‌ها خط قرمز است. علت واقعی خطا را رفع کن.");
}

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
    "tests/",
    "e2e/",
    "__tests__/"
  ];
  if (normPath && !allowed.some((p) => normPath.includes(p))) {
    deny(`قفل محدوده بیلدر (GYM_SCOPE=builder) فعال است. ویرایش ${rawPath} مجاز نیست.`);
  }
}
process.exit(0);