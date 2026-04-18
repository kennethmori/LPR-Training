# Frontend Implementation Prompt

## Purpose

This document is a standalone frontend implementation prompt for the next major dashboard stage of the USM License Plate Recognition Prototype.

Use it when you want to work on the operator UI separately from the backend/system build.

## Copy-Paste Prompt

```text
You are implementing the frontend/dashboard layer for the USM License Plate Recognition Prototype.

Use the existing repository docs and current backend code as your source of truth. Read the current implementation first, but align your changes with:
- README.md
- docs/architecture.md
- docs/design-guide.md
- docs/CONTEXT.md
- docs/implementation-roadmap.md
- docs/session-flow.md
- docs/missing-pieces.md
- docs/known-issues.md

Project identity:
- local-first operations dashboard for a two-stage plate-recognition and vehicle-session system
- FastAPI + Jinja2 + vanilla JavaScript + CSS
- not a marketing site
- not a SPA
- not React

Current UI foundation:
- server-rendered FastAPI dashboard already exists
- still-image upload flow already exists
- live camera panel already exists for the current single-camera mode
- status reporting already exists

Critical frontend rules you must preserve:
- keep the frontend server-rendered with Jinja2 plus vanilla JavaScript
- follow `docs/design-guide.md`
- keep the UI minimalist, professional, data-dense, and honest
- never show fake readiness or placeholder operational data that could be mistaken for real output
- do not introduce a heavy frontend framework
- let data be the focus, not decoration

Main frontend goal:
Turn the current recognition dashboard into a clear operator dashboard for entry, exit, events, and vehicle sessions.

The final dashboard should support:
1. system readiness visibility
2. still-image inference
3. entry camera monitoring
4. exit camera monitoring
5. current recognition state
6. active sessions
7. recent events
8. session history
9. unmatched exits

Assume the backend provides or will provide these endpoints:
- `GET /`
- `POST /predict/image`
- `GET /status`
- `POST /cameras/{role}/start`
- `POST /cameras/{role}/stop`
- `GET /cameras/{role}/stream`
- `GET /cameras/{role}/latest-result`
- `GET /sessions/active`
- `GET /sessions/history`
- `GET /events/recent`
- `GET /events/unmatched-exit`

Frontend implementation scope:

Phase 1: Template structure
- update `templates/index.html` into a more complete operator layout
- keep the page server-rendered
- organize the page into clear sections:
  - header and readiness
  - controls and upload
  - entry camera panel
  - exit camera panel
  - recognition result panel
  - active sessions table
  - recent events table
  - session history table
  - unmatched exits panel

Phase 2: Visual design alignment
- apply the design system in `docs/design-guide.md`
- preserve the intended visual direction:
  - flat surfaces
  - thin borders
  - system fonts
  - strong alignment
  - quiet internal-tool appearance
- avoid:
  - gradients
  - glassmorphism
  - decorative shadows
  - playful animations
  - marketing-style hero layouts

Phase 3: Client-side behavior
- update `static/js/app.js` to support role-aware camera interactions
- support:
  - start and stop per camera role
  - per-role latest-result polling
  - session table refresh
  - event table refresh
  - upload-result updates
- keep polling simple and explicit
- stop polling when it is not needed
- use class toggling rather than inline style manipulation when possible

Phase 4: Honest runtime states
- display real readiness states from the backend
- clearly show when:
  - detector is unavailable
  - OCR is unavailable
  - camera is stopped
  - session storage is unavailable
- never present fake active sessions or placeholder plates
- pair status colors with text labels

Phase 5: Data presentation
- make plate numbers highly legible
- make active sessions easy to scan quickly
- make recent event history understandable at a glance
- include useful columns like:
  - plate number
  - camera role
  - timestamp
  - status or action
  - confidence where appropriate
- unmatched exits should be visible but lower emphasis than active sessions

Phase 6: Responsiveness and accessibility
- preserve the simple responsive behavior in the design guide
- desktop is the main target, but smaller screens should collapse cleanly
- ensure:
  - labels are present
  - images have alt text
  - keyboard focus is visible
  - color is not the only status signal

Implementation constraints:
- do not switch to React, Vue, or another SPA framework
- do not add decorative motion
- do not mix backend business logic into frontend code
- do not use inline styles for major presentation logic
- do not add fake sample data into the operational views
- preserve the current upload and live-recognition flows while extending them

Frontend files to inspect and likely update:
- templates/index.html
- static/js/app.js
- static/css/style.css
- optionally src/api/routes.py if the template context must be expanded
- optionally src/api/schemas.py if UI-facing payload shape clarification is needed

Frontend verification requirements:
- verify the page loads correctly
- verify upload inference still works visually
- verify entry and exit camera controls behave correctly
- verify readiness states render honestly
- verify active sessions and event sections update from real API data
- verify no obvious layout breakage on desktop and narrow widths
- verify the UI still feels like an internal operations tool, not a marketing page

Frontend deliverables:
1. updated dashboard template
2. updated CSS aligned with the design guide
3. updated JavaScript for role-aware camera and data polling behavior
4. clear operator-facing sections for entry, exit, sessions, events, and unmatched exits
5. a short summary of:
   - what changed in the UI
   - which backend contracts the frontend expects
   - what should be tested next

Important mindset:
- optimize for fast operator comprehension
- keep the interface quiet, clear, and truthful
- preserve simplicity while making the dashboard operationally useful
```

## Suggested Use

Use this file when the task is mainly:

- dashboard structure
- Jinja2 template changes
- CSS cleanup or redesign
- JS polling and controls
- operator-facing UI behavior
