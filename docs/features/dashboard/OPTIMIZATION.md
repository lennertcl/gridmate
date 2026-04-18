# Optimization Dashboard

## Overview

The optimization dashboard displays the current state and results of EMHASS energy optimization. It shows the EMHASS connection status, a stacked energy plan chart visualizing base load plus per-device scheduled power alongside solar production and battery charge/discharge, summary metrics for the optimized period, and a managed devices section showing both the home battery and deferrable load devices. Users can trigger manual optimization runs directly from the dashboard.

When no optimization results are available, the dashboard shows an empty state prompting the user to run their first optimization. When optimization is disabled entirely, a configuration prompt is shown instead.

## Relevant Artefacts

- [optimization.html](../../../web/templates/dashboard/optimization.html) — Dashboard template
- [optimization.py](../../../web/routes/dashboards/optimization.py) — Dashboard routes and API endpoints
- [optimization-dashboard.js](../../../web/static/js/optimization-dashboard.js) — Chart rendering and AJAX interactions
- [optimization.css](../../../web/static/css/dashboard/optimization.css) — Dashboard styles
- [models.py](../../../web/model/optimization/models.py) — OptimizationResult, DeviceSchedule, ScheduleEntry, TimeseriesPoint
- [optimization_manager.py](../../../web/model/optimization/optimization_manager.py) — Manager for config, deferrable loads, and EMHASS config sync
- [emhass_connector.py](../../../web/model/optimization/emhass_connector.py) — EMHASS API connector: config sync, runtime param building, optimization execution
- [scheduler.py](../../../web/model/optimization/scheduler.py) — Orchestrates optimization runs, battery SOC reading, actuation, notifications
- [solar_forecast.py](../../../web/model/optimization/solar_forecast.py) — Builds PV power forecast from solar estimation sensors
- [cost_forecast.py](../../../web/model/optimization/cost_forecast.py) — Builds load cost and production price forecasts from energy contract
- [result_store.py](../../../web/model/optimization/result_store.py) — Result persistence layer
- [connector.py](../../../web/model/optimization/connector.py) — Abstract OptimizerConnector interface
- [config_validator.py](../../../web/model/optimization/config_validator.py) — Validates optimization config before runs

## Models

### OptimizationResult

Returned by the optimizer after each run.

| Field | Type | Description |
|---|---|---|
| timestamp | datetime | When the optimization was run |
| optimization_type | str | dayahead or mpc |
| time_step_minutes | int | Timestep in minutes |
| pv_forecast | list[TimeseriesPoint] | Solar production forecast (kW) |
| load_forecast | list[TimeseriesPoint] | Non-deferrable base load consumption forecast (kW) |
| load_cost_forecast | list[TimeseriesPoint] | Import price series actually sent to EMHASS for optimization (€/kWh) |
| prod_price_forecast | list[TimeseriesPoint] | Export price series actually sent to EMHASS for optimization (€/kWh) |
| grid_forecast | list[TimeseriesPoint] | Net grid power forecast (kW) |
| battery_soc_forecast | list[TimeseriesPoint] | Battery SOC trajectory |
| battery_power_forecast | list[TimeseriesPoint] | Battery charge/discharge power (kW) |
| device_schedules | dict[str, DeviceSchedule] | Per-device on/off schedule blocks |
| device_power_forecasts | dict[str, list[TimeseriesPoint]] | Per-device power forecast timeseries (kW), used by the stacked energy plan chart |
| total_cost_eur | float | Total estimated cost for the period |
| total_grid_import_kwh | float | Total forecasted grid import |
| total_grid_export_kwh | float | Total forecasted grid export |
| total_pv_production_kwh | float | Total forecasted solar production |
| total_self_consumption_kwh | float | Total self-consumed energy |

### DeviceSchedule

| Field | Type | Description |
|---|---|---|
| device_id | str | Device identifier |
| device_name | str | Human-readable name |
| schedule_entries | list[ScheduleEntry] | On/off time blocks |
| total_energy_kwh | float | Total energy for this device |

### ScheduleEntry

| Field | Type | Description |
|---|---|---|
| start_time | datetime | Block start |
| end_time | datetime | Block end |
| power_w | float | Operating power during block |
| is_active | bool | Whether the device should be on |

### BatteryOptimizationConfig

Represents the home battery device's optimization configuration for display on the dashboard. Created via `BatteryOptimizationConfig.from_device()` which reads the device's `custom_parameters`.

| Field | Type | Description |
|---|---|---|
| device_id | str | Device identifier |
| device_name | str | Human-readable device name |
| enabled | bool | Whether battery optimization is enabled (from `opt_enabled`, defaults False) |
| capacity_kwh | float | Battery capacity in kWh |
| max_charge_power_kw | float | Maximum charging power in kW |
| max_discharge_power_kw | float | Maximum discharging power in kW |
| charge_efficiency | float | Charging efficiency factor 0-1 (from `charge_efficiency`, defaults 0.95) |
| discharge_efficiency | float | Discharging efficiency factor 0-1 (from `discharge_efficiency`, defaults 0.95) |
| min_charge_level | int | Minimum SOC percentage (from `min_charge_level`, defaults 20) |
| max_charge_level | int | Maximum SOC percentage (from `max_charge_level`, defaults 80) |
| target_soc | int | Target SOC percentage (from `target_soc`, defaults 80) |

The `opt_enabled` flag on the `home_battery` device type controls whether the battery is included in EMHASS optimization. `EmhassConnector._find_home_battery_device()` returns `None` when `opt_enabled` is False, which gates both `_build_runtime_params()` and `build_emhass_config_dict()` — no battery parameters are sent to EMHASS and `set_use_battery` is set to False.

`OptimizationManager.get_managed_battery()` returns the battery config regardless of `opt_enabled` so the dashboard always shows the battery card (with the toggle reflecting the current state). The EMHASS connector separately enforces the gate.

## Routes

### Dashboard Routes (dashboard_optimization_bp)

| Method | Path | Handler | Description |
|---|---|---|---|
| GET | /dashboard/optimization | optimization_dashboard | Dashboard page |
| GET | /api/optimization/status | optimization_status | Current optimization status JSON |
| GET | /api/optimization/schedule | optimization_schedule | Latest optimization result JSON |
| POST | /api/optimization/run | run_optimization | Trigger manual optimization run |
| POST | /api/optimization/device/<device_id>/override | set_device_override | Set next-optimization override for a device (num_cycles, hours_between_runs, earliest_start_time, latest_end_time) |
| POST | /api/optimization/device/<device_id>/clear-override | clear_device_override | Remove next-optimization override for a device |

### Optimization Run Flow

When POST `/api/optimization/run` is called:

1. **Config gathering** — OptimizationManager reads OptimizationConfig and enabled deferrable loads from settings
2. **EMHASS config sync** — OptimizationManager calls `sync_config_to_emhass` which builds a config dict from user settings (solar, battery, energy contract, forecaster, devices) and POSTs it to EMHASS `/set-config`
3. **Runtime params** — EmhassConnector builds runtime parameters:
   - `load_cost_forecast` and `prod_price_forecast` from CostForecastService (energy contract + Nord Pool sensor history)
   - `load_power_forecast` from OptimizationConfig load power config (time-of-day patterns or sensor data)
   - `pv_power_forecast` from SolarForecastService (fetches 24h history of the `estimated_actual_production_offset_day` sensor and maps it to forecast timesteps using naive persistence, converts kW to W) — falls back to EMHASS internal weather-based method if unavailable
   - Battery physical params from device `custom_parameters` (capacity, charge/discharge power, efficiency, SOC limits, target SOC) — only included when `opt_enabled` is True on the home_battery device
   - `soc_init` read internally from the home battery device's `battery_level_sensor` via HA REST API
   - Deferrable load schedules from enabled devices
4. **Optimization execution** — EmhassConnector POSTs runtime params to EMHASS `/action/dayahead-optim` or `/action/naive-mpc-optim`
5. **Result publishing** — EmhassConnector calls EMHASS `/action/publish-data` to publish optimization results as HA sensors
6. **Result reading** — EmhassConnector reads the published EMHASS result sensors from HA. Handles two EMHASS sensor formats: list-of-dicts with `date` key (for `forecasts` attribute), and battery-specific attributes (`battery_scheduled_power`, `battery_scheduled_soc`). Deferrable load data is read from `sensor.p_deferrable{i}` entities (EMHASS naming convention with `p_` prefix)
7. **Result storage** — OptimizationResultStore saves the result to JSON

### Data Sources

All optimization data comes from user configuration — no hardcoded values:

| Data | Source | Config Location |
|---|---|---|
| Battery capacity, charge/discharge power | Device custom_parameters | Settings > Devices (home_battery type) |
| Battery efficiency, SOC limits, target SOC | Device custom_parameters | Settings > Devices (home_battery type) |
| Current battery SOC | HA sensor via battery_level_sensor | Device custom_parameters |
| Energy buy/sell prices | Nord Pool sensor via HA history API | Settings > Energy Contract |
| PV power forecast | Solar estimation sensor history (naive persistence) | Settings > Solar |
| Load power forecast | Time-of-day config or HA sensor | Settings > Optimization |
| Grid import/export limits | OptimizationConfig | Settings > Optimization |
| Deferrable loads | Device custom_parameters (opt_enabled) | Settings > Devices |
| Battery optimization enabled | Device custom_parameters (opt_enabled on home_battery) | Settings > Devices |

## Services

### EmhassConnector

Primary interface between GridMate and the EMHASS REST API. Accepts `emhass_url`, `ha_connector`, and `data_connector` in its constructor.

Key responsibilities:
- **Config sync** via `build_emhass_config_dict` — maps user settings to EMHASS config format (sensor names, battery physical params in Wh/W, PV/battery flags, weather forecast method)
- **Runtime param building** via `_build_runtime_params` — assembles all forecast data, battery params (including SOC read from HA internally), deferrable load configs into a single dict for EMHASS action endpoints
- **Deferrable load EMHASS mapping** — `treat_deferrable_load_as_semi_cont` is set from `is_constant_power` (semi-continuous = on at max or off). `set_deferrable_load_single_constant` is set to True when `is_continuous_operation` is True (forces in a single contiguous block). Start/end timesteps are computed pairwise via `_compute_load_time_window` which validates that end > start, re-wrapping to the next day if the end time resolves before the start within the optimization window
- **Optimization execution** — POSTs to EMHASS day-ahead or MPC endpoints. The connector interface accepts only `OptimizationConfig`; operational state like battery SOC is read internally
- **Result publishing** — calls EMHASS `/action/publish-data` after optimization to push results to HA as sensors
- **Result parsing** — reads EMHASS result sensors from HA silently (no warnings for missing sensors) and builds OptimizationResult. Handles EMHASS list-of-dicts format (`[{date: ..., key: value}]`) and battery-specific attribute names (`battery_scheduled_power`, `battery_scheduled_soc`). Deferrable load entities use EMHASS naming: `sensor.p_deferrable{i}` (with `p_` power prefix). Both raw per-timestep power forecasts (`device_power_forecasts`) and aggregated on/off schedule blocks (`device_schedules`) are built from the same entity data. Schedule blocks use average power across all timesteps in the block

Battery physical parameters are sourced entirely from the home_battery device's `custom_parameters`: capacity_kwh, max_charge_power, max_discharge_power (converted from kW/kWh to W/Wh for EMHASS), charge_efficiency, discharge_efficiency, min_charge_level, max_charge_level, and target_soc (converted from percentage to 0-1 fraction for EMHASS). Current SOC is read from the device's `battery_level_sensor` HA entity. Battery parameters are only included when the device's `opt_enabled` flag is True — `_find_home_battery_device()` checks both `capacity_kwh > 0` and `opt_enabled` before returning the device.

### SolarForecastService

Builds PV power forecast from the `estimated_actual_production_offset_day` solar estimation sensor (Forecast.Solar's "Estimated Power Production - Next 24 Hours" sensor). Uses a naive persistence approach: fetches the sensor's 24-hour history from HA, where each historical state at time T represents the predicted power (kW) at T+24h. This past-24h history directly maps to the next-24h forecast. Sensor values are converted from kW to W (×1000). Falls back to EMHASS internal weather forecast when no sensor data or history is available.


### CostForecastService

Builds `load_cost_forecast` (buy price) and `prod_price_forecast` (sell price) from the energy contract configuration. Reads variable pricing sensor history from HA and applies fixed components (taxes, distribution, injection fees) to compute total buy and sell prices per timestep.

### OptimizationScheduler

Orchestrates the full optimization run:
- Delegates to EmhassConnector for optimization execution (the connector handles SOC reading and result publishing internally)
- Stores results via OptimizationResultStore
- Handles post-optimization actuation (automatic device control via HA automations)

## Frontend

### Dashboard Layout

1. **Status Bar** — Full-width card showing EMHASS connection, actuation mode, last run time, and run status
2. **Energy Plan Chart** — Stacked bar chart (Chart.js) showing the 24-hour plan after the last day-ahead optimization. Base load shown as grey bars, each managed device stacked on top in distinct colors showing their scheduled power during planned windows. Battery charge/discharge power is stacked in teal (`#0f766e`) — positive values (charging) stack with consumption, negative values (discharging) extend below zero. Solar production is overlaid as a stepped yellow line. The same chart also overlays the import and export energy price series that were passed to EMHASS, rendered as stepped lines on a secondary right-hand y-axis in €/kWh. The chart uses a stepped (non-smooth) style reflecting the discrete time steps (typically 30 minutes). Rendered at a larger height (420px) for clarity
3. **Summary Cards** — 5-column grid with estimated cost, production, grid import, grid export, and self-consumption metrics
4. **Managed Devices** — Section showing all devices that participate in optimization. The home battery (if configured) appears first with a battery icon, showing capacity (kWh) and charge/discharge power limits (kW). Deferrable load devices follow, each showing nominal power, operating duration, time window constraints, today's schedule summary (number of cycles and gap), next planned optimization time, and override status. All devices have a per-device optimization enable toggle. Below each deferrable load device, the scheduled time blocks are shown as labeled chips with start/end times and operating power. An "Override next optimization" button expands inline controls using the same cycle editor UI as the settings page (cycles, hours between runs, earliest start, latest end) for temporarily changing the device config for the next optimization run only. Setting cycles to 0 disables the device for the next run. Active overrides are shown as a yellow banner with clear button. Overrides are automatically cleared after the next optimization run. When no devices are configured for optimization, a generic empty state message is shown

### JavaScript (optimization-dashboard.js)

- `checkStatus()` — Polls /api/optimization/status to update EMHASS badge color
- `renderEnergyPlanChart()` — Creates Chart.js stacked bar chart from load_forecast, device_power_forecasts, battery_power_forecast, pv_forecast, load_cost_forecast, and prod_price_forecast. The base load is taken directly from load_forecast (which represents non-deferrable household load). Device power forecasts are stacked on top, followed by battery charge/discharge power in teal. Solar production renders as a stepped line overlay, while import/export prices render as stepped lines on a secondary y-axis so the dashboard shows the exact prices used during optimization. Uses DEVICE_COLORS array for consistent per-device coloring and DEVICE_NAMES for human-readable labels
- `runOptimization()` — POSTs to /api/optimization/run, shows spinner, reloads on success
- `toggleDeviceOptimization()` — AJAX toggle of per-device optimization flag
- `toggleOverrideControls()` — Shows/hides inline override editor for a device
- `setDeviceOverride()` — POSTs override (num_cycles, hours_between_runs, earliest_start_time, latest_end_time) to the API, reloads on success
- `clearDeviceOverride()` — POSTs to clear-override API endpoint, reloads on success
