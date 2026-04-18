# Devices Dashboard

## Overview

The devices dashboard provides an at-a-glance view of all registered devices in the energy management system. Each device card displays type-specific sections organized by priority, with live Home Assistant state data for entity parameters. Automatable devices show a toggle switch in the card header for quick on/off control. The device detail page displays comprehensive information organized into per-type section cards.

Device cards show up to 3 type sections (configurable via `MAX_DEVICE_CARD_SECTIONS`), prioritized as follows:
1. **Primary type** — always shown first (unless the primary type is `automatable_device`, which is handled as a toggle instead)
2. **Additional types** — selected from the device's secondary types in priority order: Energy Reporting → Deferrable Load → Battery Device → Duration Reporting → Home Battery → EV → Charging Station → Heat Pump → Electric Heating → Water Heater → Washing Machine → Dryer → Dishwasher

The priority order is defined in `DEVICE_TYPE_SECTION_PRIORITY` in `device_type.py`.

Parameters with `param_type: entity` display live Home Assistant state data fetched via WebSocket, with real-time updates. Non-entity parameters (float, int, string, bool) display their configured values directly.

## Relevant Artefacts

- [devices.html](../../web/templates/dashboard/devices.html) — Devices dashboard page
- [device-detail.html](../../web/templates/dashboard/device-detail.html) — Individual device detail page
- [dashboard.py](../../web/routes/dashboards/dashboard.py) — Dashboard routes
- [devices.css](../../web/static/css/dashboard/devices.css) — Dashboard device styling
- [device-entities.js](../../web/static/js/device-entities.js) — JS module for live HA entity state fetching, display and device toggling
- [models.py](../../web/model/device/models.py) — Device and DeviceType models
- [device_type.py](../../web/model/device/device_type.py) — DeviceType base class, section priority system, `get_device_sections()` helper
- [data_connector.py](../../web/model/data/data_connector.py) — DeviceManager, DeviceTypeManager

## Models

### Section Priority System (`device_type.py`)

The section priority system determines which device type sections are displayed on cards and detail pages:

- `DEVICE_TYPE_SECTION_PRIORITY` — ordered list of type IDs defining display priority
- `MAX_DEVICE_CARD_SECTIONS = 3` — configurable maximum number of sections shown on device cards
- `get_device_sections(device, type_registry, max_sections)` — returns an ordered list of `(type_id, DeviceType)` tuples for a device:
  - Primary type is always first (excluded if `automatable_device`)
  - Additional sections come from the priority list
  - `automatable_device` is excluded from sections (handled as a toggle)
  - Types not in the priority list are appended after prioritized types
  - Pass `max_sections=None` for unlimited sections (used on detail pages)

### Automatable Device

The `automatable_device` type receives special treatment:
- Not shown as a section — instead rendered as a toggle switch
- The toggle controls the device's `control_entity` via HA WebSocket `homeassistant.toggle` service
- Toggle state updates in real-time via entity subscription

## Routes

| Route | Method | Description |
|---|---|---|
| `/dashboard/devices` | GET | Dashboard overview showing all devices as cards. Supports optional `?type=<type_id>` query parameter to filter devices by type. |
| `/dashboard/device/<device_id>` | GET | Detail view for a single device with per-type section cards |
| `/dashboard/device/<device_id>/battery` | GET | Home battery dashboard (only for devices with `home_battery` as primary type) |
| `/api/ha/config` | GET | Returns HA connection config for frontend WebSocket auth |

### Dashboard Route

The `/dashboard/devices` route loads all devices via `DeviceManager` and the full type registry via `DeviceTypeManager`. For each device, it pre-computes:
- `is_automatable` — whether the device has the `automatable_device` type
- `control_entity` — the control entity ID (if automatable)
- `sections` — ordered type sections via `get_device_sections()`

This `device_info` dict is passed to the template keyed by device ID.

### Device Detail Route

The `/dashboard/device/<device_id>` route checks if the device's **primary type** has a custom dashboard template (e.g., `home_battery` → `home-battery.html`). If so, it renders that template. Otherwise, it renders the default sectioned detail page with all type sections (no section limit) and automatable toggle info. For deferrable loads, it also fetches schedule data from the `OptimizationManager`: today's weekly schedule entry (cycle count, time window) and plan schedule blocks from the latest optimization result.

## Frontend

### Live Entity State Display (`device-entities.js`)

An ES module that connects to Home Assistant via WebSocket to fetch and display live entity states on device pages. It:

1. Scans the DOM for elements with `data-entity-id` attributes (entity state display) and `data-entity-toggle` attributes (toggle switches)
2. Fetches HA connection config from `/api/ha/config`
3. Establishes a WebSocket connection using `home-assistant-js-websocket`
4. Subscribes to entity state updates via `subscribeEntities`
5. Updates matching DOM elements in real-time whenever entity state changes
6. Handles toggle switch click events by calling `homeassistant.toggle` via `callService`
7. Prevents toggle clicks from triggering card navigation (via `.device-toggle-wrapper` click interception)

**Entity domain handling:**

| Domain | Display | Example |
|---|---|---|
| `sensor.*`, `input_number.*` | Value + unit of measurement | `42 %`, `2.3 kW` |
| `switch.*`, `input_boolean.*` | On / Off with color state | `On` (green), `Off` (gray) |
| `binary_sensor.*` | Active/Inactive (or Open/Closed for door class) | `Active` (green) |
| `climate.*` | Temperature + HVAC action | `21°C · heating` |
| `cover.*` | State capitalized | `Open`, `Closed` |
| Other | Raw state + unit if available | State value |

Each entity display includes a status indicator dot:
- Green: entity available and connected
- Gray: entity unavailable or unknown
- Red: HA connection failed

When HA is not connected or has no token configured, all entity elements show an appropriate error message instead of loading indefinitely.

### Devices Dashboard (`devices.html`)

Displays a grid of device cards. The page header includes an "Add Device" button linking to the settings add-device form. Each card shows:
- Device type icon (from primary type, FontAwesome)
- Device name and primary type name
- Toggle switch (top right, if device has `automatable_device` type) — controls the device's `control_entity`
- Up to 3 type sections (configurable), each showing:
  - Section header with type icon and name
  - Up to 2 configured parameter values per section (entity params show live HA state)

When no devices are configured, an empty state message is shown with a link to the device settings page.

### Device Detail (`device-detail.html`)

Shows a device dashboard organized by type sections with custom metric-tile layouts:
- **Header**: Device icon, name, primary type label, and toggle switch (if automatable) aligned side-by-side via flex layout
- **Schedule card** (deferrable loads only): Shows today's planned cycles from the optimization weekly schedule, schedule blocks with start/end times and power, and a weekly overview with badge indicators per day
- **Type Section cards**: One card per device type (all types, no limit), each with a custom metric-tile layout per type:
  - `energy_reporting_device` — live power + total energy sensors
  - `battery_device` — battery level, capacity, charge/discharge power
  - `deferrable_load` — nominal power, duration, operating window, priority
  - `duration_reporting_device` — remaining time sensor
  - `home_battery` — max charge/discharge power, battery mode, link to battery dashboard
  - `electric_vehicle` — estimated range, charging state
  - `charging_station` — max charge rate, session energy
  - `heat_pump` — temperature, COP
  - `electric_heating` — temperature, thermostat
  - `water_heater` — water temperature
  - Unknown types fall back to generic metric tiles from custom parameter definitions
- Action buttons: Edit device (links to settings), back to dashboard

Custom dashboards: If the device's primary type has a registered custom dashboard template (e.g., `home_battery`), that template is used instead of the default sectioned layout.

### Styling (`devices.css`)

- `.device-dashboard-card` — Card layout with hover effect and icon/info sections
- `.device-toggle-wrapper` — Positions the automatable toggle at the top right of the card header
- `.device-dashboard-sections` — Container for type sections within a card
- `.device-type-section` — Individual type section with header and params
- `.device-section-header` — Uppercase type name with icon, separated by border
- `.device-detail-header` — Flex layout aligning device name and toggle side-by-side
- `.device-detail-title` — Title block within the detail header
- `.device-detail-toggle` — Toggle container within the detail header with flex-shrink
- `.section-metrics` — Flex wrap container for metric tiles within a type section
- `.metric-tile` — Individual metric display with icon, value, and label (min-width 160px, max-width 280px)
- `.metric-tile-highlight` — Highlighted metric variant with green left border
- `.metric-icon` / `.metric-content` / `.metric-value` / `.metric-label` — Metric tile sub-elements
- `.section-link` — Container for links within type sections (e.g., battery dashboard link)
- `.device-weekly-overview` — Weekly schedule overview container with border-top separator
- `.weekly-badges` — Flex row of day badges for the weekly schedule
- `.weekly-badge-item` / `.weekly-badge-day` — Individual badge items with day abbreviation and cycle count
- `.page-actions` — Action button container
- `.entity-state` — Flex container for entity indicator + value
- `.entity-state-compact` — Compact variant for device card previews
- `.entity-state-indicator` / `.indicator-active` / `.indicator-unavailable` / `.indicator-error` — Status dot with colors
- `.entity-state-value` / `.entity-sensor` / `.entity-on` / `.entity-off` / `.entity-unavailable` — Value text with state-dependent coloring
