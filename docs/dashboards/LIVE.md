# Live Energy Dashboard

## Overview

The live energy dashboard provides real-time monitoring of energy usage, production, consumption from grid, and injection to grid. It connects to Home Assistant via WebSocket for live entity updates and renders two time-series charts alongside current sensor values. Users can select a custom date/time range using start and end pickers, and shift the window forward or backward by 2 hours. Charts only update with real-time data when the selected end time is near "now" (within 3 minutes), indicated by a pulsing LIVE badge. When viewing a historical window, only the sensor value cards update — the charts remain static.

Each live data card now also shows a cumulative kWh total for the currently selected range, derived in the frontend from the same history points used to draw the charts. The page also ends with a compact “Today’s Use” section that highlights total usage, the imported versus self-consumed split, injected energy, and net grid balance from midnight until now.

## Relevant Artefacts

- [live.html](../../web/templates/dashboard/live.html) — Dashboard template
- [dashboard.py](../../web/routes/dashboards/dashboard.py) — Dashboard routes
- [live.css](../../web/static/css/dashboard/live.css) — Page-specific styles
- [live-charts.js](../../web/static/js/live-charts.js) — Chart creation and update helpers
- [live-dashboard.js](../../web/static/js/live-dashboard.js) — Main orchestration, HA WebSocket connection, range controls

## Models

No dedicated backend models. The dashboard reads sensor configuration from `EnergyFeed` (energy feed settings) to determine which HA entity IDs to subscribe to.

## Services

No backend services. All data comes directly from Home Assistant via the WebSocket API in the browser.

## Forms

No forms.

## Routes

### GET `/dashboard/live`

Renders the live dashboard. Passes sensor entity IDs from the configured `EnergyFeed` to the template as `actual_consumption_sensor`, `actual_injection_sensor`, `actual_usage_sensor`, and `actual_production_sensor`. Also passes `usage_mode` (`'auto'` or `'manual'`) which controls how usage is calculated in the frontend.

When `usage_mode` is `'auto'`, the frontend computes usage as `max(0, consumption + production − injection)` instead of reading from a dedicated usage sensor. When `'manual'`, the usage sensor entity value is used directly.

### GET `/api/ha/config`

Returns the Home Assistant URL and access token as JSON for frontend WebSocket authentication. In local dev mode reads from environment variables; in addon mode reads from saved settings.

## Frontend

### Range Selector

Located in the page header, right-aligned next to the title. Styled as a cohesive pill-shaped control bar with:

- **Back button** (chevron left) — shifts both start and end back by 2 hours
- **Start datetime picker** (labelled "From") — sets the beginning of the displayed window
- **End datetime picker** (labelled "To") — sets the end of the displayed window
- **Forward button** (chevron right) — shifts both start and end forward by 2 hours, clamped so the end never exceeds the current time
- **LIVE indicator** — A badge with a pulsing green dot that appears active when the end time is within 3 minutes of now. When active, charts receive real-time data pushes and the end time auto-advances.

Default range on page load is the last 2 hours (realtime mode active). Changing either picker or clicking a shift button clears the charts and re-fetches history for the new range.

### Live Data Cards

Four sensor cards in a single row show current values for Usage, Production, Consumption, and Injection. Each card uses the standard `sensor-item` styling from `main.css` with the category badge icon and name on the left, and a right-aligned stack of the live power reading (kW) and cumulative kWh total for the selected range. Updated in real time via WebSocket entity subscription.

The kWh totals reflect the currently selected range and are computed from the chart history points so the summary stays aligned with what the user sees.

### Grid Interaction Chart

Line chart showing Consumption (positive, orange) and Injection (negative, green) with a time x-axis.

The chart intentionally inserts `null` points whenever a series is inactive or the opposite series becomes active. This ensures Chart.js breaks the line instead of connecting two non-adjacent consumption or injection points across a period where the home was interacting with the grid in the opposite direction. The datasets also enable point rendering only for real data points, not for null gaps.

### Energy Usage Chart

Line chart showing total Usage (blue) and Production (yellow). Same time x-axis and real-time update behavior.

### Today’s Use Section

A two-panel layout summarizes today from midnight to now:

**Left panel — Total usage card** (usage-colored border, large hero value):
- Hero value showing total energy consumed by the home
- Two breakdown rows below a divider: Imported (orange dot) and Self consumed (green dot)

**Right panel — Three detail tiles** stacked vertically, each styled like a `sensor-item` with badge icon, label, and right-aligned value:
- **Injected** (injection color) — surplus energy exported to the grid
- **Self-sufficiency** (production color) — percentage of total usage covered by direct solar (`direct_solar / total_used × 100`)
- **Net grid** (consumption color) — net balance between injection and consumption, prefixed with `+` or `-`

Energy values are fetched via HA’s `recorder/statistics_during_period` WebSocket API with 5-minute aggregation, which gives properly averaged power per bucket. Each bucket’s mean power is multiplied by its duration to compute energy (trapezoidal integration). This avoids the sparse-data problem where sensors with few raw state changes (e.g. solar production at night) would produce wildly inaccurate results if integrated from raw history. Live sensor updates are appended after the last statistics bucket to keep the totals current between fetches.

These values are refreshed from history on page load and range changes, and then kept current with the same live entity subscription used for the cards and charts.

### JavaScript Architecture

All JS is split into separate files following the project rules:

- **live-charts.js** — Loaded as a regular script. Provides `create_energy_chart()`, `create_consumption_chart()`, `clear_chart()`, `process_history_for_chart()`, `process_activity_history_for_chart()`, and `update_chart_realtime()`. Reusable chart configuration and dataset builders.
- **live-dashboard.js** — Loaded as an ES module. Handles the HA WebSocket connection lifecycle, range control initialization, history fetching, realtime detection (`is_realtime_window()`), LIVE indicator toggling, and real-time entity subscription updates. Only pushes data to charts when the window is in realtime mode; always updates the sensor value cards. Depends on functions from `live-charts.js`. When `usage_mode` is `'auto'`, computes usage history from consumption, production, and injection history data points using `compute_usage_from_history()`, matching the same formula used for live updates (`max(0, consumption + production − injection)`). It also derives selected-range kWh counters and today-level detail metrics directly from the fetched Chart.js data.

The only inline script in the template injects backend sensor entity IDs into `window.HA_CONFIG`.

### WebSocket Connection

The frontend uses `home-assistant-js-websocket` loaded as an ES module. It:

1. Fetches HA connection config from `/api/ha/config`
2. Creates a long-lived token auth connection
3. Fetches historical data for the selected range via `history/history_during_period`
4. Subscribes to live entity updates via `subscribeEntities`
