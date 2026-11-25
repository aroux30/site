// .claude/hooks/guard-shell.mjs — قفل مکانیکی دستورات خطرناک شل، انشعاب main، حذف اسکرین‌شات‌ها و AGENT_STOP
import { existsSync, readFileSync } from "node:fs";

let input = {};
try {
  const raw = readFileSync(0, "utf8");
  if (raw && raw.trim()) input = JSON.parse(raw);
} catch {
  input = {};
}

const cmd = String(input?.tool_input?.command ?? "");

const deny = (reason) => {
  console.error("BLOCKED BY GUARD-SHELL: " + reason);
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

// 1. بررسی وجود فایل AGENT_STOP
if (existsSync("AGENT_STOP")) {
  deny("فایل AGENT_STOP در ریشه پروژه دیده شد. هرگونه اجرای دستور شل تا زمان رفع توقف مسدود است.");
}

// 2. مسدود کردن git push
if (/\bgit\s+push\b/i.test(cmd)) {
  deny("دستور git push اکیداً ممنوع است. تمام کارها باید صرفاً روی شاخه ایزوله محلی بماند.");
}

// 3. مسدود کردن merge یا rebase روی main/master
if (/\bgit\s+(merge|rebase)\b.*\b(main|master)\b/i.test(cmd) || /\bgit\s+checkout\s+(main|master)\b/i.test(cmd)) {
  deny("ادغام، ری‌بیس یا جابه‌جایی به شاخه main/master ممنوع است؛ فقط روی شاخه autofix/* کار کن.");
}

// 4. دستورهای مخرب گیت
if (/\bgit\s+checkout\s+--\s+\./i.test(cmd)) {
  deny("دستور مخرب git checkout -- . ممنوع است. بازگردانی تغییرات باید هدفمند و با git restore انجام شود.");
}
if (/\bgit\s+reset\s+--hard\b/i.test(cmd)) {
  deny("دستور مخرب git reset --hard ممنوع است؛ هیچ تغییر یا فایلی نباید بدون ثبت لاگ از دست برود.");
}
if (/\bgit\s+clean\s+-[a-zA-Z]*f[a-zA-Z]*d?/i.test(cmd)) {
  deny("دستور مخرب git clean -fd ممنوع است.");
}
if (/\bgit\s+stash\s+drop\b/i.test(cmd)) {
  deny("دستور git stash drop به دلیل اشتراک حافظه استش بین ورک‌تری‌ها ممنوع است.");
}

// 5. حذف اسکرین‌شات‌ها و آرتیفکت‌ها
if (/(rm|del|Remove-Item)\b.*\.loop[\/]artifacts/i.test(cmd)) {
  deny("حذف اسکرین‌شات‌ها و آرتیفکت‌های .loop/artifacts اکیداً ممنوع است (RL4).");
}

// 6. ویرایش .claude/** از مسیر شل
if (/(>|>>|tee|Out-File|Set-Content)\s*.*?\.claude[\/]/i.test(cmd) || /(sed|awk|node|python).*?-i.*?\.claude[\/]/i.test(cmd)) {
  deny("ویرایش و دستکاری فایل‌های .claude/** از طریق شل توسط config-guard مسدود است.");
}

process.exit(0);
