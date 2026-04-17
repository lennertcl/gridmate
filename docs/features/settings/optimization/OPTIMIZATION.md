# Optimization Settings

## Overview

The optimization settings feature configures the EMHASS energy optimization engine integration. Users set the EMHASS connection URL, grid constraints, load power source, day-ahead schedule time, and actuation mode. Devices with the `deferrable_load` device type appear as schedulable loads that EMHASS can shift to optimal time slots based on energy prices and solar forecasts.

GridMate acts as the translation layer between the user-friendly settings UI and EMHASS's configuration format. There are two distinct data flows:
1. **EMHASS config (set-config API):** Static configuration GridMate pushes to EMHASS via the `POST /set-config` endpoint on save. Includes sensor mappings, battery specs, deferrable load definitions, grid limits.
2. **Runtime parameters:** Dynamic data GridMate passes to EMHASS with each optimization API call. Includes energy price forecasts, load power forecasts, current battery SOC.

Battery optimization is controlled via the `opt_enabled` custom parameter on devices with the `home_battery` type. Battery SOC limits, efficiency, and target SOC are configured as parameters on the HomeBattery device type. Solar production sensor data is automatically pulled from the solar panels configuration.

When settings are saved, GridMate stores them in `settings.json` under the `optimization_config` key and pushes the generated config to EMHASS via `set-config`.

Field explanations for all settings are available in the [Optimization guide](../../../web/templates/guides/optimization.html) page, accessible from the Guides navigation menu or via the link banner at the top of the settings page.

## Relevant Artefacts

- [optimization.html](../../../web/templates/settings/optimization.html) — Settings page template
- [optimization.py](../../../web/routes/settings/optimization.py) — Settings routes and API endpoints
- [models.py](../../../web/model/optimization/models.py) — Domain models (OptimizationConfig, DeferrableLoadConfig, LoadPowerConfig, LoadPowerScheduleBlock)
- [connector.py](../../../web/model/optimization/connector.py) — OptimizerConnector ABC
- [emhass_connector.py](../../../web/model/optimization/emhass_connector.py) — EMHASS REST API connector
- [cost_forecast.py](../../../web/model/optimization/cost_forecast.py) — Price forecast generation from EnergyContract
- [scheduler.py](../../../web/model/optimization/scheduler.py) — Optimization run orchestrator
- [ha_automation_manager.py](../../../web/model/optimization/ha_automation_manager.py) — HA automation CRUD for device actuation
- [result_store.py](../../../web/model/optimization/result_store.py) — Optimization result persistence
- [config_validator.py](../../../web/model/optimization/config_validator.py) — EMHASS config consistency validation
- [optimization_manager.py](../../../web/model/optimization/optimization_manager.py) — High-level optimization config/operations manager
- [optimization.py](../../../web/forms/optimization.py) — WTForms form definitions
- [data_connector.py](../../../web/model/data/data_connector.py) — DataConnector extensions (get/set optimization_config)
- [device_types.py](../../../web/model/device/device_types.py) — deferrable_load and home_battery device type definitions
- [optimization-settings.js](../../../web/static/js/optimization-settings.js) — Settings page interactivity
- [optimization.css](../../../web/static/css/settings/optimization.css) — Settings page styles

## Models

### OptimizationConfig

Stored under `optimization_config` in `settings.json`.

| Field | Type | Default | Description |
|---|---|---|---|
| emhass_url | str | http://localhost:5000 | EMHASS add-on REST API URL |
| enabled | bool | false | Master switch for automated optimization |
| dayahead_schedule_time | str | 05:30 | HH:MM time to run day-ahead optimization |
| max_grid_import_w | int | 9000 | Grid import power limit in watts |
| max_grid_export_w | int | 9000 | Grid export power limit in watts |
| actuation_mode | str | manual | manual or automatic |
| load_power_config | LoadPowerConfig | (default) | Non-deferrable load configuration |
| weekly_schedule | WeeklySchedule | (empty) | Per-day per-device scheduling configuration (Mon-Sun) |
| next_run_overrides | list[DeviceDayEntry] | [] | Transient overrides for the next optimization run, auto-cleared after run |
| last_optimization_run | datetime | null | Timestamp of last optimization run |
| last_optimization_status | str | '' | Status of last optimization run |
| last_updated | datetime | null | Last config change |

Battery and solar settings are no longer part of OptimizationConfig. Battery optimization is controlled per-device via `opt_enabled` on the `home_battery` device type. Solar is auto-detected from the solar panels configuration.

### LoadPowerConfig

Defines how non-deferrable household load is provided to EMHASS.

| Field | Type | Default | Description |
|---|---|---|---|
| source_type | str | sensor | `sensor` (HA entity) or `schedule` (repeating daily schedule) |
| sensor_entity | str | '' | HA entity ID when source_type is `sensor` |
| schedule_blocks | list[LoadPowerScheduleBlock] | [] | Time blocks when source_type is `schedule` |

The `build_forecast()` method generates a per-timestep power array from the schedule blocks for passing into EMHASS runtime params as `load_power_forecast`.

### LoadPowerScheduleBlock

| Field | Type | Default | Description |
|---|---|---|---|
| start_time | str | 00:00 | HH:MM start of the block |
| end_time | str | 23:59 | HH:MM end of the block |
| power_w | float | 0.0 | Load power during the block in watts |

### DeviceDayEntry

Represents one device's schedule configuration for a single day. Also used as the model for next-run overrides.

| Field | Type | Default | Description |
|---|---|---|---|
| device_id | str | '' | Reference to the parent Device |
| num_cycles | int | 1 | Number of times the device should be powered on. 0 = disabled for the day |
| hours_between_runs | float | 0.0 | Minimum gap in hours between consecutive cycles |
| earliest_start_time | str | '' | Optional per-day override for device earliest start (HH:MM). Empty = use device default |
| latest_end_time | str | '' | Optional per-day override for device latest end (HH:MM). Empty = use device default |

A device is considered disabled for a particular day when `num_cycles` is 0. The `opt_enabled` device parameter remains the master switch: if `opt_enabled` is false, the device is excluded from optimization entirely regardless of the schedule.

### WeeklySchedule

Dict of `monday`–`sunday` → `List[DeviceDayEntry]`. Stored in `OptimizationConfig.weekly_schedule`.

- `get_today()` — Returns the list of DeviceDayEntry for the current weekday
- `get_day(day_name)` — Returns entries for a specific day
- `get_device_entry_for_today(device_id)` — Finds a specific device's entry for today

When the weekly schedule is empty (no entries configured), all enabled devices default to 1 cycle per day with no gap.

### DeferrableLoadConfig

Built from Device objects that have the `deferrable_load` device type. Parameters are stored in the device's `custom_parameters`.

| Field | Type | Default | Description |
|---|---|---|---|
| device_id | str | '' | Reference to the parent Device |
| enabled | bool | true | Include this load in optimization |
| nominal_power_w | float | 0 | Operating power in watts |
| operating_duration_hours | float | 0 | How long the device needs to run |
| is_constant_power | bool | true | Semi-continuous: device runs at full nominal power or off |
| is_continuous_operation | bool | false | Single constant power profile: runs as one uninterrupted block |
| earliest_start_time | str | '' | HH:MM earliest allowed start |
| latest_end_time | str | '' | HH:MM latest allowed end |
| startup_penalty | float | 0 | Cost penalty per start in EUR |
| priority | int | 5 | Priority 1 (highest) to 10 (lowest) |

## Services

### OptimizationManager

High-level manager wrapping DataConnector for optimization operations.

- `get_config()` / `save_config()` — Read/write OptimizationConfig
- `get_deferrable_loads()` — Build DeferrableLoadConfig list from devices with deferrable_load type, sorted by priority
- `get_enabled_deferrable_loads()` — Filtered list of loads where `enabled` is true
- `get_effective_deferrable_loads(config)` — Applies weekly schedule + overrides, expands multi-cycle devices into separate EMHASS deferrable loads. Applies per-day earliest_start/latest_end overrides from DeviceDayEntry. Returns `(expanded_loads, index_mapping)` where mapping tracks EMHASS index → (device_id, cycle_number)
- `clear_next_run_overrides(config)` — Clears all next-run overrides and persists config
- `get_latest_result()` — Read optimization result from ResultStore
- `sync_config_to_emhass()` — Build EMHASS config dict using effective loads and push to EMHASS via set-config API
- `get_emhass_config()` — Fetch current live config from EMHASS via get-config API

#### Multi-Cycle Expansion Algorithm

When a device has N cycles with H-hour gap, its time window (earliest_start to latest_end, optionally overridden per day) is divided into N non-overlapping sub-windows:

1. `total_hours = latest_end - earliest_start`
2. `window_size = (total_hours - (N-1) * H) / N`
3. Window i: `start = earliest + i * (window_size + H)`, `end = start + window_size`

Example: device with window 08:00–16:00, 3 cycles, 1h gap → total 8h, gap total 2h, window_size 2h → slots [08:00–10:00], [11:00–13:00], [14:00–16:00]

If window_size < operating_duration_hours, falls back to 1 cycle.

### OptimizationScheduler

Orchestrates a single optimization run.

- `run_scheduled_optimization()` — Assigns deferrable loads, calls connector (defaults to dayahead), actuates devices if configured
- `_actuate_devices()` — In automatic mode, delegates to `HAAutomationManager.sync_device_automations()` to create HA automations for device control

### HAAutomationManager

Manages Home Assistant automations for device actuation via the HA REST API (`/api/config/automation/config/{id}`).

- `ensure_trigger_automation(config)` — Creates/updates a `[gridmate] Daily Optimization` HA automation that calls `rest_command.gridmate_run_optimization` at the configured `dayahead_schedule_time`
- `remove_trigger_automation()` — Deletes the daily trigger automation
- `sync_device_automations(result)` — Deletes all existing `[gridmate]` device automations, then creates one automation per device with active schedule entries. Each automation uses time-based triggers and `choose` actions
- `cleanup_all_automations()` — Removes all `[gridmate]` automations (trigger + device)
- `cleanup_device_automations()` — Removes only device automations, keeps the trigger

Automation structure per device:
- **Constant power devices** — All "on" triggers share one `choose` branch (turn_on control_entity), all "off" triggers share another (turn_off)
- **Variable power devices** — Each "on" trigger gets its own branch with turn_on + `number.set_value` on the `power_control_entity` at the schedule block's power level. All "off" triggers grouped

Automation IDs are deterministic: `gridmate_daily_optimization` for the trigger, `gridmate_device_{device_id}` per device.

### EmhassConnector

Translates GridMate config to EMHASS API calls.

- `is_available()` — Health check via GET /get-config
- `get_emhass_config()` — GET /get-config, returns current EMHASS config dict
- `set_emhass_config()` — POST /set-config, pushes config dict to EMHASS
- `run_dayahead_optimization()` — POST /action/dayahead-optim with runtime params
- `run_mpc_optimization()` — POST /action/naive-mpc-optim with runtime params
- `build_emhass_config_dict()` — Generates EMHASS config from GridMate settings (battery, solar, deferrable loads, grid limits)
- `_build_runtime_params()` — Generates per-run dynamic data: cost forecasts, load power forecast, battery SOC
- `_is_battery_optimization_enabled()` — Checks devices for home_battery type with opt_enabled=True
- `_read_result_entities()` — Reads EMHASS result entities from HA. Uses `load_mapping` to merge multiple EMHASS deferrable indices back into a single DeviceSchedule per device, summing power forecasts across cycles

### CostForecastService

Generates `load_cost_forecast` and `prod_price_forecast` arrays from the user's EnergyContract.

- Accepts `time_step` and `horizon_hours` directly (no longer depends on OptimizationConfig)
- Reads variable component sensor forecasts from HA entity attributes
- Falls back to P(t-24h) for missing forecast data

## Forms

### OptimizationSettingsForm

| Field | Type | Description |
|---|---|---|
| emhass_url | StringField | EMHASS URL |
| enabled | BooleanField | Enable optimization |
| dayahead_schedule_time | StringField | Day-ahead run time (HH:MM) |
| max_grid_import_w | IntegerField | Max grid import in watts |
| max_grid_export_w | IntegerField | Max grid export in watts |
| actuation_mode | SelectField | manual / automatic |
| load_power_source_type | SelectField | sensor / schedule |
| load_power_sensor_entity | StringField | HA entity for load sensor |
| weekly_schedule_data | HiddenField | Weekly schedule JSON blob |

Schedule blocks are submitted as JSON via a hidden `load_power_schedule_blocks` field. The weekly schedule is submitted as JSON via `weekly_schedule_data`.

## Routes

### Settings Routes (settings_optimization_bp)

| Method | Path | Handler | Description |
|---|---|---|---|
| GET/POST | /settings/optimization | optimization_settings | Settings form page. POST saves config, pushes to EMHASS, and manages HA automations (creates trigger automation when enabled, creates device automations only in automatic mode, cleans up when disabled). |
| GET | /api/optimization/emhass/status | emhass_status | EMHASS health check (accepts `?url=` to test a specific URL) |
| GET | /api/optimization/emhass/config | emhass_config | Fetch current live EMHASS config |
| POST | /api/optimization/device/<device_id>/toggle | toggle_device_optimization | Toggle opt_enabled for a device |

## Frontend

### Settings Page

Card-based layout with sections:
1. **EMHASS Connection** — URL, actuation mode, day-ahead schedule time, enable toggle, connection status indicator with test button
2. **Grid & Load** — Max import/export power, load power source type (sensor vs schedule), sensor entity field or schedule block editor
3. **EMHASS Configuration** — Fetch button to view the live config currently active in EMHASS
4. **Weekly Device Schedule** — Compact table (rows = deferrable devices, columns = Mon–Sun). Each row includes an opt_enabled toggle for the master switch. Each cell shows a badge with the cycle count (green if enabled and > 0, gray otherwise). Clicking a cell opens an inline editor with Cycles, Hours between runs, Earliest start, and Latest end fields plus an Apply button. "Apply to all days" button copies Monday's config to all other days. Devices with `opt_enabled=False` are grayed out
5. **Save** — Saves settings and automatically pushes updated config to EMHASS

### JavaScript (optimization-settings.js)

- `checkEmhassConnection()` — Reads the URL from the form field and passes it to the status API endpoint
- `toggleLoadPowerSource()` — Shows/hides sensor entity field or schedule block editor based on selected source type
- `initScheduleBlocks()` — Loads existing schedule blocks from the hidden field on page load
- `addScheduleBlock()` / `renderScheduleBlock()` — Dynamically add/render schedule block rows with time inputs and power value
- `updateScheduleBlocksHidden()` — Serializes current schedule blocks to the hidden JSON field
- `fetchEmhassConfig()` — Fetches and displays the live EMHASS config from the API
- `initWeeklySchedule()` — Loads weekly schedule from hidden JSON field, renders badges, attaches cell click handlers, apply-all buttons, and opt_enabled toggle handlers
- `toggleDeviceOpt()` — Toggles opt_enabled via API and updates row styling/badges
- `openCellEditor()` / `closeEditor()` / `saveCellFromEditor()` — Inline editor for per-cell schedule configuration (cycles, hours between runs, earliest start, latest end); requires explicit Apply button click
- `applyToAllDays()` — Copies Monday's config for a device to all other days
- `syncWeeklyScheduleHidden()` — Serializes current schedule state to hidden field
