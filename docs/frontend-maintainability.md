# Frontend Maintainability Guide

## Purpose

This guide defines how to keep the dashboard maintainable while staying server-rendered and framework-free (Jinja2 + vanilla HTML/CSS/JS).

Use this before changing templates, styles, or dashboard JavaScript.

## Frontend Architecture

Current frontend modules:

- `templates/index.html`: page composition from partials
- `templates/partials/dashboard/*.html`: dashboard sections and table templates
- `static/js/dashboard_dom.js`: DOM collection and binding validation
- `static/js/dashboard_utils.js`: pure formatting and normalization helpers
- `static/js/dashboard_panels.js`: UI renderers and table row rendering
- `static/js/app.js`: state orchestration, events, fetch calls, tab flow
- `static/css/style.css`: visual system and responsive behavior

Core rule:

- `app.js` controls state and side effects
- `dashboard_panels.js` renders from data to DOM
- `dashboard_utils.js` stays pure and reusable

## Maintainability Rules

### 1. Keep modules single-purpose

- Avoid mixing network requests with row rendering.
- Do not put application state mutations in utility functions.
- Keep rendering helpers reusable and deterministic.

### 2. Prefer config-driven rendering

For record tables, use shared row rendering helpers instead of repeated loops.

- Use shared utilities in `dashboard_panels.js`:
  - `renderRecordTableRows(...)`
  - `renderTableBodyRows(...)`
  - `setCellText(...)`
  - `configureModerationButton(...)`
  - `insertArtifactLinks(...)`

### 3. Avoid magic numbers in tables

- Do not hardcode `colspan` in JavaScript.
- Keep empty row fallback text in the section/template where possible.
- Let shared table helpers derive column count from `<thead>`.

### 4. Fail loudly for missing DOM bindings

`dashboard_dom.js` validates required element bindings and tab panels.

If IDs or panels are renamed in templates, update DOM bindings in the same change.

### 5. Keep status mapping centralized

- Badge class mapping should use shared functions (`actionBadgeClass`, shared status helpers).
- Do not duplicate status string logic in multiple renderers.

### 6. Keep text normalization consistent

- Use `normalizeTextValue(...)` from `dashboard_utils.js` for user or API strings.
- Avoid ad-hoc string trimming logic scattered in renderers.

## How To Add A New Session Workspace Table

1. Add section markup in:
   - `templates/partials/dashboard/records_panel.html`
2. Add a row template in:
   - `templates/partials/dashboard/record_templates.html`
3. Bind new DOM IDs in:
   - `static/js/dashboard_dom.js`
4. Add a renderer in:
   - `static/js/dashboard_panels.js`
   - use `renderRecordTableRows(...)` for row and empty-state handling
5. Wire data flow in:
   - `static/js/app.js` (`applyDashboardState`, counts, tab behavior)

## PR Checklist For Frontend Changes

- Templates render without missing IDs
- `dashboard_dom.js` has no missing-binding warnings
- Active, Events, History, Unmatched, Logs tabs still switch correctly
- Empty table states render correctly
- Deletion and artifact actions still work
- `/dashboard/snapshot` updates all affected sections
- Mobile and narrow-width layout still readable
- No inline style hacks introduced

## Anti-Patterns To Avoid

- Building large HTML strings manually for table rows
- Repeating the same table rendering loop in multiple functions
- Hardcoding endpoint-specific logic inside generic render helpers
- Silent failures when required DOM nodes are missing
- Mixing UI formatting rules directly into fetch/update logic

## Recommended Way To Extend

When adding UI behavior:

1. Add/adjust API payload handling in `app.js`
2. Add formatting helpers in `dashboard_utils.js` if needed
3. Render in `dashboard_panels.js` via existing shared helpers
4. Bind required elements in `dashboard_dom.js`
5. Add template markup last, matching established IDs/class names

This order keeps changes reviewable and prevents hidden coupling.
