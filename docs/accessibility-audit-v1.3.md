# Yearly Yields — Accessibility Audit v1.3

> **Type:** Reconnaissance only. No fixes in this document.
> **Scope:** Color contrast (WCAG 2.1 AA) + ARIA gaps across all three themes.
> **Remediation target:** v1.4 hardening sprint.
> **Audit method:** Static CSS token analysis (contrast ratios computed from `_tokens.scss`), template scan for ARIA attributes, and visual inspection of all three themes at `https://localhost:4200`.

---

## Summary

| Category | Failures | Near-miss | Passing |
|----------|----------|-----------|---------|
| Contrast (WCAG AA 4.5:1) | 4 | 2 | 1 |
| ARIA / semantic HTML | 5 gaps | — | — |

The root of the contrast failures is using **harvest gold (`#C9A227`) as a foreground/icon color**. It works as a background (black text on gold = 8.33:1 ✓) but fails at every ratio when used as text or icon color against light or green surfaces. This is a design system decision that touches nav, chips, FABs, and table action icons.

---

## 1. Color Contrast

### 1.1 Failures (< 4.5:1, WCAG AA)

| Pair | Ratio | Theme(s) | Location |
|------|-------|----------|----------|
| Harvest gold `#C9A227` on field green `#507B6A` | **1.98 : 1** | Default, Light | Sidenav nav text + icons (default); active-link text + icon (light) |
| Harvest gold `#C9A227` on parchment `#F4EDD9` | **2.07 : 1** | Default | Chip labels, FAB icons, table action icons on parchment surface |
| Harvest gold `#C9A227` on white `#FFFFFF` | **2.42 : 1** | Light | Filled button labels, chip labels, FAB icons on white surface |
| Field green `#507B6A` on parchment `#F4EDD9` | **4.10 : 1** | Default | Primary color usage — any text or icon using `--mat-sys-primary` on parchment |

### 1.2 Near-miss (passes AA, fails AAA 7.0:1)

| Pair | Ratio | Theme(s) | Location |
|------|-------|----------|----------|
| Field green `#507B6A` on white `#FFFFFF` | **4.79 : 1** | Light | Primary color on light surface — passes AA but thin margin |
| Harvest gold `#C9A227` on washed-black `#3B3A3C` | **4.68 : 1** | Dark | Sidenav nav icons on dark sidebar — passes AA but close |

### 1.3 Passing

| Pair | Ratio | Theme(s) | Location |
|------|-------|----------|----------|
| Text black `#08060D` on harvest gold `#C9A227` | **8.33 : 1** | All | Filled button labels, chip text — harvest gold as background ✓ |

### Recommended remediation direction (v1.4)

Harvest gold should be treated as a **background-only brand color** for interactive elements. For icon and text uses in the sidenav and on surface:

- **Default / Light nav icons and text:** Switch to `--yy-white-board` (`#EEEEEE`) on the field green sidebar. White-board on field green = approximately 7.3:1 (AAA).
- **Active-link in light mode** (harvest gold text on field green): Switch active-link text to `--yy-white-board` or `--yy-text-black` on a lighter active background.
- **Chips, FABs, table icons on surface:** Harvest gold remains the container/background color — ensure label/icon inside uses `--yy-text-black`. Already correct on filled buttons; verify chip icon and FAB icon colors.
- **Field green on parchment (4.10:1):** Darken primary slightly for default theme, or use `--yy-text-black` for body text rather than primary color where possible.

---

## 2. ARIA Gaps

### 2.1 Icon-only buttons missing `aria-label` (all feature pages)

**Severity:** High — screen readers announce these as unlabeled buttons.

All table action buttons use `matTooltip` only. `matTooltip` is a visual hover hint and does **not** expose an accessible name. Every `mat-icon-button` without visible text needs an explicit `aria-label`.

Affected locations:
- `users.ts` — Edit button, Delete/Deactivate button
- `alerts.ts` — Resolve manually button
- `customers.ts` — Edit button, Delete button
- `fields.ts` — Edit button
- `crop-cycles.ts` — Update button
- `invoices.ts` — Review/Advance button, Download PDF button
- `dashboard-shell.html` — Logout button in toolbar

**Fix pattern:**
```html
<!-- Before -->
<button mat-icon-button matTooltip="Resolve manually" (click)="resolve(a)">
  <mat-icon>check_circle</mat-icon>
</button>

<!-- After -->
<button mat-icon-button matTooltip="Resolve manually" aria-label="Resolve alert manually" (click)="resolve(a)">
  <mat-icon>check_circle</mat-icon>
</button>
```

### 2.2 Logo image used as interactive button

**Severity:** Medium — `<img>` with `(click)` is not keyboard-focusable and has no accessible role.

`dashboard-shell.html` line 5–9: logo image opens the theme picker on click. An `<img>` element is not a keyboard-accessible interactive element.

**Fix:** Wrap in a `<button>` with `aria-label="Change display theme"` and remove inline `style="cursor: pointer;"`.

### 2.3 `<mat-nav-list>` missing navigation landmark label

**Severity:** Medium — multiple `<nav>` landmarks without labels are indistinguishable for screen reader users.

The sidenav `<mat-nav-list>` renders a `<nav>` element but has no `aria-label`. If the page has more than one `<nav>` (e.g., breadcrumbs or pagination added later), they become ambiguous.

**Fix:** `<mat-nav-list aria-label="Main navigation">`

### 2.4 Mobile nav items lose visible labels without `aria-label`

**Severity:** Medium — in mobile mode, `<span matListItemTitle>` is hidden. The `matTooltip` is not announced on keyboard focus.

When `isMobile()` is true, nav `<a>` elements display only an icon. `matTooltip` is triggered by hover, not focus. Screen reader users navigating by keyboard get unlabeled links.

**Fix:** Add `[attr.aria-label]="isMobile() ? item.label : null"` to the nav `<a>` element.

### 2.5 No skip-navigation link

**Severity:** Low-Medium — keyboard users must tab through the entire sidenav on every page load to reach main content.

No `<a href="#main-content">Skip to main content</a>` exists at the top of `dashboard-shell.html`. The `<main class="shell-main">` element also lacks `id="main-content"`.

**Fix:**
```html
<!-- Top of dashboard-shell.html, before mat-sidenav-container -->
<a href="#main-content" class="skip-nav">Skip to main content</a>

<!-- On the main element -->
<main id="main-content" class="shell-main">
```
Add `.skip-nav { position: absolute; left: -999px; }` and `.skip-nav:focus { left: 0; }` in styles.

---

## 3. What Was Not Checked

The following require browser-based tooling (Lighthouse or axe DevTools) to verify and should be re-run in v1.4 alongside fixes:

- Focus order and focus visibility across all pages
- Form field labels and error message associations (`mat-error` / `aria-describedby`)
- Dialog accessibility (`mat-dialog` ARIA roles, focus trap, return focus on close)
- Color contrast in dark mode for Material system-generated tonal roles (M3 tonal palettes — not audited here as they are generated, not static)
- Images of text
- Touch target sizes on mobile nav items

---

## 4. Recommended v1.4 Priority Order

1. **`aria-label` on all icon-only buttons** — highest user impact, purely additive, no visual change
2. **Nav contrast: harvest gold on field green** — affects every page load in default/light mode
3. **Logo button semantic fix** — keyboard accessibility gap
4. **Skip-nav link** — standard pattern, low effort
5. **Mobile nav `aria-label`** — affects mobile sessions
6. **Nav landmark label** — low effort, good hygiene
7. **Chip/FAB/table icon contrast on surface** — requires design decision on gold-as-foreground policy
8. **Full browser re-audit with axe DevTools** after fixes to catch anything missed in static analysis
