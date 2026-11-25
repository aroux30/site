name: qa-round-gate
description: راه‌اندازی دور R000 (فیکسچرهای کالیبراسیون RED/GREEN)، قرارداد اسپرینت (round_contract.json)، چک‌لیست دروازه مکانیکی gate.mjs، سناریوهای کاربری (Journeys) و قالب تحلیل ≤۱۲ خطی در قدم‌های ۴، ۶B و ۷.
user-invocable: false
راه‌اندازی R000، قرارداد اسپرینت، دروازه مکانیکی و گزارش دور
۱. راه‌اندازی یک‌باره R000 (فقط بار اول؛ سپس توقف و گزارش)
موجودی .claude/settings.json، .claude/hooks/*، .claude/agents/*، scripts/loop/* و .loop/* را بخوان؛ ابزارهای موجود را گسترش بده، جایگزین نکن.

اسکریپت‌های Node ESM زیر را در scripts/loop/ بساز/تکمیل کن: discover.mjs، census.mjs، probe-lib.mjs، probe-one.mjs، sensors.mjs، contact-sheet.mjs، gate.mjs، round-report.mjs و build-manifest.mjs.

کالیبراسیون سنسورها (D7): در scripts/loop/fixtures/ برای هر کلاس باگ (SCROLL_TRAP، CLIPPED_X، DEAD_MENU، RAW_ICON_SLUG، INVISIBLE_ACTIONS، INVALID_COLOR) یک HTML معیوب و یک HTML سالم بساز و تست واحد اجرا کن: روی معیوب RED، روی سالم GREEN.

فایل تست قراردادی controls.contract.spec.ts را در پوشه E2E Playwright با برچسب عنوان @unit:<id> @col:<name> و خروجی JSON بساز.

۲. قالب round_contract.json (نوشته‌شده در انتهای قدم ۲ پیش از کدنویسی)json
{
"round": 1,
"weight": 0,
"target_units": ["inspector|style"],
"fip_defects": ["D-0001", "D-0002"],
"cluster_defects": ["D-0001", "D-0002", "D-0003", "D-0004"],
"census_controls_to_verify": ["padding_top", "bg_color", "icon_picker"],
"hard_pass_criteria": [
"scroll_audit.json: zero SCROLL_TRAP_P0 and zero CLIPPED_X at 1280/1366/1440",
"menu_open_proof.json: 100% tested menus open above iframe with >=2 options",
"semantic_widget_audit.json: zero raw icon slugs",
"all cluster defects have RED->GREEN regression tests and atomic commits"
]
}


## ۳. شروط `GATE_OK` در `scripts/loop/gate.mjs`
- **G1:** شاخه ≠ `main`/`master`، صفر تغییر در `audit_service.py` و `showcase`، و در حالت `GYM_SCOPE=builder` صفر تغییر خارج از مسیرهای مجاز بیلدر.
- **G2:** صفر توکن ممنوع RL5 در `git diff` (`force: true`، `.skip`، `.only`، `dispatchEvent('click')`، `el.click()`، `waitForTimeout`).
- **G3:** صفر شکست و صفر skip در خروجی JSON تست‌ها؛ شمار تست‌ها ≥ Baseline (`pytest >= 622`، `vitest >= 369`).
- **G4:** هیچ فایلی از `artifacts.manifest.json` حذف یا بازنویسی نشده است.
- **G5:** تمام تصاویر کنتاکت‌شیت در `.loop/vision_receipts.jsonl` ثبت شده و در `vision_notes.md` مشاهده مشخص (selector/مختصات) دارند؛ هر پاس ≤ ۱۰ تصویر.
- **G6:** `coverage_matrix.json` از خروجی JSON تست‌های `@unit: @col:` بازسازی و با فایل ذخیره‌شده برابر است.
- **G7:** هر باگ `fixed` در `state_ledger.json` دارای `fix_commit` مجزا، تست سبز و `sibling_hits` بررسی‌شده است.
- **G8:** ۱۰۰٪ کنترل‌های `census.json` در `mutation_report.json` حکم دارند و `round_contract.json` موجود است.
- **G9:** در حالت `--final --weights a-b`، ۱۰۰٪ ردیف‌های آن وزنه‌ها `true` و `verifier_verdict.json` با حکم `"APPROVE"` از طریق هوک `SubagentStop` مهر شده است.

## ۴. قالب تحلیل مستند (حداکثر ۱۲ خط در گزارش دور)
- **SWOT (۴ خط):** ۱–۳ مورد عینی در هر ربع S / W / O / T.
- **TOWS (۲ خط):** اقدام مهندسی دقیق دور بعد (SO/WO/ST/WT).
- **۵-چرا (۳ خط):** ریشه‌یابی باگ محوری خوشه با ارجاع دقیق `file:line`.
- **ماتریس ریسک (۳ خط):** لایه‌های لمس‌شده + تست قفل‌کننده + اثر بر اندازه باندل/امنیت.