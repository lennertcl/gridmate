# Energy Dashboard

## Overview

The energy dashboard provides a unified view of energy usage, production, consumption from grid, and injection to grid. It connects to Home Assistant via WebSocket for live entity updates and renders multiple time-series charts alongside current sensor values and aggregated energy statistics. The default time window is a full day (00:00 to 00:00 next day), and users can navigate day-by-day or enter custom date/time ranges. Charts and statistics update with real-time data when the current time falls within the selected range, indicated by a pulsing LIVE badge. When viewing a historical window, only the sensor value cards update — the charts and statistics remain static.

The page is organised into a unified flow of full-width card sections:

1. **Live sensor cards** — Four cards showing current power values for Usage, Production, Consumption, and Injection. Always display real-time values.
2. **Energy flow visualization** — A single full-width rectangle with two rows: row 1 shows three proportional segments (Grid Import, Self-consumed, Exported) and row 2 shows two overlapping total bars (Usage and Production). Below, centered stats show Self-sufficiency and Net Grid.
3. **Grid Interaction + Energy Usage charts** — Two side-by-side line charts. Data is fetched via `recorder/statistics_during_period` with 5-minute aggregation, giving ~288 data points per sensor per day. For live windows, data extends up to the current time. For historical windows, data covers the full selected range.
4. **Energy Price + Solar charts** — Two side-by-side charts (conditional). Price and solar charts display the full selected range including future predictions where available.

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

The route additionally passes:
- `has_variable_pricing` — boolean indicating whether any `VariableComponent` with a `price_provider_name` exists in the energy contract or any Energy Price Providers are defined. Used to conditionally render the price chart section.
- `solar_sensors` — a dict of all solar sensor entity IDs (production + estimation + consumption/injection) when solar is configured.
- `solar_configured` — boolean indicating whether solar panels are configured.

### GET `/api/energy-prices`

Returns price data from all defined Energy Price Providers. Fetches prices for a 48-hour window (today and tomorrow). Response format:
```json
{
  "providers": {
    "Provider Name": {"1234567890000": 0.05, ...}
  }
}
```
Keys are millisecond timestamps; values are prices in €/kWh.

For `NordpoolPriceProvider`, GridMate resolves future values through Home Assistant's `nordpool.get_prices_for_date` action instead of relying on sensor attributes. This returns the published quarter-hour or hour prices for the requested day. Tomorrow's values are only present after Nord Pool has published them through the integration.

### GET `/api/ha/config`

Returns the Home Assistant URL and access token as JSON for frontend WebSocket authentication. In local dev mode reads from environment variables; in addon mode reads from saved settings.

## Frontend

### Range Selector

Located in the page header, right-aligned next to the "Energy Dashboard" title. Styled as a cohesive pill-shaped control bar with:

- **Back button** (chevron left) — shifts both start and end back by one day
- **Start datetime picker** (labelled "From") — sets the beginning of the displayed window
- **End datetime picker** (labelled "To") — sets the end of the displayed window
- **Forward button** (chevron right) — shifts both start and end forward by one day
- **LIVE indicator** — A badge with a pulsing green dot that appears active when the current time falls within the selected range. When active, charts and statistics receive real-time data pushes.

Default range on page load is the current day (00:00 today to 00:00 tomorrow, realtime mode active). Changing either picker or clicking a shift button clears all charts and re-fetches history, statistics, price, and solar data for the new range.

### Live Data Cards

Four sensor cards in a single row show current values for Usage, Production, Consumption, and Injection. Each card uses the standard `sensor-item` styling from `main.css` with the category badge icon and name on the left, and a right-aligned live power reading (kW). Always updated in real time via WebSocket entity subscription regardless of the selected range.

### Energy Flow Visualization

A single full-width bordered rectangle divided into two rows:

**Row 1 (Segments)** — Three proportional flex segments showing the energy breakdown:
- **Grid Import** (orange background) — energy drawn from the grid
- **Self-consumed** (green background) — solar energy consumed directly
- **Exported** (yellow background) — surplus solar energy sent to the grid

Each segment displays its kWh value and label. Segment widths are proportional to their kWh values via CSS `flex`.

**Row 2 (Totals)** — Two overlapping bars showing aggregate totals:
- **Usage** (blue, left-aligned) — spans the width of Import + Self-consumed. Shows total usage with a bolt icon.
- **Production** (yellow, right-aligned) — spans the width of Self-consumed + Exported. Shows total production with a solar panel icon.

The bars overlap in the Self-consumed zone, visually showing how usage and production share the self-consumed energy. When there is no production, the production bar hides.

Below the rectangle, centered stats show:
- **Self-sufficiency** — percentage of total usage covered by direct solar (`direct_solar / total_used × 100`)
- **Net Grid** — net balance between injection and consumption, prefixed with `+` or `-`

Energy values are computed from the same `recorder/statistics_during_period` data used for the charts (5-minute aggregation). Before deriving usage and self-consumed solar, the frontend aligns the 5-minute buckets across consumption, production, injection, and usage so missing buckets are treated consistently. Live sensor updates are appended after the last statistics bucket and the flow summary is recalculated immediately, but only when in realtime mode.

### Charts Row (Grid Interaction + Energy Usage)

The Grid Interaction and Energy Usage charts are displayed side by side in a single card. On screens narrower than 768px, they stack vertically. Each chart has a visible title heading.

**Grid Interaction chart** — Line chart showing Consumption (positive, orange) and Injection (negative, green) with a time x-axis. Values close to zero are nullified to create natural gaps when a series is inactive.

**Energy Usage chart** — Mixed chart showing total Usage (blue line) and Production (yellow line). Same time x-axis and real-time update behavior.

Both charts use data from `recorder/statistics_during_period` with 5-minute aggregation (~288 points per day), which is much more efficient than fetching raw history. Chart.js auto-detects the appropriate time unit for the x-axis based on the data range. For live windows, data extends to the current time. For historical windows, data covers the full range.

### Charts Row (Energy Prices + Solar)

A second side-by-side chart row displays below the main charts. These charts use the full selected range (including future time) to display predictions:

**Energy Prices chart** — A stepped line chart showing price data from all defined Energy Price Providers. Price data is fetched once from the `/api/energy-prices` backend endpoint on page load. The frontend creates one dataset per provider from the API response, so all configured providers are rendered even when none were known when the chart instance was created. Nord Pool providers use Home Assistant's day-price action for the published remaining slots of today and, when available, tomorrow. Each provider gets its own dataset with a distinct color from `PRICE_COLORS`. Only rendered if at least one Energy Price Provider is defined or a variable component has a `price_provider_name` configured.

**Solar Production vs Forecast chart** — Identical to the chart on the Solar Dashboard. Shows actual production (yellow bars) and forecast (dashed blue line). Actual production history is fetched from HA, while the forecast combines the current-day estimation entity with the +24h offset entity for future hours. Updated in real time via entity subscription. Only rendered if solar panels are configured.

If only one of these charts is configured, it spans the full width via CSS `:only-child`.

### JavaScript Architecture

All JS is split into separate files following the project rules:

- **live-charts.js** — Loaded as a regular script. Provides `create_energy_chart()`, `create_consumption_chart()`, `create_price_chart(price_sensors, start_time, end_time)`, `clear_chart()`, `process_history_for_chart()`, `process_activity_history_for_chart()`, and `update_chart_realtime()`. Reusable chart configuration and dataset builders.
- **solar-charts.js** — Conditionally loaded when solar is configured. Provides `create_solar_production_chart()`, `update_solar_production_chart_realtime()`, `update_solar_chart_range()`, and `clear_solar_charts()`. Reused from the solar dashboard.
- **live-dashboard.js** — Loaded as an ES module. Handles the HA WebSocket connection lifecycle, range control initialization, statistics fetching, realtime detection (`is_realtime_window()`), LIVE indicator toggling, energy flow updates, and real-time entity subscription updates. Only pushes data to charts and statistics when in realtime mode (current time within selected range); always updates the sensor value cards. Depends on functions from `live-charts.js` and optionally `solar-charts.js`. Uses a single `recorder/statistics_during_period` call with 5-minute aggregation for both chart data and energy summary. When `usage_mode` is `'auto'`, it first aligns the timestamp buckets returned for consumption, production, and injection, then computes usage as `max(0, consumption + production − injection)` on that aligned timeline. It also resizes the price chart datasets to exactly match the providers returned by `/api/energy-prices`. All charts and the energy flow use the same selected time range.

The only inline script in the template injects backend sensor entity IDs into `window.HA_CONFIG`.

### WebSocket Connection

The frontend uses `home-assistant-js-websocket` loaded as an ES module. It:

1. Fetches HA connection config from `/api/ha/config`
2. Creates a long-lived token auth connection
3. Fetches aggregated statistics for the selected range via `recorder/statistics_during_period` (5-minute period) for charts and energy summary
4. Fetches raw history via `history/history_during_period` for price and solar charts only
5. Subscribes to live entity updates via `subscribeEntities`

