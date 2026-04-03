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
| actuation_mode | str | manual | manual, notify, or automatic |
| load_power_config | LoadPowerConfig | (default) | Non-deferrable load configuration |
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
- `get_latest_result()` — Read optimization result from ResultStore
- `sync_config_to_emhass()` — Build EMHASS config dict and push to EMHASS via set-config API
- `get_emhass_config()` — Fetch current live config from EMHASS via get-config API

### OptimizationScheduler

Orchestrates a single optimization run.

- `run_scheduled_optimization()` — Assigns deferrable loads, calls connector (defaults to dayahead), actuates devices if configured
- `_get_current_battery_soc()` — Reads SOC from home_battery devices with opt_enabled=True
- `_actuate_devices()` — Sends turn_on/turn_off commands to HA based on schedule
- `_send_notifications()` — Logs upcoming device activations

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
- `_read_result_entities()` — Reads EMHASS result entities from HA

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
| actuation_mode | SelectField | manual / notify / automatic |
| load_power_source_type | SelectField | sensor / schedule |
| load_power_sensor_entity | StringField | HA entity for load sensor |

Schedule blocks are submitted as JSON via a hidden `load_power_schedule_blocks` field (not a WTForms field).

## Routes

### Settings Routes (settings_optimization_bp)

| Method | Path | Handler | Description |
|---|---|---|---|
| GET/POST | /settings/optimization | optimization_settings | Settings form page. POST saves config and pushes to EMHASS. |
| GET | /api/optimization/emhass/status | emhass_status | EMHASS health check (accepts `?url=` to test a specific URL) |
| GET | /api/optimization/emhass/config | emhass_config | Fetch current live EMHASS config |
| POST | /api/optimization/device/<device_id>/toggle | toggle_device_optimization | Toggle opt_enabled for a device |

## Frontend

### Settings Page

Card-based layout with sections:
1. **EMHASS Connection** — URL, actuation mode, day-ahead schedule time, enable toggle, connection status indicator with test button
2. **Grid & Load** — Max import/export power, load power source type (sensor vs schedule), sensor entity field or schedule block editor
3. **EMHASS Configuration** — Fetch button to view the live config currently active in EMHASS
4. **Save** — Saves settings and automatically pushes updated config to EMHASS

### JavaScript (optimization-settings.js)

- `checkEmhassConnection()` — Reads the URL from the form field and passes it to the status API endpoint
- `toggleLoadPowerSource()` — Shows/hides sensor entity field or schedule block editor based on selected source type
- `initScheduleBlocks()` — Loads existing schedule blocks from the hidden field on page load
- `addScheduleBlock()` / `renderScheduleBlock()` — Dynamically add/render schedule block rows with time inputs and power value
- `updateScheduleBlocksHidden()` — Serializes current schedule blocks to the hidden JSON field
- `fetchEmhassConfig()` — Fetches and displays the live EMHASS config from the API
