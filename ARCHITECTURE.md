# Yearly Yields — Architecture v1.4

> **Intended audience:** Claude Code, sprint planning sessions, project handoff.
> **Status:** Pre-sprint architectural design. Approved scope, pending sprint start.
> **Parent system:** Yearly Yields (.NET Core / Angular / PostgreSQL / pgvector)
> **Sprint model:** Hardening sprint. Scope is driven entirely by findings in `docs/accessibility-audit-v1.3.md`.
> **Sprint goal:** Accessibility remediation, color role enforcement, and sprint close-out audit doc.
> **Prerequisite:** v1.3 merged to `main`. `docs/accessibility-audit-v1.3.md` present and reviewed before sprint begins.

---

## Table of Contents

1. [Sprint Goal & Definition of Done](#1-sprint-goal--definition-of-done)
2. [v1.4 Scope — In Sprint](#2-v14-scope--in-sprint)
3. [Feature: Harvest Gold Foreground Policy](#3-feature-harvest-gold-foreground-policy)
4. [Feature: aria-label on Icon-Only Buttons](#4-feature-aria-label-on-icon-only-buttons)
5. [Feature: Logo Image → Semantic Button](#5-feature-logo-image--semantic-button)
6. [Feature: Skip-Navigation Link](#6-feature-skip-navigation-link)
7. [Feature: Mobile Nav aria-label](#7-feature-mobile-nav-aria-label)
8. [Deliverable: Full Re-Audit with axe DevTools](#8-deliverable-full-re-audit-with-axe-devtools)
9. [v1.3 Carry-Forward Verification](#9-v13-carry-forward-verification)
10. [Human-in-the-Loop Checkpoints](#10-human-in-the-loop-checkpoints)
11. [Out of Scope — v1.4](#11-out-of-scope--v14)

---

## 1. Sprint Goal & Definition of Done

v1.4 is an **accessibility remediation sprint** driven by concrete findings from the v1.3 audit. Every item in scope has a known location and a known failure mode — this is not an exploratory audit sprint. The work is fix, verify, repeat, then close with a formal re-audit document.

Priority order follows `docs/accessibility-audit-v1.3.md`. Read that document before beginning any remediation work.

A v1.4 release to `main` is considered **complete** when:

- [ ] Harvest gold is enforced as a background-only color across all themes; foreground gold transitions to a darkened accessible variant
- [ ] All icon-only table action buttons and the toolbar logout button have `aria-label`
- [ ] Theme-picker trigger is a semantic `<button>` with `aria-label`; no clickable `<img>` elements remain
- [ ] Skip-nav link is present, first in DOM, and becomes visible on keyboard focus
- [ ] Mobile nav `<a>` elements have fallback accessible names when text labels are hidden
- [ ] `docs/accessibility-audit-v1.4.md` is produced per the spec in Section 8
- [ ] No regressions introduced to v1.3 functionality

---

## 2. v1.4 Scope — In Sprint

| # | Feature | Weight | Audit source |
|---|---------|--------|--------------|
| 1 | Harvest gold foreground policy | Medium | Contrast failures: 1.98:1, 2.07:1, 2.42:1 on all surfaces |
| 2 | `aria-label` on icon-only buttons | Light | Table action buttons + toolbar logout |
| 3 | Logo image → semantic button | Light | Clickable `<img>` is not keyboard-focusable |
| 4 | Skip-navigation link | Light | Missing from shell |
| 5 | Mobile nav `aria-label` | Light | Text labels hidden in mobile without fallback |
| 6 | Full re-audit with axe DevTools | Medium | Sprint close-out deliverable; produces audit doc |

> Items 2–5 are independent and can be completed in any order. Item 1 (gold policy) touches the design token layer and should be completed and verified across all three themes before the re-audit in item 6 runs.

---

## 3. Feature: Harvest Gold Foreground Policy

### Problem
`#C9A227` (harvest gold) fails WCAG AA as a text or icon color on every surface in the current design system:

| Surface | Contrast ratio | Result |
|---------|---------------|--------|
| Field green (sidebar) | 1.98:1 | ❌ Fail |
| Parchment | 2.07:1 | ❌ Fail |
| White | 2.42:1 | ❌ Fail |

`#C9A227` **passes** as a *background* with black or dark text (8.33:1). The color is visually important to the Yearly Yields brand and is not being removed — its role is being corrected.

### Decision
Harvest gold is enforced as a **background-only** color going forward. Where gold was used as a foreground (nav icons, nav text on the field green sidebar), the foreground color transitions to `--yy-white-board`. A darkened accessible gold variant will be established for any cases where a gold foreground is genuinely required by the design.

### Darkened gold target
The exact accessible gold value depends on the surface it appears on. The target is WCAG AA (4.5:1 minimum for normal text). As a reference starting point, values in the `#7A5C10`–`#8B6B14` range typically achieve this on light surfaces — but Claude Code must calculate the precise value against the actual surface colors in the codebase rather than using these as hardcoded targets.

### Human checkpoint
> Before finalizing the darkened gold value, surface the calculated contrast ratio and hex value to Jacob for approval. Gold is a brand color — the exact shade is a product call, not a code call.

### Implementation approach

1. Read `docs/accessibility-audit-v1.3.md` for the exact surfaces and component locations flagged.
2. Identify all CSS variable usages of `--yy-harvest-gold` (or equivalent) where it is applied as `color`, `fill`, or `stroke` (foreground roles).
3. On the field green sidebar: switch nav icon and text color to `--yy-white-board`.
4. For any remaining foreground gold usages: calculate the minimum darkened value that passes 4.5:1 on its surface, surface to Jacob for approval, then apply as a new token (e.g., `--yy-harvest-gold-accessible`).
5. Verify `--yy-harvest-gold` in background roles (e.g., badges, highlights, buttons) is unaffected — background usage is correct and should not change.
6. Cross-check all three themes after changes — shared tokens propagate across themes.

### Definition of done for this feature
- [ ] No instance of `--yy-harvest-gold` (or `#C9A227`) used as a foreground color in any theme
- [ ] Field green sidebar nav icons and text use `--yy-white-board`
- [ ] Darkened accessible gold token established and approved by Jacob
- [ ] All three themes pass contrast check on gold-related elements
- [ ] Background gold usages (badges, highlights) are visually unchanged

---

## 4. Feature: aria-label on Icon-Only Buttons

### Problem
All table action buttons (edit, delete, view, and similar) and the toolbar logout button render icon-only with no accessible name. `matTooltip` provides a visual hover label but is not read by screen readers — it is not a substitute for `aria-label`.

### Implementation
Add `aria-label` to every icon-only `<button>` element. Labels must be action-descriptive and include enough context to be useful without visual context:

- Prefer: `aria-label="Edit crop cycle"` over `aria-label="Edit"`
- Prefer: `aria-label="Delete growing area"` over `aria-label="Delete"`
- Toolbar logout: `aria-label="Log out"`

Do not remove `matTooltip` — it serves sighted mouse users. `aria-label` is additive.

### Definition of done for this feature
- [ ] All table action buttons have `aria-label` with contextual descriptions
- [ ] Toolbar logout button has `aria-label="Log out"`
- [ ] No icon-only interactive element remains without an accessible name
- [ ] `grep` for `mat-icon-button` (or equivalent) returns no results without an accompanying `aria-label`

---

## 5. Feature: Logo Image → Semantic Button

### Problem
The theme-picker trigger is currently a clickable `<img>` element. Image elements are not keyboard-focusable by default and are not announced as interactive by screen readers. This makes the theme picker entirely inaccessible to keyboard and screen reader users.

### Implementation
Wrap the `<img>` in a `<button>` element:

```html
<!-- Before -->
<img src="logo.svg" (click)="openThemePicker()" />

<!-- After -->
<button (click)="openThemePicker()" aria-label="Change theme" class="theme-picker-trigger">
  <img src="logo.svg" alt="" aria-hidden="true" />
</button>
```

Note: `alt=""` on the image and `aria-hidden="true"` prevents the screen reader from announcing the image twice — the button's `aria-label` carries the accessible name.

Apply styling to the `<button>` to match the current visual appearance (remove default button chrome: `background: none; border: none; padding: 0; cursor: pointer;`).

### Definition of done for this feature
- [ ] No clickable `<img>` elements remain in the shell or nav
- [ ] Theme-picker trigger is a `<button>` with `aria-label="Change theme"`
- [ ] Button is keyboard-focusable and activates the theme picker on Enter/Space
- [ ] Visual appearance is unchanged from v1.3

---

## 6. Feature: Skip-Navigation Link

### Problem
There is no skip-nav link in the shell. Keyboard users must tab through the entire sidenav on every page before reaching main content. This is a WCAG 2.4.1 (Bypass Blocks) failure.

### Implementation
Add a skip-nav link as the first element inside `<body>` (or the root Angular component):

```html
<a href="#main-content" class="skip-nav">Skip to main content</a>
```

The target element (main content area) must have `id="main-content"` and `tabindex="-1"` so it receives focus when the link is activated.

CSS — visually hidden by default, visible on focus:

```css
.skip-nav {
  position: absolute;
  top: -100%;
  left: 0;
  background: var(--yy-field-green);
  color: var(--yy-white-board);
  padding: 8px 16px;
  z-index: 9999;
  text-decoration: none;
}

.skip-nav:focus {
  top: 0;
}
```

Adjust colors to match the active theme's high-contrast pairing. Verify the skip-nav itself passes contrast in all three themes.

### Definition of done for this feature
- [ ] Skip-nav link is the first focusable element in the DOM
- [ ] Link is visually hidden until focused
- [ ] Activating the link moves focus to `#main-content`
- [ ] Skip-nav passes contrast in all three themes
- [ ] Verified with keyboard-only navigation (Tab → skip-nav appears → Enter → focus lands in content)

---

## 7. Feature: Mobile Nav aria-label

### Problem
In mobile mode, nav item text labels are hidden (icon-only display). The `<a>` elements have no fallback accessible name, making the mobile nav completely opaque to screen readers.

### Implementation
Add `aria-label` to each nav `<a>` element with the same label text that is shown in desktop mode:

```html
<a routerLink="/crop-cycles" aria-label="Crop Cycles">
  <mat-icon>grass</mat-icon>
  <span class="nav-label">Crop Cycles</span>
</a>
```

This approach works for both desktop (label visible, aria-label redundant but harmless) and mobile (label hidden, aria-label provides accessible name). Do not use `aria-hidden` on the `<span>` — let the label be read in desktop mode and rely on `aria-label` as the canonical name in both modes.

### Definition of done for this feature
- [ ] All nav `<a>` elements have `aria-label` matching their visible text label
- [ ] Verified in mobile viewport: screen reader announces nav item names correctly
- [ ] No nav item is announced as unlabeled or as its icon name

---

## 8. Deliverable: Full Re-Audit with axe DevTools

### Purpose
After all remediations above are complete, run a full browser accessibility audit using axe DevTools to catch issues not detectable from static CSS inspection. This includes focus order, form label associations, dialog ARIA roles, and Material 3 tonal role contrast that only manifests at runtime.

This audit produces `docs/accessibility-audit-v1.4.md` as a formal sprint close-out artifact.

### When to run
After all items in Sections 3–7 are complete and verified. Do not run the re-audit mid-sprint — partial fixes will produce misleading results.

### Audit scope
Run axe DevTools against:
- Dashboard / growing area overview
- Crop cycle detail view
- Sensor readings view
- Alert stream view
- Invoice list and detail
- Mobile viewport (375px width minimum)
- All three themes (run separately for each)

### Expected output — `docs/accessibility-audit-v1.4.md`

The document must contain the following sections:

```
# Yearly Yields — Accessibility Audit v1.4

## Audit date
## Auditor
## Tool
## Themes audited
## Pages / views audited

## Summary
Short paragraph: what was fixed in v1.4, overall accessibility posture post-remediation.

## Findings resolved from v1.3 audit
Table: Finding | Location | Resolution | Status (Resolved / Verified)

## New findings (if any)
Table: Finding | Severity | Location | Recommended fix | Target version

## Remaining known issues
Any issues identified but explicitly deferred, with rationale and target version.

## WCAG AA compliance status by theme
Table: Theme | Status (Pass / Pass with exceptions) | Notes
```

If the re-audit surfaces new critical failures (Level A violations), surface them to Jacob before closing the sprint — do not defer Level A issues to backlog without explicit approval.

### Definition of done for this deliverable
- [ ] axe DevTools audit run on all views in all three themes
- [ ] `docs/accessibility-audit-v1.4.md` produced per the spec above
- [ ] All v1.3 audit findings appear in the "Findings resolved" table
- [ ] Any new findings are documented with severity and recommended fix
- [ ] Document committed to `main` alongside the remediation code

---

## 9. v1.3 Carry-Forward Verification

The following item was scoped for v1.3 but may or may not have landed depending on sprint capacity. Claude Code must verify before assuming either way.

| Item | How to verify | If landed | If not landed |
|------|--------------|-----------|---------------|
| `harvest_ready` removal from `AlertType` enum | `grep -r "harvest_ready"` in codebase; check migration history | No action needed | Add to v1.4 scope; write migration per original spec before beginning accessibility work |

Do not proceed past this check without confirming the status. Surface the result to Jacob if not landed.

---

## 10. Human-in-the-Loop Checkpoints

Claude Code must pause and surface a question to Jacob before proceeding at these points:

| # | Checkpoint | Question |
|---|-----------|----------|
| 1 | Darkened gold hex value | Surface calculated value and contrast ratio for approval before applying. Gold is a brand color — exact shade is a product call. |
| 2 | Shared token changes | If a CSS variable change affects more than one theme simultaneously, surface before committing. |
| 3 | `harvest_ready` status | Surface verification result (landed or not) before beginning sprint work. |
| 4 | New Level A findings in re-audit | If axe DevTools surfaces any WCAG Level A violations not in the v1.3 audit, surface to Jacob before closing sprint. Do not defer without explicit approval. |

---

## 11. Out of Scope — v1.4

- Customer-scoped crop rates
- Crop rate seeding
- Indiscriminate crop invoicing (pick-triggered draft invoices)
- User-to-growing-area assignment model
- Configurable crop phase day admin UI
- IoT reading source
- SMS alert notifications
- Sortable table columns
- Any features listed as "Possible Future Features" in the README
- Switchyard or any other project
