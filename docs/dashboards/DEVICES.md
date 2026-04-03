# Devices Dashboard

## Overview

The devices dashboard provides an at-a-glance view of all registered devices in the energy management system. It shows device cards with type icons, parameter previews, and links to a detailed device view. The device detail page displays all configured parameters, type information (primary and secondary types), and navigation to the device edit form.

Parameters with `param_type: entity` display live Home Assistant state data fetched via WebSocket, with real-time updates. Non-entity parameters (float, int, string, bool) display their configured values directly. Entity IDs are only shown on the device detail page as a small reference — the raw ID is visible when editing the device in settings.

## Relevant Artefacts

- [devices.html](../../web/templates/dashboard/devices.html) — Devices dashboard page
- [device-detail.html](../../web/templates/dashboard/device-detail.html) — Individual device detail page
- [dashboard.py](../../web/routes/dashboards/dashboard.py) — Dashboard routes
- [devices.css](../../web/static/css/dashboard/devices.css) — Dashboard device styling
- [device-entities.js](../../web/static/js/device-entities.js) — JS module for live HA entity state fetching and display
- [models.py](../../web/model/device/models.py) — Device and DeviceType models
- [data_connector.py](../../web/model/data/data_connector.py) — DeviceManager, DeviceTypeManager

## Routes

| Route | Method | Description |
|---|---|---|
| `/dashboard/devices` | GET | Dashboard overview showing all devices as cards. Supports optional `?type=<type_id>` query parameter to filter devices by type. |
| `/dashboard/device/<device_id>` | GET | Detail view for a single device with full parameter list |
| `/dashboard/device/<device_id>/battery` | GET | Home battery dashboard (only for devices with `home_battery` type) |
| `/api/ha/config` | GET | Returns HA connection config for frontend WebSocket auth |

### Dashboard Route

The `/dashboard/devices` route loads all devices via `DeviceManager` and the full type registry via `DeviceTypeManager`. It passes both to the template so each device card can display the correct icon and type name. An optional `?type=<type_id>` query parameter filters devices to only those with the given type (primary or secondary). When a filter is active, the page title and subtitle reflect the filter and a link to clear it is shown.

### Device Detail Route

The `/dashboard/device/<device_id>` route loads a single device and its primary device type. It computes the full parameter list from all assigned types (primary + secondary) via `device.get_all_parameters(type_registry)` and passes this to the template along with the device's configured values.

## Frontend

### Live Entity State Display (`device-entities.js`)

An ES module that connects to Home Assistant via WebSocket to fetch and display live entity states on device pages. It:

1. Scans the DOM for elements with `data-entity-id` attributes (rendered by templates for entity-type parameters)
2. Fetches HA connection config from `/api/ha/config`
3. Establishes a WebSocket connection using `home-assistant-js-websocket`
4. Subscribes to entity state updates via `subscribeEntities`
5. Updates matching DOM elements in real-time whenever entity state changes

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
- Device name
- Primary type name as a badge
- Secondary type count (if any)
- Up to 3 parameter previews: entity-type params show live HA state, non-entity params show configured values
- Click-through link to the device detail page

When no devices are configured, an empty state message is shown with a link to the device settings page.

### Device Detail (`device-detail.html`)

Shows comprehensive device information:
- Header with icon, name, and primary type badge
- **Primary Type**: Displayed prominently with icon and name
- **Secondary Types**: List of additional types with their icons, shown only if secondary types exist
- **Battery Dashboard Link**: If the device has the `home_battery` type (primary or secondary), a card with a link to the dedicated Home Battery Dashboard is shown. See [HOME_BATTERY.md](HOME_BATTERY.md) for details.
- **Parameters Table**: A two-column fixed-width table (Parameter, Value) showing all assigned parameters. Uses the `.params-table` modifier on `.device-table` to override the default 5-column grid. Entity-type parameters show live HA state with a small entity ID reference below. Non-entity parameters show their configured value directly.
- Action buttons: Edit device (links to settings), back to dashboard

### Styling (`devices.css`)

- `.device-dashboard-card` — Card layout with hover effect and icon/info sections
- `.device-dashboard-secondary` — Secondary type count display on device cards
- `.detail-grid` / `.detail-row` — Detail page grid layout for info rows
- `.type-badge-list` / `.type-badge-item` — Styled list for primary and secondary types on detail page
- `.page-actions` — Action button container
- `.entity-state` — Flex container for entity indicator + value
- `.entity-state-compact` — Compact variant for device card previews
- `.entity-state-indicator` / `.indicator-active` / `.indicator-unavailable` / `.indicator-error` — Status dot with colors
- `.entity-state-value` / `.entity-sensor` / `.entity-on` / `.entity-off` / `.entity-unavailable` — Value text with state-dependent coloring
- `.entity-id-ref` — Small monospace entity ID reference shown on detail page
- `.params-table` — Overrides `.device-table` grid to a 2-column layout for the device detail parameters table
- `.col-param-name` / `.col-param-value` — Fixed-width columns for the parameters table
