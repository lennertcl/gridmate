# Frontend Guidelines

## Overview

Cross-cutting frontend guidelines that apply to all pages and features in the GridMate application.

## Responsiveness and Mobile UX

All pages must be designed with responsiveness and mobile UX as a first-class concern. The application runs as a Home Assistant addon and is frequently accessed from mobile devices (phones, tablets) via the HA companion app or mobile browsers.

### Key Principles

- **Mobile-first mindset**: Every new page or component must be tested and verified on small screens (≤ 768px) before merging
- **No horizontal scrolling**: Pages must never require horizontal scrolling on any screen width. Use `min(value, 100%)` in CSS `minmax()` grid declarations to prevent overflow
- **Touch-friendly interactions**: All interactive elements (buttons, navigation, dropdowns) must work with tap gestures — avoid relying on `:hover` for essential functionality
- **Readable content**: Tables, forms, and data-heavy sections must gracefully reflow to single-column layouts on narrow screens
- **Overflow handling**: Cards and containers should use `min-width: 0` and `overflow-x: auto` to prevent content from breaking layout boundaries

### Breakpoints

The application uses three responsive breakpoints defined in `main.css`:

| Breakpoint | Target | Key Behavior |
|---|---|---|
| `≤ 1024px` | Tablets / small desktops | Dashboard grids collapse to single column |
| `≤ 768px` | Mobile landscape / large phones | Navigation becomes hamburger menu with tap-to-expand submenus; forms go single column; tables reduce padding |
| `≤ 480px` | Mobile portrait | Buttons go full-width; font sizes reduce; form actions stack vertically |

### Navigation on Mobile

On screens ≤ 768px, the navigation switches to a hamburger menu. Submenu groups (Dashboard, Settings) use a click/tap-based toggle instead of the desktop `:hover` behavior. This is handled via the `.open` CSS class toggled by JavaScript in `main.js`.

### Common Patterns

- Use `grid-template-columns: repeat(auto-fit, minmax(min(350px, 100%), 1fr))` for dashboard grids
- Add `overflow-x: auto` to table containers for graceful degradation
- Use `word-break: break-word` or `break-all` on long values (entity IDs, sensor names)
- Stack flex layouts vertically with `flex-direction: column` at mobile breakpoints
- Page-specific responsive styles go in the page's dedicated CSS file (e.g., `costs.css`, `devices.css`)

## Relevant Artefacts

- [main.css](../web/static/css/main.css) — Global styles and responsive breakpoints
- [main.js](../web/static/js/main.js) — Navigation and responsive initialization
- [layout.html](../web/templates/layout.html) — Base layout template with responsive viewport meta tag
