# Home Battery Dashboard

## Overview

The home battery dashboard provides a real-time view of a home battery device's state of charge, power flow, operating mode, and historical data. It is accessible directly from the devices overview — when a user clicks on a home battery device, the custom battery dashboard is shown instead of the generic device detail page.

A **Home Battery** link is shown in the top navigation bar under the Dashboard menu. Its destination is determined dynamically via a context processor in `app.py`:
- If exactly **one** home battery device exists: links directly to that device's detail dashboard page.
- If **zero or multiple** home battery devices exist: links to the devices dashboard filtered by the `home_battery` type (`/dashboard/devices?type=home_battery`).

This works through the **custom dashboard template** mechanism: the `device_detail` route checks all of a device's type IDs against the `CUSTOM_DASHBOARD_TEMPLATES` map in `dashboard.py`. If a matching template is found, it is rendered instead of the generic `device-detail.html` fallback. For home batteries, the map entry is `'home_battery': 'dashboard/device/home-battery.html'`.

The route gathers parameters from **all** device types assigned to the device (primary + secondary), ensuring parameters from base types like `battery_device` are available alongside `home_battery`-specific parameters.

The dashboard connects to Home Assistant via WebSocket to display live sensor data, control the battery operating mode, and render a 24-hour history chart with battery level and power flow.

## Relevant Artefacts

- [home-battery.html](../../web/templates/dashboard/device/home-battery.html) — Dashboard template
- [home-battery.css](../../web/static/css/dashboard/home-battery.css) — Dashboard-specific styles
- [home-battery-dashboard.js](../../web/static/js/home-battery-dashboard.js) — Real-time WebSocket updates, gauge, chart, and mode control logic
- [dashboard.py](../../web/routes/dashboards/dashboard.py) — Route definitions
- [device_types.py](../../web/model/device/device_types.py) — Home battery and battery device type definitions with parameters
- [models.py](../../web/model/device/models.py) — Device model (parameters are read from `custom_parameters`)

## Models

The home battery dashboard does not use a dedicated domain model. It reads all configuration from the device's `custom_parameters` dict, which is populated based on parameter definitions from all assigned device types.

### Parameter Sources

Home battery devices typically use `home_battery` as primary type with `battery_device` and `energy_reporting_device` as secondary types. Parameters come from multiple types:

**From `battery_device` (base type):**

| Parameter | Type | Unit | Required | Description |
|---|---|---|---|---|
| `battery_level_sensor` | entity | % | yes | HA entity reporting the battery state of charge |
| `capacity_kwh` | float | kWh | yes | Total usable capacity of the battery |
| `power_sensor` | entity | kW | no | HA entity for charge/discharge power (positive = charging, negative = discharging) |

**From `home_battery` (primary type):**

| Parameter | Type | Unit | Required | Description |
|---|---|---|---|---|
| `max_charge_power` | float | kW | no | Maximum charging power |
| `max_discharge_power` | float | kW | no | Maximum discharging power |
| `mode_select_entity` | entity | — | no | HA select/input_select entity to switch the battery operating mode |

The `power_sensor` uses a single combined value where positive values indicate charging and negative values indicate discharging. This simplifies the configuration compared to maintaining separate charge and discharge sensors.

The `mode_select_entity` points to a Home Assistant `select` or `input_select` entity. The available mode options are fetched dynamically from the entity's `options` attribute, so any battery's specific modes are automatically supported without hardcoding.

### Example Device Configuration

```json
{
    "device_id": "home_battery_1707000000",
    "name": "BYD HVS 10.2",
    "primary_type": "home_battery",
    "secondary_types": ["battery_device", "energy_reporting_device"],
    "custom_parameters": {
        "battery_level_sensor": "sensor.byd_battery_soc",
        "capacity_kwh": 10.2,
        "power_sensor": "sensor.byd_battery_power",
        "max_charge_power": 5.0,
        "max_discharge_power": 5.0,
        "mode_select_entity": "select.battery_mode"
    }
}
```

### Default Secondary Types

When a user creates a new device with Home Battery as the primary type, the secondary types Battery Device and Energy Reporting Device are automatically pre-selected in the device form. This is a frontend-only UX convenience defined in the `DEFAULT_SECONDARY_TYPES` map in `device-form.js` — it does not constrain the user's choices and has no effect on backend logic. All concrete device types have similar defaults defined; see [DEVICES.md](../../docs/features/settings/device/DEVICES.md) for the full list.

## Routes

| Route | Method | Description |
|---|---|---|
| `/dashboard/device/<device_id>` | GET | Shows the home battery dashboard if the device has the `home_battery` type, otherwise shows the generic device detail page |

### Custom Dashboard Template Routing

The `device_detail` route in `dashboard.py` uses a `CUSTOM_DASHBOARD_TEMPLATES` dictionary to map device type IDs to custom dashboard templates. When a device is requested, the route iterates through all of the device's type IDs (primary + secondary). If any type ID has a matching entry in the map, that custom template is rendered with the device object, type registry, and all `custom_parameters` from **all assigned types** passed as individual template variables. If no match is found, the generic `device-detail.html` template is used as a fallback.

## Frontend

### Dashboard Layout (`home-battery.html`)

The template renders five sections in a `dashboard-grid`:

1. **Hero Card** — Full-width card with an SVG circular gauge showing battery level percentage (always green), and a 2×2 stats grid showing current power, stored energy, status (Charging/Discharging/Idle), and max capacity.

2. **Charge Rate Card** — A single centered bar representing the current charge/discharge rate relative to configured maximums. The bar has a center divider at zero: charging fills from center to right in green, discharging fills from center to left in orange. Max discharge power is labeled on the left, max charge power on the right, and the current power value floats above the bar at the corresponding position. Only shown if at least one power limit is configured.

3. **Energy Stored Card** — A compact card displayed alongside the charge rate card. Shows the cumulative energy usage value from the `energy_sensor` entity (provided by the `energy_reporting_device` secondary type). The title is top-aligned while the value and sublabel are centered.

4. **Battery Mode Card** — Displays the current battery operating mode and a dropdown selector to change it. The dropdown options are populated dynamically from the HA entity's `options` attribute. When the user selects a new mode and clicks Apply, a `select.select_option` service call is made via WebSocket. Only shown if `mode_select_entity` is configured.

5. **History Charts** — Two side-by-side Chart.js charts spanning full width:
   - **Battery Level (24h)** — Line chart showing battery level (%) over the last 24 hours with a green line and light green fill.
   - **Charge & Discharge (24h)** — Line chart showing power flow (kW) with Chart.js segment styling: segments where the average value is positive (charging) render in green, segments where the average is negative (discharging) render in orange. Fill extends to the origin line so the colored area reflects direction and magnitude.

Backend variables are injected into `window.BATTERY_CONFIG` via a `<script>` block in the template.

### Real-Time Updates (`home-battery-dashboard.js`)

An ES module that:

1. Reads `window.BATTERY_CONFIG` for device configuration
2. Connects to HA via WebSocket using the same pattern as `device-entities.js`
3. Subscribes to entity state changes via `subscribeEntities`
4. Updates the gauge (always green), power display, status text, stored energy, cumulative energy card (from `energy_sensor`), and charge rate bar in real-time
5. Monitors the mode select entity and updates the current mode display and dropdown options
6. Handles mode switching via the `select.select_option` HA service call
7. Fetches 24h history on initial load and renders it across two separate Chart.js charts (battery level and power)

**Gauge rendering:** The SVG circle uses `stroke-dasharray` and `stroke-dashoffset` to animate the fill level. The stroke color is always green (`var(--color-primary)`).

**Charge rate bar:** A single centered bar replaces the old dual power limit bars. The bar is split into two halves at the zero midpoint. Charging power fills the right half in green, discharging power fills the left half in orange, each proportional to its respective maximum. A floating indicator above the bar shows the current power value and tracks the fill position via CSS `left` positioning with smooth transitions.

**Cumulative energy:** The energy stored card reads its value directly from the `energy_sensor` HA entity (exposed by the `energy_reporting_device` secondary type), which reports cumulative energy consumption in kWh.

**Status determination:** Positive power values indicate charging, negative values indicate discharging. A threshold of 0.05 kW is used to avoid flickering between states.

**Mode control:** The mode entity's `options` attribute is used to populate the dropdown dynamically on first load only. This means the available modes are determined entirely by the Home Assistant entity — different batteries may expose different modes (e.g. zero mode, manual charge, standby, peak shaving). The current mode label is updated in real-time via WebSocket, but the dropdown selection is never overwritten by incoming updates — it is a pure input field. When the user selects a new mode and clicks Apply, a `select.select_option` service call is made via WebSocket.

### Styles (`home-battery.css`)

- `.battery-hero-card` — Full-width card with gradient background and left green border
- `.battery-hero` — Flex container for gauge and stats
- `.battery-gauge-ring` / `.gauge-fill` — SVG circular gauge with animated fill and status-dependent colors
- `.battery-stat` — Individual stat boxes with icon, value, and label
- `.charge-rate-*` — Centered charge/discharge bar with left/right halves, center divider, floating indicator, and limit labels
- `.battery-energy-card` / `.energy-stored-*` — Cumulative energy stored card with large value display and sublabel
- `.battery-history-row` / `.battery-history-card` — Side-by-side chart layout for battery level and power history
- `.battery-mode-*` — Mode control section with current mode display, dropdown selector, and apply button
- Responsive breakpoints at 900px and 600px for mobile layout (history charts stack vertically on narrow screens)
