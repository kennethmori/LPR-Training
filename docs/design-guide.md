# Design Guide

## Design Direction

Minimalist and professional. The dashboard should feel like an internal operations tool built by engineers, not a marketing page.

Rules that define this direction:

- remove anything that does not help the operator read data faster
- prefer flat surfaces over layered glass effects
- prefer whitespace over decorative fills
- prefer one accent color over a palette
- prefer system fonts over branded typefaces
- prefer sharp alignment over rounded softness
- let data be the visual focus, not the container it sits in

## Design Principles

### 1. Data density over decoration

Every pixel should either show data or provide breathing room for data. No ornamental gradients, no illustrative backgrounds, no drop shadows that exist purely for aesthetics.

### 2. One-glance comprehension

A campus operator should know the system state within two seconds. This means: status indicators visible without scrolling, active session count prominent, plate reads large and clear.

### 3. Honest state

If the detector is not loaded, say "Not ready." If the camera is disconnected, show it. Never render placeholder data that could be confused with a real result.

### 4. Quiet confidence

The interface should look like it was built by someone who knows what they are doing. No gimmicks, no animations that exist for fun, no color used without purpose.

## Color System

### Palette

Keep the palette extremely tight. One primary accent, one neutral scale, and three semantic status colors.

```css
:root {
    --accent: #0f3f78;
    --accent-hover: #0a274c;

    --bg: #ffffff;
    --bg-subtle: #f7f8fa;
    --bg-inset: #f0f2f5;

    --text: #111827;
    --text-secondary: #6b7280;
    --text-tertiary: #9ca3af;

    --border: #e5e7eb;
    --border-strong: #d1d5db;

    --status-ok: #16a34a;
    --status-warn: #ca8a04;
    --status-error: #dc2626;
}
```

### Color rules

- the accent color appears only on primary buttons, active indicators, and the header bar
- body backgrounds are white or near-white; never tinted or gradient
- borders are thin (1px) and light gray
- status colors appear only on small indicators (dots, badges, inline text) — never as panel backgrounds
- never use color as the sole differentiator; always pair with a text label

## Typography

### Font stack

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
```

System sans-serif. Fast to load, native to every platform, no font files to manage. A serif font has no place in an operations dashboard.

### Monospace stack (for plate numbers and debug output)

```css
font-family: "SF Mono", "Cascadia Code", "Consolas", monospace;
```

### Type scale

| Role | Size | Weight | Letter spacing |
| --- | --- | --- | --- |
| App title | `1.25rem` | `600` | `0` |
| Panel heading | `0.8rem` | `600` | `0.04em`, uppercase |
| Body | `0.875rem` | `400` | `0` |
| Label | `0.75rem` | `500` | `0.02em`, uppercase |
| Value | `0.875rem` | `400` | `0` |
| Plate number | `1.5rem` | `700` | `0.1em`, monospace |
| Badge | `0.7rem` | `500` | `0.05em`, uppercase |
| Code / JSON | `0.8rem` | `400` | `0`, monospace |

### Typography rules

- headers are small and uppercase; they identify sections, they do not dominate
- the plate number is the loudest text on the page
- body text is 14px equivalent (`0.875rem`); dense but readable
- never bold an entire paragraph; bold only labels and headings
- line-height is `1.5` for body text, `1.2` for headings

## Spacing

### Base unit

All spacing derives from a 4px base:

| Token | Value | Usage |
| --- | --- | --- |
| `--space-1` | `4px` | Tight internal gaps |
| `--space-2` | `8px` | Between related elements |
| `--space-3` | `12px` | Between components in a group |
| `--space-4` | `16px` | Panel internal padding |
| `--space-5` | `20px` | Between panels |
| `--space-6` | `24px` | Section separation |
| `--space-8` | `32px` | Page margin |

### Spacing rules

- panel internal padding: `16px`
- gap between panels: `20px` (reduced from current `18px` for 4px-grid alignment)
- page shell max-width: `1360px`, centered
- never use inconsistent spacing; every gap should trace back to the base unit

## Layout

### Grid

Three-column grid for the main workspace:

```css
.layout {
    display: grid;
    grid-template-columns: 260px 1fr 300px;
    gap: 20px;
}
```

- left: controls and status (narrow, fixed)
- center: camera feed or uploaded image (fluid)
- right: recognition results (narrow, fixed)

Session tables, event logs, and history panels go below the main grid as full-width sections.

### Responsive

Single breakpoint at `1024px`:

```css
@media (max-width: 1024px) {
    .layout {
        grid-template-columns: 1fr;
    }
}
```

No tablet-specific layouts. The UI either runs on a desktop monitor or collapses to a single column.

## Surfaces

### Panels

Panels are flat white containers with a thin border:

```css
.panel {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
}
```

No shadows. No backdrop blur. No transparency. The border alone defines the boundary.

Border radius is `8px` maximum. This is an operations tool, not a consumer app.

### Inset areas

Camera frames, plate crop previews, and code blocks use a slightly recessed background:

```css
.inset {
    background: var(--bg-inset);
    border: 1px solid var(--border);
    border-radius: 6px;
}
```

### Header

The header is the only element that uses the accent color:

```css
.header {
    background: var(--accent);
    color: #ffffff;
    padding: 16px 20px;
    border-radius: 8px;
}
```

No gradient. Flat fill. The header is compact — one line for the app title, one line for the subtitle, a status badge on the right.

## Components

### Buttons

```css
button {
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s ease;
}

.btn-primary {
    background: var(--accent);
    color: #ffffff;
}

.btn-primary:hover {
    background: var(--accent-hover);
}

.btn-secondary {
    background: var(--bg-inset);
    color: var(--text);
    border: 1px solid var(--border);
}

.btn-secondary:hover {
    background: var(--border);
}

button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}
```

Button rules:

- no transform on hover (no `translateY`, no scale)
- no shadows on buttons
- full-width inside narrow panels, auto-width in headers and inline contexts
- label text is short: "Start Camera", "Stop", "Upload", "Refresh"

### Status indicators

Use small colored dots paired with text:

```css
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
}

.status-dot.ok    { background: var(--status-ok); }
.status-dot.warn  { background: var(--status-warn); }
.status-dot.error { background: var(--status-error); }
.status-dot.idle  { background: var(--text-tertiary); }
```

Always show text next to the dot. A green dot without "Ready" is ambiguous.

### Data rows

Label-value pairs use a simple flex row:

```css
.data-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 6px 0;
    border-bottom: 1px solid var(--border);
    font-size: 0.875rem;
}

.data-row:last-child {
    border-bottom: none;
}

.data-label {
    font-weight: 500;
    color: var(--text);
}

.data-value {
    color: var(--text-secondary);
    text-align: right;
}
```

### Plate number display

The recognized plate is the single most important piece of data:

```css
.plate-display {
    font-family: "SF Mono", "Cascadia Code", "Consolas", monospace;
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    color: var(--text);
    text-align: center;
    padding: 12px;
    background: var(--bg-inset);
    border: 1px solid var(--border-strong);
    border-radius: 6px;
}
```

Monospaced, large, centered, and visually distinct from everything else on the page.

### Tables

```css
.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
}

.data-table th {
    text-align: left;
    padding: 8px 12px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-secondary);
    border-bottom: 2px solid var(--border);
}

.data-table td {
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    color: var(--text);
}

.data-table tr:hover {
    background: var(--bg-subtle);
}
```

Table rules:

- headers are small, muted, and uppercase
- data rows are the focus
- right-align numeric columns
- no zebra striping; hover highlight only
- cap visible rows at a reasonable default; use scroll for overflow

### Badges

Small inline pills for status and event types:

```css
.badge {
    display: inline-block;
    padding: 2px 8px;
    font-size: 0.7rem;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border-radius: 4px;
    background: var(--bg-inset);
    color: var(--text-secondary);
}

.badge.live  { background: #dcfce7; color: #166534; }
.badge.open  { background: #dbeafe; color: #1e40af; }
.badge.closed { background: var(--bg-inset); color: var(--text-secondary); }
.badge.error { background: #fee2e2; color: #991b1b; }
```

### Image frames

```css
.frame {
    background: var(--bg-inset);
    border: 1px solid var(--border);
    border-radius: 6px;
    min-height: 300px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}

.frame img {
    width: 100%;
    height: 100%;
    object-fit: contain;
}
```

No decorative gradients inside the frame. The image is the content.

### Code blocks

```css
pre {
    margin: 0;
    padding: 12px;
    border-radius: 6px;
    background: #1e293b;
    color: #e2e8f0;
    font-family: "SF Mono", "Cascadia Code", "Consolas", monospace;
    font-size: 0.8rem;
    line-height: 1.5;
    overflow: auto;
}
```

## Dashboard Sections

### Current sections (keep)

1. **Header** — app title, university, status badge
2. **Controls** — upload form, camera buttons, system status
3. **Source view** — annotated image or live MJPEG stream
4. **Recognition result** — plate crop, plate number, confidences, metadata

### Planned sections (add when session layer is built)

5. **Active sessions** — table of open vehicle visits
6. **Recent events** — table of latest recognition events with action taken
7. **Session history** — table of completed sessions
8. **Unmatched exits** — list of exit reads with no matching entry (collapsible)

### Section order on page

```
┌─────────────────────────────────────────────┐
│  Header                        [LIVE badge] │
├───────────┬─────────────────┬───────────────┤
│ Controls  │  Source View    │  Recognition  │
│ Upload    │  (feed/image)  │  Result       │
│ Camera    │                 │  Plate: ABC   │
│ Status    │                 │  Conf: 0.95   │
├───────────┴─────────────────┴───────────────┤
│  Active Sessions                            │
├─────────────────────────────────────────────┤
│  Recent Events                              │
├─────────────────────────────────────────────┤
│  Session History                            │
├─────────────────────────────────────────────┤
│  ▸ Unmatched Exits (collapsed by default)   │
└─────────────────────────────────────────────┘
```

## Interaction Rules

### Polling

- status and result polling: every 3 seconds when a camera is live
- session table refresh: every 5 seconds or on new event
- no polling when camera is stopped and no upload is in progress

### State transitions

- uploading an image: badge shows `PROCESSING`, upload button disabled, result updates on completion
- starting camera: source view swaps to MJPEG stream, badge shows `LIVE`
- stopping camera: source view shows last frame or placeholder, badge shows `IDLE`
- new session event: active sessions table updates, recent events table prepends new row

### Animations

Only two are permitted:

1. `transition: background 0.15s ease` on buttons and table rows (hover feedback)
2. `transition: opacity 0.2s ease` on elements appearing or disappearing

No transforms. No keyframe animations. No bouncing, sliding, or fading in from off-screen.

### Error display

- API errors render in the JSON debug block
- status badge updates to system state, not an error label
- never use alert dialogs or toasts

## Accessibility

- all `<img>` elements require `alt` attributes
- all form inputs require `<label>` elements
- color is never the sole indicator; always paired with text
- tab order follows visual layout: controls → source → results → tables
- focus states use `outline: 2px solid var(--accent)` with `outline-offset: 2px`
- minimum touch target: `32px` height for buttons

## File Ownership

| File | Responsibility |
| --- | --- |
| `templates/index.html` | Semantic HTML structure, Jinja2 bindings |
| `static/css/style.css` | All visual rules, tokens, layout, responsive |
| `static/js/app.js` | API calls, DOM updates, polling, state toggling |

### Rules

- no inline styles in HTML templates
- no style manipulation in JavaScript; use class toggling (`classList.add`, `classList.remove`)
- CSS is organized: tokens → reset → layout → header → panels → components → tables → responsive
- no CSS framework dependencies

## Naming

### CSS classes

Lowercase kebab-case:

- `data-row`, `data-label`, `data-value`
- `status-dot`, `plate-display`, `data-table`
- state classes prefixed with `is-`: `is-active`, `is-disabled`, `is-live`

### Element IDs

camelCase, for JavaScript references:

- `plateText`, `detectorStatus`, `statusBadge`, `uploadForm`

### Data attributes

For runtime state read by JavaScript:

- `data-camera-role="entry"`, `data-session-status="open"`

## What This Guide Excludes

- backend API contracts (see architecture.md)
- database schema (see architecture.md)
- deployment and infrastructure
- mobile-native layouts
- print stylesheets
- marketing or landing pages
