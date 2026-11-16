# Visual Page Builder Phase P2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase P2.0 of Visual Page Builder: DTCG-compliant Design Tokens, SiteTheme & ThemeRevision backend models with Alembic migration, Global Styles manager in Builder Studio, isolated CSS variable propagation in CanvasFrame, and Media Library picker in Image Inspector.

**Architecture:** A unified Design Token System based on the DTCG (Design Tokens Community Group) specification. Backend persistence via PostgreSQL `site_themes` and `theme_revisions` tables with a partial unique index guaranteeing exactly one active theme. Pydantic v2 and Zod schemas enforce type safety and token resolution. Frontend Builder Studio manages global brand styles (Primary, Secondary, Typography, Radius) synchronized with CanvasFrame's isolated iframe `:root` CSS variables, while the Image Inspector integrates with the existing Strapi-style `MediaPicker`.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2, PostgreSQL (JSONB), TypeScript, Next.js 15, React 19, Tailwind CSS, Radix UI, Zustand, Vitest, Pytest, Playwright.

**Spec:** Phase P2.0 specification from prompt instructions, `docs/UI_UX_DESIGN_SYSTEM.md`, and `backend/alembic/versions/2026_11_14_pagebld1_add_builder_data_and_page_templates.py`.

## Global Constraints

- Never mutate or overwrite the real `showcase` page in any automated test; all E2E tests must run against `e2e-isolated-scratchpad`.
- Never execute destructive or irreversible migrations; all Alembic migrations must have a fully tested `downgrade()` function.
- Do not modify `backend/app/modules/audit/application/audit_service.py`; use `log_action` for audit logging.
- Retain all 28 existing block patterns intact without altering their IDs, visual identity, or nested AST decomposition.
- Keep the canvas iframe strictly isolated; CSS variables must not leak into the parent Admin Studio shell.
- Preserve manual URL entry for images while offering the Media Library picker.
- Target branch is `feature/design-system-p2-core`, kept isolated until approved for PR merge.

## Review Focus

1. Partial unique index on `site_themes.is_active`: Activating a theme must atomically deactivate the previously active theme, preventing multiple active themes.
2. DTCG token alias resolution: An alias reference like `"{color.primary.500}"` must resolve cleanly without circular dependency or crash.
3. Canvas iframe style isolation: Changing Global Styles in studio updates only the iframe `:root` styles, never the Admin UI shell.
4. Media Library integration: Selecting an asset from `MediaPicker` populates `widgetProps.url` and triggers autosave without breaking manual typing.
5. Migration downgrade: Running `alembic downgrade -1` cleanly removes `site_themes`, `theme_revisions`, and `page_templates.category` without leaving orphan indices.

---

### Task 1: Create Feature Branch & Backend Domain Models

**Files:**
- Create: `backend/app/modules/content/domain/theme_models.py`
- Modify: `backend/app/modules/content/domain/models.py:315-337`
- Test: `backend/app/tests/unit/test_theme_models.py`

**Interfaces:**
- Produces: `SiteTheme`, `ThemeRevision` SQLAlchemy models in `app.modules.content.domain.theme_models`.
- Updates: `PageTemplate` model with `category: Mapped[str | None]`.

- [ ] **Step 1: Create feature branch `feature/design-system-p2-core`**
Run: `git checkout -b feature/design-system-p2-core`

- [ ] **Step 2: Write failing unit tests for theme models**
Write tests in `backend/app/tests/unit/test_theme_models.py` verifying model instantiation, default values, relationship with revisions, and `category` attribute on `PageTemplate`.

- [ ] **Step 3: Run test to verify it fails**
Run: `pytest backend/app/tests/unit/test_theme_models.py -v`
Expected: FAIL with Import/AttributeError.

- [ ] **Step 4: Implement `SiteTheme` and `ThemeRevision` models**
Create `backend/app/modules/content/domain/theme_models.py` with `SiteTheme` and `ThemeRevision` mapped classes inheriting from `BaseModel`, including `is_active` boolean, `tokens` JSONB column, and foreign keys. Add `category` to `PageTemplate` in `models.py`.

- [ ] **Step 5: Run test to verify it passes**
Run: `pytest backend/app/tests/unit/test_theme_models.py -v`
Expected: PASS

- [ ] **Step 6: Commit**
Run:
```bash
git add backend/app/modules/content/domain/theme_models.py backend/app/modules/content/domain/models.py backend/app/tests/unit/test_theme_models.py
git commit -m "feat(content): add SiteTheme and ThemeRevision models and PageTemplate category"
```

---

### Task 2: DTCG Design Token Schemas (Pydantic v2 & Zod)

**Files:**
- Create: `backend/app/modules/content/schemas/theme.py`
- Create: `frontend/lib/builder/theme-schema.ts`
- Test: `backend/app/tests/unit/test_theme_schemas.py`
- Test: `frontend/tests/theme-schema.test.ts`

**Interfaces:**
- Produces: `DesignTokensSchema`, `SiteThemeCreateRequest`, `SiteThemeUpdateRequest`, `SiteThemeResponse` in backend.
- Produces: `DesignTokensZodSchema`, `DTCGToken`, `extractCssVariablesFromTokens` in frontend.

- [ ] **Step 1: Write failing backend test for Pydantic DTCG schemas**
Write `backend/app/tests/unit/test_theme_schemas.py` testing validation of `$value`, `$type`, alias references, and token grouping.

- [ ] **Step 2: Run backend test to verify it fails**
Run: `pytest backend/app/tests/unit/test_theme_schemas.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Pydantic DTCG schema in `backend/app/modules/content/schemas/theme.py`**
Define `DTCGToken`, `TokenGroup`, `DesignTokensSchema`, `SiteThemeCreateRequest`, and `SiteThemeResponse`.

- [ ] **Step 4: Run backend test to verify it passes**
Run: `pytest backend/app/tests/unit/test_theme_schemas.py -v`
Expected: PASS

- [ ] **Step 5: Write failing frontend Vitest test for Zod DTCG schema & CSS variable generator**
Write `frontend/tests/theme-schema.test.ts` testing schema parsing and conversion of tokens to CSS variable map (`--primary`, `--secondary`, `--radius`, `--font-family`).

- [ ] **Step 6: Run frontend test to verify it fails**
Run: `cd frontend && npx vitest run tests/theme-schema.test.ts`
Expected: FAIL

- [ ] **Step 7: Implement Zod DTCG schema & helper in `frontend/lib/builder/theme-schema.ts`**
Export `DesignTokensZodSchema`, `DEFAULT_THEME_TOKENS`, and `extractCssVariablesFromTokens(tokens)`.

- [ ] **Step 8: Run frontend test to verify it passes**
Run: `cd frontend && npx vitest run tests/theme-schema.test.ts`
Expected: PASS

- [ ] **Step 9: Commit**
```bash
git add backend/app/modules/content/schemas/theme.py backend/app/tests/unit/test_theme_schemas.py frontend/lib/builder/theme-schema.ts frontend/tests/theme-schema.test.ts
git commit -m "feat(theme): add DTCG design token schemas in Pydantic v2 and Zod"
```

---

### Task 3: Alembic Migration `themetok1` (Upgrade & Downgrade)

**Files:**
- Create: `backend/alembic/versions/2026_11_16_themetok1_add_site_themes_and_page_template_category.py`
- Test: `backend/app/tests/unit/test_theme_migration.py`

**Interfaces:**
- Consumes: `pagebld1` (head).
- Produces: `themetok1` (new head) creating `site_themes`, `theme_revisions`, partial index `uq_site_themes_is_active`, and column `page_templates.category`.

- [ ] **Step 1: Write Alembic migration script**
Create `backend/alembic/versions/2026_11_16_themetok1_add_site_themes_and_page_template_category.py` with `upgrade()` and clean `downgrade()`. Include partial index:
`CREATE UNIQUE INDEX uq_site_themes_is_active ON site_themes (is_active) WHERE is_active = true;`

- [ ] **Step 2: Write test verifying migration upgrade and rollback**
Write `backend/app/tests/unit/test_theme_migration.py` verifying SQL statements generated and rollback cleanliness.

- [ ] **Step 3: Run Alembic upgrade and test**
Run: `cd backend && python -m alembic upgrade head`
Run: `pytest app/tests/unit/test_theme_migration.py -v`
Expected: PASS

- [ ] **Step 4: Verify migration rollback (downgrade)**
Run: `cd backend && python -m alembic downgrade -1 && python -m alembic upgrade head`
Expected: Downgrade and Upgrade complete with exit code 0.

- [ ] **Step 5: Commit**
```bash
git add backend/alembic/versions/2026_11_16_themetok1_add_site_themes_and_page_template_category.py backend/app/tests/unit/test_theme_migration.py
git commit -m "feat(migration): add site_themes, theme_revisions and page_templates category"
```

---

### Task 4: Theme Service & Backend Admin API

**Files:**
- Create: `backend/app/modules/content/application/theme_service.py`
- Modify: `backend/app/modules/content/api/routes.py`
- Test: `backend/app/tests/unit/test_theme_service.py`

**Interfaces:**
- Produces: `GET /api/v1/content/themes/active`, `GET /api/v1/content/admin/themes`, `POST /api/v1/content/admin/themes`, `PATCH /api/v1/content/admin/themes/{id}`, `POST /api/v1/content/admin/themes/{id}/activate`.

- [ ] **Step 1: Write failing test for theme service and endpoints**
Write `backend/app/tests/unit/test_theme_service.py` testing creation, update, listing, and single-active-theme activation.

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest backend/app/tests/unit/test_theme_service.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `theme_service.py` and routes**
Implement CRUD service with revision snapshots and atomic activation. Register routes in `app/modules/content/api/routes.py` with `RequirePermissions("settings:write")`.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest backend/app/tests/unit/test_theme_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/modules/content/application/theme_service.py backend/app/modules/content/api/routes.py backend/app/tests/unit/test_theme_service.py
git commit -m "feat(content): implement theme management service and admin API routes"
```

---

### Task 5: Global Styles Manager & CSS Variable Injection in CanvasFrame

**Files:**
- Create: `frontend/components/admin/builder/global-styles-dialog.tsx`
- Modify: `frontend/components/admin/builder/builder-toolbar.tsx`
- Modify: `frontend/components/admin/builder/canvas-frame.tsx`
- Modify: `frontend/stores/builder-store.ts`
- Test: `frontend/tests/global-styles.test.ts`

**Interfaces:**
- Produces: `globalStyles` management in `builder-store.ts`.
- Injects: Dynamic CSS variables into iframe `:root` inside `CanvasFrame`.

- [ ] **Step 1: Write failing frontend test for Global Styles state & CSS variable extraction**
Write `frontend/tests/global-styles.test.ts` testing store action `updateGlobalStyles` and its serialization into `PageAST.globalStyles`.

- [ ] **Step 2: Run test to verify it fails**
Run: `cd frontend && npx vitest run tests/global-styles.test.ts`
Expected: FAIL

- [ ] **Step 3: Add `globalStyles` state & action in `builder-store.ts`**
Add `updateGlobalStyles(patch)` in `builder-store.ts` updating `ast.globalStyles` and setting `isDirty = true`.

- [ ] **Step 4: Implement `GlobalStylesDialog` component**
Create `frontend/components/admin/builder/global-styles-dialog.tsx` with color pickers for Primary, Secondary, Font selector (Vazirmatn/system), and Border Radius slider.

- [ ] **Step 5: Connect Global Styles to `BuilderToolbar`**
Add a "استایل‌های سراسری" (Global Styles) button with `Paintbrush` icon in `builder-toolbar.tsx` that opens `GlobalStylesDialog`.

- [ ] **Step 6: Inject CSS Variables into Iframe in `canvas-frame.tsx`**
In `canvas-frame.tsx`, read `ast.globalStyles` from store and inject `--primary`, `--secondary`, `--radius`, `--font-vazirmatn` directly into `doc.documentElement.style` inside the iframe.

- [ ] **Step 7: Run frontend test to verify it passes**
Run: `cd frontend && npx vitest run tests/global-styles.test.ts`
Expected: PASS

- [ ] **Step 8: Commit**
```bash
git add frontend/components/admin/builder/global-styles-dialog.tsx frontend/components/admin/builder/builder-toolbar.tsx frontend/components/admin/builder/canvas-frame.tsx frontend/stores/builder-store.ts frontend/tests/global-styles.test.ts
git commit -m "feat(builder): implement Global Styles manager and iframe CSS variable injection"
```

---

### Task 6: Media Library Integration in Image Inspector

**Files:**
- Modify: `frontend/components/admin/builder/inspector-panel.tsx`
- Test: `frontend/tests/image-inspector-media.test.ts`

**Interfaces:**
- Consumes: `MediaPicker` from `components/admin/media-picker.tsx`.
- Connects: Image widget props (`url`, `alt`) to modal asset selection.

- [ ] **Step 1: Write failing test for Image Inspector with MediaPicker**
Write `frontend/tests/image-inspector-media.test.ts` verifying that `MediaPicker` is rendered in Image Inspector and calls `updateElementProps` with chosen image URL.

- [ ] **Step 2: Run test to verify it fails**
Run: `cd frontend && npx vitest run tests/image-inspector-media.test.ts`
Expected: FAIL

- [ ] **Step 3: Integrate `MediaPicker` in `inspector-panel.tsx`**
In `inspector-panel.tsx` under `case "image"`, include `MediaPicker` component alongside the existing URL input, preserving manual URL typing while offering one-click media selection from `/admin/media`.

- [ ] **Step 4: Run test to verify it passes**
Run: `cd frontend && npx vitest run tests/image-inspector-media.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add frontend/components/admin/builder/inspector-panel.tsx frontend/tests/image-inspector-media.test.ts
git commit -m "feat(builder): integrate Media Library picker in Image Inspector"
```

---

### Task 7: Full E2E Verification & Regression Guarding

**Files:**
- Create: `frontend/tests/e2e/p2-core-verification.spec.ts`
- Test: `frontend/tests/e2e/patterns-and-showcase-regression.spec.ts`

**Interfaces:**
- Tests: End-to-end flow of Global Styles, iframe color updates, Media Library picker on image block, saving draft, reloading, and confirming 28 block patterns remain 100% green on `e2e-isolated-scratchpad`.

- [ ] **Step 1: Write Playwright E2E test `p2-core-verification.spec.ts`**
Write tests covering:
1. Opening Global Styles dialog, changing primary color, verifying CSS variable updates in iframe.
2. Selecting an image element, opening MediaPicker, choosing an image.
3. Saving draft and verifying persistence of `globalStyles` on `e2e-isolated-scratchpad`.
4. Verifying Showcase is never modified.

- [ ] **Step 2: Run all Playwright E2E suites**
Run: `cd frontend && npx playwright test tests/e2e/p2-core-verification.spec.ts tests/e2e/patterns-and-showcase-regression.spec.ts`
Expected: PASS

- [ ] **Step 3: Run all Vitest and Pytest test suites**
Run: `npm test` in frontend.
Run: `pytest` in backend.
Expected: All PASS.

- [ ] **Step 4: Commit**
```bash
git add frontend/tests/e2e/p2-core-verification.spec.ts
git commit -m "test(builder): add E2E verification suite for P2.0 Global Styles and Media Picker"
```
