// .claude/hooks/reinject-rules.mjs — تزریق مجدد خط قرمزها پس از Compaction خودکار
console.log(
  JSON.stringify({
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext:
        "یادآوری حیاتی پس از Compaction: (۱) audit_service.py و showcase خط قرمز مطلق‌اند؛ (۲) عکس‌های before/ و after/ (سقف ۸–۱۰ برش) باید با Read دیده شوند؛ (۳) تک‌تک شماره‌های SoM باید با pixelmatch 0.05 و ۶ سنسور خرابی تست شوند؛ (۴) همه باگ‌های P0–P3 بدون حذف در state_ledger.json ثبت شوند؛ (۵) بدون حکم APPROVE از ساب‌ایجنت qa-verifier دور بسته نمی‌شود."
    }
  })
);
process.exit(0);