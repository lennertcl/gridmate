# Guides

## Overview

The Guides section provides user-facing documentation accessible directly from the application's navigation bar. Each guide explains the fields and concepts behind a specific configuration area, helping users set up GridMate correctly. The content was previously embedded as inline help text on individual settings pages and has been consolidated into dedicated guide pages for consistency.

Each configuration page links to its corresponding guide via a banner at the top.

## Relevant Artefacts

- [guides.py](../../web/routes/guides/guides.py) — Routes for all guide pages
- [getting-started.html](../../web/templates/guides/getting-started.html) — Getting Started guide
- [energy-feed.html](../../web/templates/guides/energy-feed.html) — Energy Feed guide
- [solar-panels.html](../../web/templates/guides/solar-panels.html) — Solar Panels guide
- [home-battery.html](../../web/templates/guides/home-battery.html) — Home Battery guide
- [devices.html](../../web/templates/guides/devices.html) — Devices guide
- [energy-contract.html](../../web/templates/guides/energy-contract.html) — Energy Contract guide
- [optimization.html](../../web/templates/guides/optimization.html) — Optimization guide
- [guides.css](../../web/static/css/guides.css) — Guide-specific styles (numbered steps)
- [optimization.css](../../web/static/css/settings/optimization.css) — Explanation card and section styles (reused)
- [layout.html](../../web/templates/layout.html) — Navbar with Guides dropdown

## Routes

All routes are registered under the `guides` blueprint.

| Route | Method | View | Description |
|---|---|---|---|
| `/guides` | GET | `getting_started` | Setup overview and ordered setup steps |
| `/guides/energy-feed` | GET | `energy_feed` | Energy feed sensor field explanations |
| `/guides/solar-panels` | GET | `solar_panels` | Solar panel sensor field explanations |
| `/guides/home-battery` | GET | `home_battery` | Home battery configuration field explanations |
| `/guides/devices` | GET | `devices` | Device type system, all device types and their parameters, deferrable load detail |
| `/guides/energy-contract` | GET | `energy_contract` | Contract component types and examples |
| `/guides/optimization` | GET | `optimization` | EMHASS optimization prerequisites and field explanations |

## Frontend

### Templates

All guide templates extend `layout.html` and follow the same structure:

1. Page header with title and link back to the configuration page
2. A single `card card-full-width explanation-card` containing `explanation-section` blocks
3. Each section uses `explanation-content` with `<dl>` definition lists for field-by-field explanations

The styling classes (`explanation-card`, `explanation-section`, `explanation-content`) are defined in `optimization.css` and shared across all guide pages.

### Navigation

The Guides dropdown is added to the navbar in `layout.html` between Dashboard and Settings. Active state detection uses `request.path` matching against `/guides/*` patterns.

### Guide Link Banners

Each configuration page includes a `.guide-link-banner` at the top linking to the relevant guide. This class is defined in `main.css` as a reusable component.
