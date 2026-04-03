# Solar Dashboard

## Overview

The solar dashboard provides real-time monitoring of solar panel production along with forecast estimates. It connects to Home Assistant via WebSocket for live entity updates, rendering a hero card with current production and a 6-stat overview grid, and a production-vs-forecast chart with a configurable time window. When no solar sensors are configured, the page shows an empty state with a CTA linking to the solar settings page.

## Relevant Artefacts

- [solar.html](../../web/templates/dashboard/solar.html) — Dashboard template
- [dashboard.py](../../web/routes/dashboards/dashboard.py) — Dashboard routes (solar function)
- [solar.css](../../web/static/css/dashboard/solar.css) — Page-specific styles
- [solar-charts.js](../../web/static/js/solar-charts.js) — Chart creation and update helpers
- [solar-dashboard.js](../../web/static/js/solar-dashboard.js) — Main orchestration, HA WebSocket connection, sensor subscriptions
- [models.py](../../web/model/solar/models.py) — Domain models (Solar, SolarSensors, SolarEstimationSensors)
- [data_connector.py](../../web/model/data/data_connector.py) — SolarManager for persistence
- [solar.py](../../web/forms/solar.py) — SolarConfigForm (used by the settings route)

## Models

### Solar

Solar sensor configuration model stored in `settings.json` under the `solar` key.

| Field | Type | Default | Description |
|---|---|---|---|
| `sensors` | SolarSensors | (empty) | Live sensor entity IDs |
| `estimation_sensors` | SolarEstimationSensors | (empty) | Forecast Solar estimation entity IDs |
| `last_updated` | datetime | now | Last configuration change timestamp |

Key properties:
- `is_configured` — Returns `True` when at least one sensor in `sensors` is set (via `sensors.has_any`)

Backward compatibility: `from_dict` migrates the old flat `production_entity` field into `sensors.actual_production`.

### SolarSensors

Live production sensor entity IDs from Home Assistant.

| Field | Sensor Type | Description |
|---|---|---|
| `actual_production` | Power (kW) | Current instantaneous production |
| `energy_production_today` | Energy (kWh) | Cumulative production today |
| `energy_production_lifetime` | Energy (kWh) | Total lifetime production |

### SolarEstimationSensors

Forecast Solar integration entity IDs. These come from the Home Assistant [Forecast.Solar](https://www.home-assistant.io/integrations/forecast_solar/) integration.

| Field | Sensor Type | Description |
|---|---|---|
| `estimated_actual_production` | Power (kW) | Forecasted current production |
| `estimated_energy_production_remaining_today` | Energy (kWh) | Remaining forecast for today |
| `estimated_energy_production_today` | Energy (kWh) | Total forecasted production today |
| `estimated_energy_production_hour` | Energy (kWh) | Forecasted production this hour |
| `estimated_actual_production_offset_day` | Power (kW) | Forecasted production at same time +24h |
| `estimated_energy_production_offset_day` | Energy (kWh) | Total forecasted production +24h |
| `estimated_energy_production_offset_hour` | Energy (kWh) | Forecasted production next hour |

## Services

### SolarManager

Part of `DataConnector`. Provides persistence operations for the `Solar` model via `JsonRepository`.

Key methods:
- `get_config()` — Returns the current `Solar` configuration
- `set_sensors(sensors_dict)` — Updates solar sensor entity IDs
- `set_estimation_sensors(estimation_dict)` — Updates estimation sensor entity IDs
- `get_all_sensor_ids()` — Returns a list of all non-empty sensor IDs (sensors + estimation sensors)

## Forms

### SolarConfigForm

WTForms form for the solar settings page. All fields use `Optional()` validators since users may not have every sensor available.

Sections:
1. **Solar Panel Sensors** — actual_production, energy_production_today, energy_production_lifetime
2. **Solar Estimation Sensors** — 7 forecast solar entity ID fields

## Routes

### GET `/dashboard/solar`

Renders the solar dashboard. Builds the template context:

- `solar_sensors` — All 12 sensor entity IDs (3 live + 7 estimation + actual_consumption and actual_injection from EnergyFeed for flow calculation)
- `is_configured` — Boolean flag from the Solar model

When `is_configured` is `False`, the template renders an empty state with a link to `settings_device.solar_panels`.

### GET/POST `/settings/solar-panels`

Settings route for configuring solar sensors. On POST saves sensor mappings and estimation sensor mappings via `SolarManager`. On GET populates form fields from the current `Solar` config.

### GET `/api/ha/config`

Shared route (used by all dashboards). Returns the Home Assistant URL and access token as JSON for frontend WebSocket authentication.

## Frontend

### Page Layout

The dashboard uses a grid layout with the following sections when configured:
1. **Page Header** — Title
2. **Solar Overview Card** — Contains the current production hero on the left (separated by a grey border-right) and a 2-column grid of stat cards on the right styled identically to the home battery dashboard's `.battery-stat` cards. Each `.solar-stat` card shows a production-colored icon, a bold value, and an uppercase label. The six stat cards are: Produced This Hour, Produced Today, Estimated This Hour, Estimated Today, Estimated Next Hour, and Estimated Tomorrow.
3. **Production vs Forecast Chart** — Time-series line chart comparing actual production (yellow) against forecast (blue dashed). Defaults to showing the entire current day (00:00–23:59). Past forecast data comes from `estimated_actual_production`; future forecast data comes from `estimated_actual_production_offset_day` (each data point at time t represents forecast for t+24h, so timestamps are shifted +24h and only future points are plotted). Includes a range selector with start/end datetime pickers and back/forward buttons (±6h) for navigating the time window. All chart animations are disabled to prevent visual glitches during live updates.

### JavaScript Architecture

All JS follows the project rules (separate files, no inline scripts except backend variable injection):

- **solar-charts.js** — Loaded as a regular script. Provides `create_solar_production_chart()` (time-series with actual + forecast datasets, x-axis spanning the full day, animations disabled), `update_solar_chart_range()` (update chart x-axis bounds on range change), `update_solar_production_chart_realtime()` (only updates the actual production dataset; replaces the last data point if within 1 minute to prevent accumulation), and `clear_solar_charts()`. Uses the globally loaded Chart.js 4.5.1.
- **solar-dashboard.js** — Loaded as an ES module. Handles HA WebSocket connection via `home-assistant-js-websocket`. Orchestrates sensor subscriptions, DOM updates, chart feeding, history fetching for the selected range (including future forecast from `estimated_actual_production_offset_day` shifted +24h), and range control initialization (defaults to full day, ±6h shift buttons, datetime pickers). Realtime entity subscription callbacks only feed actual production values to the chart — forecast values are not pushed in realtime because the forecast curve is already fully constructed from history (past) and offset entity data (future).

The only inline script in the template injects `window.SOLAR_CONFIG` with all sensor entity IDs from the backend.

### WebSocket Connection

Same pattern as the live dashboard:

1. Fetches HA connection config from `/api/ha/config`
2. Creates a long-lived token auth connection
3. Fetches production and forecast history for the selected range via `history/history_during_period`
4. Subscribes to live entity updates via `subscribeEntities`

### Color Scheme

| Color Variable | Hex | Usage |
|---|---|---|
| `--color-production` | `#ebe730` | Hero card border, sensor-item borders/backgrounds, chart actual production line |
| `--color-usage` | `#1e90ff` | Forecast/estimation chart line |
