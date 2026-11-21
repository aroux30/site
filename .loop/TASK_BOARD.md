# تابلوی وظایف صفحه‌ساز بصری (.loop/TASK_BOARD.md)

| شناسه | عنوان وظیفه | اولویت | وضعیت | مالک (Agent) | شواهد و فایل‌های وابسته |
|:---:|:---|:---:|:---:|:---:|:---|
| **TASK-01** | ممیزی شناسایی کامل پروژه، منابع و مسیرهای المنتور | P0 | **DONE** | Lead Architect | `.loop/INITIAL_PROJECT_AUDIT.md` |
| **TASK-02** | استخراج موجودی جامع ۳۴ ویجت، ۲۸ الگو و کنترل‌های بازرس | P0 | **DONE** | Feature Auditor | `.loop/BUILDER_FEATURE_INVENTORY.md` |
| **TASK-03** | تحلیل شکاف عمیق معماری با Elementor Core و Pro | P0 | **DONE** | Elementor Specialist | `.loop/ELEMENTOR_GAP_ANALYSIS.md` |
| **TASK-04** | بررسی و تثبیت پیش‌نیازهای P0 (دکمه‌های لایه‌ها، ارتفاع کانتینر، نوار ابزار) | P0 | **DONE** | Frontend & QA | `.loop/audits/deterministic-report.json` |
| **TASK-05** | برطرف‌سازی خطاهای رگرسیون تداخل نوار ابزار و همگام‌سازی استیت | P0 | **DONE** | Frontend Engineer | `frontend/stores/builder-store.ts`, `canvas-element.tsx` |
| **TASK-06** | اعتبارسنجی ۱۰۰٪ تست‌های رگرسیون پیش‌رونده راندهای ۱ تا ۲۰ | P0 | **DONE** | Software QA | ۶۰ تست سبز در `playwright test tests/e2e/builder-gym-r*.spec.ts` |
| **TASK-07** | توسعه کنترل‌های انتخابگر Shape Divider در پنل بازرس | P1 | **TODO** | Frontend Engineer | `frontend/components/admin/builder/inspector-panel.tsx` |
| **TASK-08** | توسعه کنترل‌های Flex Wrap و استایل‌های وضعیت هاور | P2 | **TODO** | Frontend Engineer | `frontend/components/admin/builder/inspector-panel.tsx` |
