# Initial Project Reconnaissance & Builder Architecture Audit

**Date**: 2026-11-21  
**Working Directory**: `C:\Users\Administrator\Desktop\site\.claude\worktrees\hungry-khorana-4f765b`  
**Git Branch**: `claude/hungry-khorana-4f765b` (Clean working tree)  
**Main Branch**: `main`  
**Reference Source**: `C:\Users\Administrator\Desktop\elementor` (Read-only, Elementor & Elementor Pro)

---

## 1. Executive Summary

This project encompasses a production-grade Visual Page Builder built for an Iranian e-commerce & CMS platform. The builder enables visual composition of CMS pages and landing pages with real-time WYSIWYG fidelity, bidirectional RTL layout support, responsive breakpoint editing (Desktop, Tablet 768px, Mobile 375px), deep undo/redo history, template management, and server-side AST compilation.

---

## 2. Environment & System Architecture

### 2.1 Workspace and Services
- **OS**: Windows 10 Pro (x64)
- **Node.js**: v20.x, npm, Next.js 15.5.25
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2 (asyncpg)
- **Database Services**:
  - PostgreSQL (Docker, port 5432)
  - Redis (Docker, port 6379)
  - Elasticsearch (local/Docker, port 9200)
- **Testing Runtimes**:
  - Frontend Unit/Integration: Vitest (`npm test`)
  - Type-checking: `tsc --noEmit`
  - E2E & Browser Automation: Playwright with Chromium headless (`@playwright/test`)
  - Backend Unit: Pytest (`python -m pytest app/tests/unit`)

### 2.2 Primary Builder Codebase Structure
```
frontend/
├── components/admin/builder/
│   ├── builder-studio.tsx               # Main 3-column studio layout, toolbar, state bridge
│   ├── builder-toolbar.tsx              # Top navigation, responsive mode switcher, preview, actions
│   ├── blocks-palette.tsx               # Blocks (34), Patterns (28), Templates (3-tab sidebar)
│   ├── layers-tree.tsx                  # Navigator tree, DnD reorder, search, expand/collapse
│   ├── canvas-frame.tsx                 # Isolated iframe canvas with 2-layer design token injection
│   ├── canvas-dnd-layer.tsx             # @dnd-kit/core drag & drop integration inside canvas
│   ├── canvas-element.tsx               # Recursive AST renderer for containers & widgets
│   ├── canvas-overlay-layer.tsx         # Root overlay portal for selection & floating toolbar
│   ├── inspector-panel.tsx              # 3-tab inspector (Content, Style, Advanced)
│   ├── global-styles-dialog.tsx         # Page-level design tokens (colors, typography, radius)
│   ├── save-template-dialog.tsx         # Container section template export dialog
│   ├── save-page-template-dialog.tsx    # Full page template export dialog
│   ├── container-preset-picker.tsx      # 6 ready-made column layouts for empty containers
│   ├── builder-context-menu.tsx         # Right-click context menu (duplicate, delete, wrap, unwrap)
│   ├── history-panel.tsx                # Revision history timeline and jump-to-state
│   └── hotkeys-dialog.tsx               # Keyboard shortcuts cheat sheet (Ctrl+Z, Ctrl+D, etc.)
├── stores/
│   └── builder-store.ts                 # Zustand reactive state, AST mutations, undo/redo past/future
├── lib/builder/
│   ├── block-registry.ts                # 34 basic block definitions & factory methods
│   ├── pattern-converter.ts             # 28 block patterns converter & HTML generator
│   ├── schema.ts                        # Zod schema validation for PageAST & BuilderElement
│   └── theme-schema.ts                  # HSL color conversion & CSS variable token extraction
└── types/
    └── builder.ts                       # TypeScript interfaces for AST, Styles, Layout, & Widgets
```

### 2.3 Backend Services
```
backend/app/modules/content/
├── domain/
│   ├── builder_ast.py                   # Pydantic models for AST validation
│   └── builder_validation.py            # AST validation rules, schema version checks
├── application/
│   ├── ast_compiler.py                  # Compiles JSON AST to production HTML
│   ├── html_sanitizer.py                # Server-side HTML security sanitizer
│   ├── cms_page_service.py              # CMS page CRUD, draft/publish lifecycle
│   └── form_submission_service.py       # Builder form container submissions & spam protection
```

---

## 3. Elementor & Elementor Pro Reference Status

The local reference repository at `C:\Users\Administrator\Desktop\elementor` contains full source code for:
- **Elementor Core**: `elementor/includes/`
  - `base/controls-stack.php`: Unified control registration stack
  - `container/container.php`: Flexbox & Grid modern container engine
  - `editor-templates/`: Navigator, Panel, Library layout, Responsive bar
- **Elementor Pro**: `elementor-pro/modules/`
  - Display Conditions (`display-conditions/`): Device, authentication, role-based visibility
  - Custom CSS & Attributes (`custom-css/`, `custom-attributes/`)
  - Motion Effects & Animations (`motion-fx/`)
  - Forms & Submissions (`forms/`)
  - Global Widgets & Templates (`theme-builder/`, `assets-manager/`)

---

## 4. Current Test Baseline Status
- **Vitest Unit Tests**: `tests/builder-schema.test.ts`, `tests/builder-store.test.ts` (17 passed)
- **TypeScript Typecheck**: `tsc --noEmit` (0 errors)
- **Playwright E2E**:
  - `tests/e2e/builder-gym-r01.spec.ts`: 3/3 passed (10.1s)
  - Regression suite: 18 rounds covered in `.loop/BUILDER_GYM_LOG.md` and `.loop/EXCAVATOR_LOG.md`
- **Initial P0 Defect Status**:
  1. `layers-tree.tsx`: `depth * 24px` RTL indentation verified and active.
  2. `canvas-element.tsx`: Empty container dashed guide min-height updated to `80px` with clear Persian action text.
  3. `builder-store.ts`: Initial selection set to `null` to eliminate pointer event interception on initial load.
  4. `canvas-element.tsx`: Button widget text wrapped with `<span className="truncate">` for exact selector and overflow safety.
