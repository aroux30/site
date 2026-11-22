// .claude/hooks/guard-shell.mjs — جلوگیری از git push، کار روی main، پاک کردن عکس‌ها و تست فیلترشده
import { readFileSync } from "node:fs";

const input = JSON.parse(readFileSync(0, "utf8"));
const cmd = String(input?.tool_input?.command ?? "");

const deny = (reason) => {
  console.error(`BLOCKED BY GUARD-SHELL: ${reason}`);
  process.exit(2);
};

if (/\bgit\s+push\b/i.test(cmd)) {
  deny("اجرای git push مطلقاً ممنوع است؛ فقط روی شاخه ایزوله محلی کامیت کن.");
}
if (/\bgit\s+(checkout|switch|merge)\s+.*\b(main|master)\b/i.test(cmd)) {
  deny("تغییر شاخه یا ادغام روی main/master ممنوع است.");
}
if (/(rm\s+-rf|remove-item|del\s+|erase\s+).*(artifacts|before|after|\.loop)/i.test(cmd)) {
  deny("پاک کردن اسکرین‌شات‌ها یا آرتیفکت‌های .loop/artifacts خط قرمز است.");
}
if (/pytest.*(\s-k\s|\s--maxfail)/i.test(cmd)) {
  deny("اجرای فیلترشده pytest ممنوع است؛ کل python -m pytest app/tests/unit را کامل اجرا کن.");
}
process.exit(0);