# GridMate Optimization: EMHASS Integration Plan

> **Status:** Implementation Plan  
> **Date:** 2026-03-01  
> **Scope:** Full integration of EMHASS as the optimization engine for GridMate

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Vendor Abstraction: The Optimizer Interface](#2-vendor-abstraction-the-optimizer-interface)
3. [Data Flow](#3-data-flow)
4. [New Device Type: Deferrable Load](#4-new-device-type-deferrable-load)
5. [Configuration](#5-configuration)
6. [Domain Models](#6-domain-models)
7. [Optimizer Abstraction Layer](#7-optimizer-abstraction-layer)
8. [Cost Forecast Generation](#8-cost-forecast-generation)
9. [Optimization Scheduler Service](#9-optimization-scheduler-service)
10. [EMHASS Configuration Sync](#10-emhass-configuration-sync)
11. [API Endpoints](#11-api-endpoints)
12. [UI Specifications](#12-ui-specifications)
13. [Persistence](#13-persistence)
14. [DataConnector Extensions](#14-dataconnector-extensions)
15. [Forms](#15-forms)
16. [Templates & Static Assets](#16-templates--static-assets)
17. [Navigation & Blueprint Registration](#17-navigation--blueprint-registration)
18. [Home Assistant Automation Integration](#18-home-assistant-automation-integration)
19. [File Structure Summary](#19-file-structure-summary)
20. [Implementation Phases](#20-implementation-phases)
21. [Risk Assessment](#21-risk-assessment)
22. [Architectural Decisions](#22-architectural-decisions)
23. [Appendices](#appendices)

---

## 1. System Overview

GridMate, EMHASS, and Home Assistant form a three-layer energy management system:

| Layer | Component | Role |
|-------|-----------|------|
| **Heart** | Home Assistant | Sensor data, device control, automation execution |
| **Brain** | EMHASS | Linear Programming optimization, forecasting, schedule generation |
| **Body** | GridMate | User interface, configuration, translation layer, schedule visualization, manual overrides |

**Deployment model:** Both GridMate and EMHASS run as separate Home Assistant add-ons. They communicate over the local Docker network. EMHASS exposes a REST API (default port 5000) that GridMate calls to trigger optimizations and retrieve results. Both add-ons use Home Assistant as their shared data backbone — EMHASS reads sensor data from HA and publishes optimization results as HA entities; GridMate reads those result entities and also talks directly to EMHASS's REST API.

```
┌───────────────────────────────────────────────────────┐
│                    Home Assistant                      │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Sensors &   │  │  EMHASS      │  │  GridMate    │ │
│  │ Devices     │  │  Add-on      │  │  Add-on      │ │
│  │             │  │  (port 5000) │  │  (port 8000) │ │
│  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                │                  │         │
│         │  HA REST/WS    │  EMHASS REST API │         │
│         ◄────────────────►◄─────────────────►         │
└───────────────────────────────────────────────────────┘
```

---

## 2. Vendor Abstraction: The Optimizer Interface

EMHASS must be **replaceable** by another optimization engine without redesigning the application. GridMate defines its own **Optimizer abstraction layer** — a Python interface that any optimization backend must implement. EMHASS is the first (and current) implementation.

**Key interfaces:**

- `OptimizerConnector` — abstract base class defining how GridMate talks to any optimizer
- `EmhassConnector` — concrete implementation that translates GridMate domain models into EMHASS API calls
- `OptimizationResult` — GridMate's own data model for optimization results (vendor-agnostic)
- `OptimizationSchedule` — a per-device, per-timestep schedule that GridMate understands
- `DeferrableLoadConfig` — GridMate's representation of a load that can be deferred

---

## 3. Data Flow

```
User configures devices and optimization settings in GridMate UI
                          │
                          ▼
GridMate translates device configs into EMHASS parameters
(deferrable loads, battery specs, cost forecasts)
                          │
                          ▼
GridMate calls EMHASS REST API:
  POST /action/dayahead-optim  (daily)
  POST /action/naive-mpc-optim (every N minutes)
  with runtimeparams JSON body
                          │
                          ▼
EMHASS runs optimization, publishes results as HA entities
(sensor.deferrable0_p, sensor.battery_soc, etc.)
                          │
                          ▼
GridMate reads optimization results from HA entities
and/or EMHASS API response
                          │
                          ▼
GridMate displays schedule on Optimization Dashboard
User can override/approve individual device schedules
                          │
                          ▼
GridMate (or HA automations) actuates devices:
  - Turns on/off deferrable loads at scheduled times
  - Sets battery charge/discharge modes
```

### 3.1 Translation Logic: GridMate → EMHASS

GridMate must translate its rich domain model into EMHASS's flat parameter lists:

| GridMate Concept | EMHASS Parameter |
|---|---|
| Devices with `deferrable_load` type | `number_of_deferrable_loads`, `nominal_power_of_deferrable_loads` |
| Device operating duration | `operating_hours_of_each_deferrable_load` |
| Device time window | `start_timesteps_of_each_deferrable_load`, `end_timesteps_of_each_deferrable_load` |
| Device "can be interrupted" = false | `set_deferrable_load_single_constant` = True |
| Device "can be interrupted" = true | `treat_deferrable_load_as_semi_cont` = True |
| Energy contract variable components | `load_cost_forecast` (list of €/kWh per timestep) |
| Energy contract injection rewards | `prod_price_forecast` (list of €/kWh per timestep) |
| Home battery settings | `battery_*` parameters |
| Solar config | `sensor_power_photovoltaics` |
| Energy feed actual consumption | `sensor_power_load_no_var_loads` |
| Max grid power | `maximum_power_from_grid`, `maximum_power_to_grid` |

#### Power Unit Conversion

GridMate uses kW internally (e.g. `power_sensor`, `max_charge_power`), but EMHASS uses **Watts** for all power values. All unit conversions must be centralised in the `EmhassConnector`:

```python
def _kw_to_w(self, kw: float) -> float:
    return kw * 1000.0

def _w_to_kw(self, w: float) -> float:
    return w / 1000.0
```

The connector multiplies all GridMate kW values by 1000 when assembling `runtimeparams`, and divides by 1000 when parsing results back. No other module handles this conversion.

### 3.2 Result Mapping: EMHASS → GridMate

EMHASS publishes results as Home Assistant entities:

| EMHASS Entity | Description | Data Location |
|---|---|---|
| `sensor.p_pv_forecast` | PV power forecast | `forecasts` attribute (list of {date, value} dicts) |
| `sensor.p_load_forecast` | Load power forecast | `forecasts` attribute |
| `sensor.p_deferrable{N}` | Deferrable load N power schedule | `deferrables_schedule` attribute |
| `sensor.p_batt_forecast` | Battery power forecast | `forecasts` attribute |
| `sensor.soc_batt_forecast` | Battery SOC forecast | `forecasts` attribute |
| `sensor.p_grid_forecast` | Grid power forecast | `forecasts` attribute |
| `sensor.total_cost_profit_value` | Total cost/profit | state value |
| `sensor.unit_load_cost` | Load cost forecast | `forecasts` attribute |
| `sensor.unit_prod_price` | Production price forecast | `forecasts` attribute |

Entity names may have a prefix if EMHASS's `publish_prefix` is used. GridMate supports configuring this prefix (default: empty).

GridMate maps results back to its device IDs using the ordered list of deferrable loads it submitted (deferrable load 0 in EMHASS → first device in the priority-sorted list, etc.).

### 3.3 Deferrable Load Sensor Subtraction

EMHASS's `sensor_power_load_no_var_loads` expects the household load sensor **with deferrable loads subtracted**. If the user's grid consumption sensor includes the boiler's consumption and the boiler is a deferrable load, the boiler's power must be subtracted.

**Approach:** The optimization settings page includes an info box explaining this requirement, with a copyable HA template sensor example:

```yaml
# Example: subtract deferrable loads from total consumption
template:
  - sensor:
      - name: "Household Load No Var Loads"
        unit_of_measurement: "W"
        state: >
          {{ states('sensor.total_power_consumption') | float(0)
             - states('sensor.boiler_power') | float(0)
             - states('sensor.heating_power') | float(0) }}
```

A future enhancement could have GridMate generate these template sensors automatically via the HA REST API.

---

## 4. New Device Type: Deferrable Load

A new **secondary device type** `deferrable_load` marks devices that participate in optimization. This type is additive — a washing machine might have types `[washing_machine, automatable_device, energy_reporting_device, deferrable_load]`.

### 4.1 Device Type Registration

Add to `web/model/device/device_types.py`:

```python
'deferrable_load': {
    'type_id': 'deferrable_load',
    'name': 'Deferrable Load',
    'icon': 'fas fa-clock',
    'description': 'A device whose operation can be scheduled by the optimizer',
    'custom_parameters': {
        'opt_enabled': {
            'name': 'opt_enabled',
            'label': 'Optimization Enabled',
            'param_type': 'bool',
            'default_value': True,
            'required': False,
            'description': 'Whether this device participates in optimization',
        },
        'opt_nominal_power': {
            'name': 'opt_nominal_power',
            'label': 'Nominal Power',
            'param_type': 'float',
            'unit': 'W',
            'required': True,
            'description': 'Power draw when operating',
            'placeholder': '2000',
        },
        'opt_duration_hours': {
            'name': 'opt_duration_hours',
            'label': 'Operating Duration',
            'param_type': 'float',
            'unit': 'hours',
            'required': True,
            'description': 'Required operating time per day',
            'placeholder': '3',
        },
        'opt_constant_power': {
            'name': 'opt_constant_power',
            'label': 'Constant Power',
            'param_type': 'bool',
            'default_value': True,
            'required': False,
            'description': 'When enabled, the device always runs at its full nominal power when active (on/off only). When disabled, the optimizer can vary the power between 0 and the nominal power.',
        },
        'opt_continuous_operation': {
            'name': 'opt_continuous_operation',
            'label': 'Continuous Operation',
            'param_type': 'bool',
            'default_value': False,
            'required': False,
            'description': 'When enabled, the device must complete its full run in one uninterrupted block.',
        },
        'opt_earliest_start': {
            'name': 'opt_earliest_start',
            'label': 'Earliest Start Time',
            'param_type': 'string',
            'required': False,
            'description': 'HH:MM format — earliest time the device may start',
            'placeholder': '08:00',
        },
        'opt_latest_end': {
            'name': 'opt_latest_end',
            'label': 'Latest End Time',
            'param_type': 'string',
            'required': False,
            'description': 'HH:MM format — latest time the device must finish',
            'placeholder': '22:00',
        },
        'opt_startup_penalty': {
            'name': 'opt_startup_penalty',
            'label': 'Startup Penalty',
            'param_type': 'float',
            'unit': '€',
            'default_value': 0.0,
            'required': False,
            'description': 'Cost penalty per startup event',
        },
        'opt_priority': {
            'name': 'opt_priority',
            'label': 'Priority',
            'param_type': 'int',
            'default_value': 5,
            'required': False,
            'description': '1 (highest) to 10 (lowest)',
        },
    },
}
```

These parameters are stored within the device's `custom_parameters` dict, keeping the existing `Device` model unchanged. The `DeferrableLoadConfig` is assembled dynamically from device data at optimization time — it is not duplicated in storage.

### 4.2 Device Type Compatibility

| GridMate Device Type | Can Be Deferrable Load? | Notes |
|---|---|---|
| `water_heater` | Yes | Classic deferrable load. Known power, flexible timing. |
| `electric_heating` | Yes | Can defer to solar/cheap hours. Temperature constraints may apply. |
| `washing_machine` | Yes | Fixed cycle duration. Single constant run typical. |
| `dryer` | Yes | Similar to washing machine. |
| `dishwasher` | Yes | Similar to washing machine. |
| `electric_vehicle` | Yes | Long charging sessions. Battery SOC awareness useful. |
| `charging_station` | Yes | EV charging infrastructure. |
| `heat_pump` | Partially | Complex — COP varies with temperature. Future thermal model. |
| `home_battery` | No (handled separately) | Battery is optimized via EMHASS battery model, not as deferrable load. |

---

## 5. Configuration

### 5.1 EMHASS Config vs. Runtime Params

Some parameters belong in EMHASS's `config.json` (set once at initial setup), while others can be passed as `runtimeparams` per API call. GridMate can generate the EMHASS base config from its own data so users don't need to configure things twice.

**Must be in EMHASS `config.json`:**
- `sensor_power_photovoltaics` (auto-populated from GridMate's solar config)
- `sensor_power_load_no_var_loads`
- `optimization_time_step`
- `set_use_battery`
- `set_use_pv`
- `number_of_deferrable_loads`
- `nominal_power_of_deferrable_loads`
- PV system parameters (module, inverter, tilt, azimuth)
- `weather_forecast_method` — always set to `open-meteo` as fallback; EMHASS ignores this when `pv_power_forecast` is passed via runtimeparams
- `load_cost_forecast_method` — set to `csv` so EMHASS uses the cost forecast from runtimeparams instead of its own methods
- `production_price_forecast_method` — set to `csv` so EMHASS uses the production price forecast from runtimeparams
- `load_forecast_method` — set to `csv` so EMHASS uses the load forecast from runtimeparams
- Location secrets

**Can be overridden via `runtimeparams` (GridMate sends these dynamically):**
- `pv_power_forecast`, `load_power_forecast` (lists of values)
- `load_cost_forecast`, `prod_price_forecast` (lists of values)
- `operating_hours_of_each_deferrable_load`
- `start_timesteps_of_each_deferrable_load`, `end_timesteps_of_each_deferrable_load`
- `treat_deferrable_load_as_semi_cont`, `set_deferrable_load_single_constant`
- `set_deferrable_startup_penalty`
- `nominal_power_of_deferrable_loads` (can override config)
- `number_of_deferrable_loads` (can override config)
- `battery_minimum_state_of_charge`, `battery_maximum_state_of_charge`, `battery_target_state_of_charge`
- `battery_charge_power_max`, `battery_discharge_power_max`
- `prediction_horizon` (for MPC)
- `soc_init`, `soc_final` (for MPC)
- `def_current_state` (for MPC — currently running loads)

### 5.2 Configuration Tiers

#### Tier 1: Initial Setup (EMHASS-side, rarely changed)
Configured once in the EMHASS add-on, or generated by GridMate for copy-paste:
- Home Assistant connection (usually auto-detected)
- Location (lat/lon/alt — auto-detected from HA)
- Solar/PV system details (module model, inverter model, tilt, azimuth)
- Weather forecast method (open-meteo, solcast, etc.)

#### Tier 2: Operational Configuration (GridMate-side)
Managed in GridMate:
- **EMHASS connection:** URL of the EMHASS instance (e.g., `http://localhost:5000`)
- **Cost function:** profit / cost / self-consumption
- **Optimization frequency:** How often to run MPC (5/15/30/60 min)
- **Optimization mode:** day-ahead only / MPC only / day-ahead + MPC
- **Per-device deferrable load settings:** power, duration, time windows, interruptibility
- **Battery optimization settings:** min/max SOC, target SOC, grid charge policy
- **Energy cost forwarding:** GridMate's `EnergyContract` generates `load_cost_forecast` and `prod_price_forecast` for EMHASS
- **Global constraints:** max grid import/export

---

## 6. Domain Models

The existing `Optimization` dataclass in `web/model/energy/models.py` is replaced with a comprehensive model in `web/model/optimization/models.py`.

### 6.1 `DeferrableLoadConfig`

```python
@dataclass
class DeferrableLoadConfig:
    device_id: str                    # Links to GridMate Device
    enabled: bool = True              # Whether this device participates in optimization
    nominal_power_w: float = 0.0      # Nominal power in Watts when operating
    operating_duration_hours: float = 0.0  # Required operating duration per cycle
    is_constant_power: bool = True    # Semi-continuous: device at nominal power or off
    is_continuous_operation: bool = False  # Must run as one continuous block
    earliest_start_time: str = ''     # HH:MM format, empty = no constraint
    latest_end_time: str = ''         # HH:MM format, empty = no constraint
    startup_penalty: float = 0.0      # Cost penalty per startup (€ per start)
    priority: int = 5                 # 1-10, lower = higher priority for manual triage
```

**Design note:** `earliest_start_time` and `latest_end_time` are stored as time-of-day strings (e.g., "08:00", "22:00") which is what the user thinks in. The translation layer converts these to EMHASS's relative timestep indices at optimisation time based on the current time and the optimisation time step.

### 6.2 `OptimizationConfig`

```python
@dataclass
class OptimizationConfig:
    # Connection
    emhass_url: str = 'http://localhost:5000'
    emhass_entity_prefix: str = ''    # Prefix for EMHASS result entities (empty = default)

    # Global settings
    enabled: bool = False
    cost_function: str = 'profit'         # profit / cost / self-consumption
    optimization_mode: str = 'dayahead_mpc'  # dayahead / mpc / dayahead_mpc
    optimization_time_step: int = 30      # minutes (must match EMHASS config)

    # Day-ahead settings
    dayahead_schedule_time: str = '05:30' # HH:MM when daily optimization runs
    forecast_horizon_hours: int = 24      # hours to forecast ahead

    # MPC settings
    mpc_frequency_minutes: int = 30       # how often MPC runs
    mpc_prediction_horizon: int = 10      # timesteps for MPC prediction

    # Grid constraints
    max_grid_import_w: int = 9000         # max Watts from grid
    max_grid_export_w: int = 9000         # max Watts to grid

    # Battery optimization
    optimize_battery: bool = False
    battery_min_soc: float = 0.2          # 0.0-1.0
    battery_max_soc: float = 0.9
    battery_target_soc: float = 0.6
    allow_grid_charging: bool = True      # Can battery charge from grid?
    allow_grid_discharge: bool = False    # Can battery discharge to grid?

    # Solar settings (auto-populated from solar panels config, not shown in UI)
    optimize_pv: bool = False
    pv_power_sensor: str = ''             # HA entity for solar power (W)

    # Load sensor
    load_power_sensor: str = ''           # HA entity for total load minus deferrable loads (W)

    # Actuation mode
    actuation_mode: str = 'manual'        # manual / notify / automatic
    auto_actuate: bool = False            # Deprecated alias for actuation_mode == 'automatic'

    # Deferrable loads (ordered list, order = EMHASS index)
    deferrable_loads: List[DeferrableLoadConfig] = field(default_factory=list)

    # Override state
    active_overrides: Dict[str, DeviceOverride] = field(default_factory=dict)

    # MPC run tracking
    device_run_tracking: Dict[str, float] = field(default_factory=dict)  # device_id -> hours already run today
    last_tracking_reset: datetime = None  # Reset at midnight or dayahead time

    # Metadata
    last_optimization_run: datetime = None
    last_optimization_status: str = ''
    last_updated: datetime = field(default_factory=datetime.now)
```

### 6.3 `DeviceOverride`

```python
@dataclass
class DeviceOverride:
    device_id: str
    override_type: str        # 'force_on' / 'force_off' / 'skip_next'
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = None  # Auto-expire overrides
    reason: str = ''          # User-provided reason (optional)
```

### 6.4 `OptimizationResult`

```python
@dataclass
class OptimizationResult:
    timestamp: datetime                   # When the optimization was computed
    optimization_type: str                # 'dayahead' / 'mpc'
    cost_function: str                    # 'profit' / 'cost' / 'self-consumption'
    time_step_minutes: int

    # Per-timestep forecasts
    pv_forecast: List[TimeseriesPoint] = field(default_factory=list)
    load_forecast: List[TimeseriesPoint] = field(default_factory=list)
    grid_forecast: List[TimeseriesPoint] = field(default_factory=list)        # positive = import, negative = export
    battery_soc_forecast: List[TimeseriesPoint] = field(default_factory=list)
    battery_power_forecast: List[TimeseriesPoint] = field(default_factory=list)  # positive = discharge, negative = charge

    # Per-device schedules
    device_schedules: Dict[str, DeviceSchedule] = field(default_factory=dict)  # device_id -> schedule

    # Summary
    total_cost_eur: float = 0.0
    total_grid_import_kwh: float = 0.0
    total_grid_export_kwh: float = 0.0
    total_pv_production_kwh: float = 0.0
    total_self_consumption_kwh: float = 0.0

@dataclass
class TimeseriesPoint:
    timestamp: datetime
    value: float

@dataclass
class DeviceSchedule:
    device_id: str
    device_name: str
    schedule_entries: List[ScheduleEntry] = field(default_factory=list)
    total_energy_kwh: float = 0.0

@dataclass
class ScheduleEntry:
    start_time: datetime
    end_time: datetime
    power_w: float
    is_active: bool
```

---

## 7. Optimizer Abstraction Layer

### 7.1 `OptimizerConnector` (in `web/model/optimization/connector.py`)

```python
from abc import ABC, abstractmethod

class OptimizerConnector(ABC):

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the optimization backend is reachable"""
        pass

    @abstractmethod
    def run_dayahead_optimization(self, config: OptimizationConfig) -> OptimizationResult:
        """Run a day-ahead optimization and return results"""
        pass

    @abstractmethod
    def run_mpc_optimization(self, config: OptimizationConfig,
                            current_battery_soc: float = None) -> OptimizationResult:
        """Run an MPC optimization iteration and return results"""
        pass

    @abstractmethod
    def get_latest_result(self) -> Optional[OptimizationResult]:
        """Retrieve the most recent optimization result"""
        pass
```

### 7.2 `EmhassConnector` (in `web/model/optimization/emhass_connector.py`)

Concrete implementation. Primary responsibilities:

1. **Parameter Assembly:** Convert `OptimizationConfig` + `DeferrableLoadConfig[]` into EMHASS's `runtimeparams` JSON
2. **API Communication:** POST to EMHASS endpoints and parse responses
3. **Result Parsing:** Read EMHASS result entities from HA and convert to `OptimizationResult`
4. **Cost Forecast Generation:** Use GridMate's `EnergyContract` to generate per-timestep cost arrays
5. **Unit Conversion:** Centralise kW↔W conversion

```python
class EmhassConnector(OptimizerConnector):

    def __init__(self, emhass_url: str, ha_connector: HAConnector,
                 data_connector: DataConnector):
        self.emhass_url = emhass_url
        self.ha = ha_connector
        self.data = data_connector

    # --- Unit conversion (centralised) ---

    def _kw_to_w(self, kw: float) -> float:
        return kw * 1000.0

    def _w_to_kw(self, w: float) -> float:
        return w / 1000.0

    # --- Connectivity ---

    def is_available(self) -> bool:
        """GET {emhass_url}/ and check for 200"""

    # --- Parameter assembly ---

    def _build_runtime_params(self, config: OptimizationConfig,
                               optimization_type: str,
                               current_battery_soc: float = None) -> dict:
        """
        Translate GridMate config into EMHASS runtimeparams dict.
        This is the core translation function. All power values
        are converted from kW to W here.
        """

    def _build_cost_forecast(self, config: OptimizationConfig) -> List[float]:
        """
        Generate load_cost_forecast from GridMate's EnergyContract.
        See section 8 for the full algorithm.
        """

    def _build_production_price_forecast(self, config: OptimizationConfig) -> List[float]:
        """
        Generate prod_price_forecast from GridMate's EnergyContract.
        See section 8 for the full algorithm.
        """

    def _time_to_timestep_index(self, time_str: str, opt_start: datetime,
                                 time_step_min: int, horizon_steps: int,
                                 is_end: bool = False) -> int:
        """
        Convert a HH:MM time string to EMHASS's relative timestep index.
        See section 7.3 for edge case handling.
        """

    # --- Result parsing ---

    def _parse_emhass_response(self, response_data: dict,
                                config: OptimizationConfig) -> OptimizationResult:
        """Parse EMHASS optimization results into vendor-agnostic format.
        All power values are converted from W to kW here."""

    def _read_result_entities(self, config: OptimizationConfig) -> OptimizationResult:
        """
        Read EMHASS result entities from HA and build OptimizationResult.
        Entity names respect the configured emhass_entity_prefix.
        """

    # --- Optimization calls ---

    def run_dayahead_optimization(self, config: OptimizationConfig) -> OptimizationResult:
        """POST to /action/dayahead-optim with assembled runtimeparams"""

    def run_mpc_optimization(self, config: OptimizationConfig,
                            current_battery_soc: float = None) -> OptimizationResult:
        """POST to /action/naive-mpc-optim with assembled runtimeparams"""

    # --- Config generation ---

    def generate_emhass_config(self, config: OptimizationConfig) -> dict:
        """
        Generate an EMHASS config.json from GridMate's current settings.
        Reuses existing solar config (solar sensor), battery settings, and
        device data so users don't have to re-configure things they
        already set up elsewhere. Users can copy this into their EMHASS
        config, or it can be applied directly if EMHASS supports it.
        """
```

### 7.3 Time Window Conversion

Converting HH:MM strings to EMHASS timestep indices requires careful edge-case handling:

- If `earliest_start_time` is before the optimisation start time → use index 0
- If `latest_end_time` extends past the forecast horizon → use the last index
- If the window is overnight (e.g., start at 22:00, end at 06:00) → the target is pushed to the next day

```python
def _time_to_timestep_index(self, time_str: str, opt_start: datetime,
                             time_step_min: int, horizon_steps: int,
                             is_end: bool = False) -> int:
    if not time_str:
        return 0 if not is_end else 0  # 0 = no constraint in EMHASS

    hour, minute = map(int, time_str.split(':'))
    target = opt_start.replace(hour=hour, minute=minute, second=0)

    # Handle next-day times (e.g., end at 06:00 when optimization starts at 22:00)
    if target < opt_start:
        target += timedelta(days=1)

    delta_minutes = (target - opt_start).total_seconds() / 60
    index = int(delta_minutes / time_step_min)

    # Clamp to valid range
    return max(0, min(index, horizon_steps))
```

---

## 8. Cost Forecast Generation

This is one of the most impactful features: it lets EMHASS make truly optimal decisions based on the user's actual energy contract. EMHASS needs two cost arrays:

- `load_cost_forecast`: list of electricity prices in €/kWh for each timestep
- `prod_price_forecast`: list of production sell prices in €/kWh for each timestep

GridMate already has a rich `EnergyContract` model with `VariableComponent`, `FixedComponent`, `ConstantComponent`, `CapacityComponent`, and `PercentageComponent`.

### 8.0 PV Power Forecast Generation

`SolarForecastService` (in `web/model/optimization/solar_forecast.py`) builds the `pv_power_forecast` runtime parameter using naive persistence:

1. Reads the `estimated_actual_production_offset_day` sensor from the solar estimation config — this is the Forecast.Solar "Estimated Power Production - Next 24 Hours" sensor, whose state at any time T represents the predicted power (kW) at T+24h
2. Fetches 24 hours of history for this sensor via `ha_connector.get_history()` with `significant_changes_only=False` to capture all state changes
3. For each optimization timestep, finds the closest historical point 24h before the target time and uses its value as the forecast
4. Converts from kW (sensor unit) to W (EMHASS unit) by multiplying by 1000

**Timezone handling:** Timestamps from HA history (typically UTC with timezone info) are converted to local naive datetimes using `datetime.astimezone(tz=None)` before processing.

**All-zero filtering:** If the resulting forecast contains only zero values (e.g. no solar data in history), it is discarded.

If no forecast is produced, an empty list is returned and EMHASS falls back to its internal weather-based forecast method (open-meteo). There is intentionally no application-level fallback — EMHASS's built-in forecaster (using configured PV system parameters and weather data) produces more accurate results than any simplified approximation.

### 8.1 Component Treatment

EMHASS only needs the **marginal cost** of consuming/producing one additional kWh at each point in time:

| Component Type | Treatment | Rationale |
|---|---|---|
| `ConstantComponent` (fixed monthly fees) | **Excluded** | Does not affect marginal cost per kWh |
| `FixedComponent` (per-kWh) | **Included** directly | Directly adds to marginal cost |
| `VariableComponent` (dynamic pricing) | **Included** with time-resolved values | Core of time-varying cost |
| `PercentageComponent` (VAT) | **Applied as multiplier** to per-kWh costs | Scales the marginal cost proportionally |
| `CapacityComponent` (capacity tariff) | **Included** as marginal peak penalty | See section 8.4 |

### 8.2 Algorithm for `load_cost_forecast`

1. Determine the optimisation window: `start_time` to `start_time + forecast_horizon_hours`
2. Generate timestamps at `optimization_time_step` intervals
3. For each timestamp:
   a. If the contract has a `VariableComponent` for consumption with a price sensor:
      - Read the price sensor's forecast value from HA for that timestamp (see section 8.3)
      - Apply the formula: `effective_price = (sensor_value × variable_price_multiplier) + variable_price_constant`
   b. Add all `FixedComponent` prices for consumption: sum their `fixed_price` values
   c. Add the capacity tariff marginal cost if applicable (see section 8.4)
   d. Apply `PercentageComponent` (VAT): multiply by `(1 + percentage / 100)`
4. Return as a flat list of floats

### 8.3 Price Forecast Sensor Handling

Users configure a price forecast sensor (e.g., the Nord Pool integration). The system must not be locked into any specific vendor — any sensor that provides pricing data works. The key requirements:

- **Sensor-based:** Users configure their forecast sensor entity in GridMate; no direct integration with any specific pricing API
- **Forecast attribute:** Many pricing integrations (like Nord Pool) expose a `forecast` attribute on their sensor with future prices. GridMate reads this attribute to build the time-resolved cost array
  - Reference: Home Assistant Nord Pool integration provides a `get_price_for_date` mechanism and forecast data through sensor attributes
- **Fallback:** If the user has not configured a forecast sensor, or the sensor does not provide forecast data for the requested timestep, use `P(t) = P(t - 24h)` — i.e., use the price from 24 hours ago as the prediction. This provides a reasonable baseline without requiring any special configuration
- **Other vendors:** The architecture assumes other pricing vendors will provide similar sensor APIs to Nord Pool. The sensor-based approach ensures vendor independence

### 8.4 Capacity Tariff (CapacityComponent) in Cost Forecast

The `CapacityComponent` represents a capacity tariff — a cost based on the peak 15-minute power draw in a billing period. This can and should be included in the optimisation cost forecast as a marginal peak penalty.

**Algorithm:**

1. Fetch the current peak 15-minute power for the current billing period (this data is already available in the costs dashboard)
2. For each timestep, estimate whether the sum of scheduled loads could cause a new peak
3. If any 15-minute window exceeds the current peak, add the marginal cost: `(new_peak - current_peak) × capacity_price_per_kw`
4. Keep the period definition in mind (monthly/yearly as defined by the `CapacityComponent`)

**Example:** If the current monthly peak is 3 kW and the optimiser schedules a window at 4 kW, the marginal cost is `1 kW × capacity_price_multiplier`.

### 8.5 Algorithm for `prod_price_forecast`

1. Same timestep generation as `load_cost_forecast`
2. For each timestamp:
   a. If the contract has a `VariableComponent` marked `is_injection_reward`: read price sensor value, apply formula
   b. Add `FixedComponent` injection reward prices
   c. Apply `PercentageComponent` (VAT) if applicable
3. Return as a flat list of floats

### 8.6 Concrete Example (Belgian Market)

Given a contract with:
- `VariableComponent` "Energieprijs" with `sensor.nord_pool_be_daily_average`, multiplier 1.0429, constant 0.0745
- `FixedComponent` "Bijzondere accijns" at 0.050329 €/kWh
- `FixedComponent` "Bijdrage op de Energie" at 0.002042 €/kWh
- `FixedComponent` "Afnametarief normaal" at 0.0747 €/kWh
- `PercentageComponent` "BTW" at 6%

Per-timestep marginal cost = `((nordpool_price × 1.0429 + 0.0745) + 0.050329 + 0.002042 + 0.0747) × 1.06`

---

## 9. Optimization Scheduler Service

### 9.1 `OptimizationScheduler` (in `web/model/optimization/scheduler.py`)

This service manages the automated optimisation cycle. It is triggered by Flask route calls that are invoked by Home Assistant automations — GridMate runs as a web server, not a daemon, so leveraging HA's scheduling system keeps the architecture simple.

```python
class OptimizationScheduler:

    def __init__(self, connector: OptimizerConnector, data_connector: DataConnector,
                 ha_connector: HAConnector):
        self.connector = connector
        self.data = data_connector
        self.ha = ha_connector
        self.result_store = OptimizationResultStore(data_connector)

    def run_scheduled_optimization(self, force_type: str = None) -> OptimizationResult:
        """
        Run optimization based on current config and time.
        Called by the /api/optimization/run endpoint.

        Args:
            force_type: 'dayahead' or 'mpc' to force a specific type,
                       None to auto-determine based on config and time.
        """
        config = self.data.get_optimization_config()

        if not config.enabled:
            raise OptimizationDisabledError()

        if not self.connector.is_available():
            raise OptimizerUnavailableError()

        # Apply active overrides to config before running
        effective_config = self._apply_overrides(config)

        # Determine optimization type
        opt_type = force_type or self._determine_optimization_type(config)

        # For MPC: adjust parameters for shrinking horizon
        if opt_type == 'mpc':
            effective_config = self._prepare_mpc_params(effective_config)

        # Get current battery SOC if battery is configured
        current_soc = self._get_current_battery_soc(config) if config.optimize_battery else None

        # Run optimization
        if opt_type == 'dayahead':
            result = self.connector.run_dayahead_optimization(effective_config)
            # Reset run tracking on day-ahead run
            config.device_run_tracking = {}
            config.last_tracking_reset = datetime.now()
        else:
            result = self.connector.run_mpc_optimization(effective_config, current_soc)

        # Store result
        self.result_store.save_result(result)

        # Actuate devices based on actuation_mode
        if config.actuation_mode == 'automatic':
            self._actuate_devices(result, config)
        elif config.actuation_mode == 'notify':
            self._send_notifications(result, config)

        # Update config metadata
        config.last_optimization_run = datetime.now()
        config.last_optimization_status = 'success'
        self.data.set_optimization_config(config)

        return result

    def _apply_overrides(self, config: OptimizationConfig) -> OptimizationConfig:
        """
        Apply user overrides: remove force_off devices from deferrable loads,
        keep force_on devices as mandatory.
        """

    def _prepare_mpc_params(self, config: OptimizationConfig) -> OptimizationConfig:
        """
        Adjust MPC parameters for shrinking horizon:
        1. Read current deferrable load states from HA (are they on or off?)
        2. Calculate remaining operating hours = configured hours - hours already run today
        3. Calculate remaining prediction horizon = end of day - now
        4. Set def_current_state as a list of booleans
        5. Adjust operating_hours_of_each_deferrable_load to remaining hours
        """

    def _get_current_battery_soc(self, config: OptimizationConfig) -> float:
        """Read current battery SOC from HA entity"""

    def _actuate_devices(self, result: OptimizationResult, config: OptimizationConfig):
        """
        Send control commands to HA for devices that should change state NOW.
        Only actuates for the current timestep.
        Uses the device's control_entity (from automatable_device type).

        Safety checks before actuation:
        1. Device state coherence — don't send "turn on" if device is already on
        2. Override precedence — user overrides always take priority
        3. Graceful failure — log errors, continue with other devices, surface on dashboard
        """

    def _send_notifications(self, result: OptimizationResult, config: OptimizationConfig):
        """Create HA notifications for scheduled device actions without actuating"""
```

### 9.2 Device Actuation Safety

Before actuating any device, GridMate must check:

1. **Device state coherence:** Don't send "turn on" if device is already on (verified via HA entity state)
2. **Override precedence:** User overrides always take priority over optimisation
3. **Graceful failure:** If a device control command fails, log the error, continue with other devices, and surface the error on the dashboard

**Actuation mode** (global setting):
| Mode | Behaviour |
|---|---|
| `manual` (default) | GridMate shows the schedule but never actuates devices |
| `notify` | GridMate creates HA notifications for scheduled actions but doesn't actuate |
| `automatic` | GridMate directly controls devices via HA entity control |

Default is `manual` to prevent unexpected device control on first setup.

### 9.3 `OptimizationResultStore` (in `web/model/optimization/result_store.py`)

```python
class OptimizationResultStore:

    def __init__(self, data_connector: DataConnector):
        self.data = data_connector

    def save_result(self, result: OptimizationResult) -> None:
        """Save the latest optimization result to data/optimization_latest.json"""

    def get_latest_result(self) -> Optional[OptimizationResult]:
        """Get the most recent optimization result"""

    def get_result_history(self, days: int = 7) -> List[OptimizationResult]:
        """Get historical results for comparison"""
```

**Storage strategy:**
- Latest result: `data/optimization_latest.json` (separate from `settings.json` to avoid bloat)
- Historical results: `data/optimization_history/` directory, one JSON file per day
- Retention: keep only the last N days to manage disk usage

---

## 10. EMHASS Configuration Sync

GridMate generates the EMHASS base config from its own data so users don't need to configure things twice. Values like `sensor_power_photovoltaics` are auto-populated from existing solar config; `number_of_deferrable_loads` comes from the device list.

### 10.1 Config Generation

The settings page includes a **"Generate EMHASS Config"** button that produces a ready-to-use `config.json` for the EMHASS add-on, pre-filled from GridMate's existing configuration. Users can copy-paste this into their EMHASS configuration.

### 10.2 Config Validation

A **"Sync Configuration"** button validates that EMHASS's base config is consistent with GridMate's expectations:

```python
class EmhassConfigValidator:
    def validate(self, gridmate_config: OptimizationConfig,
                 emhass_config: dict) -> List[ConfigWarning]:
        warnings = []

        # Check number of deferrable loads matches
        gm_loads = len(gridmate_config.deferrable_loads)
        em_loads = emhass_config.get('number_of_deferrable_loads', 0)
        if gm_loads != em_loads:
            warnings.append(ConfigWarning(
                'MISMATCH',
                f'GridMate has {gm_loads} deferrable loads but EMHASS expects {em_loads}. '
                f'Update EMHASS config: number_of_deferrable_loads = {gm_loads}'
            ))

        # Check time step matches
        gm_step = gridmate_config.optimization_time_step
        em_step = emhass_config.get('optimization_time_step', 30)
        if gm_step != em_step:
            warnings.append(ConfigWarning(
                'MISMATCH',
                f'Time step mismatch: GridMate={gm_step}min, EMHASS={em_step}min'
            ))

        # Check battery enabled matches
        if gridmate_config.optimize_battery != emhass_config.get('set_use_battery', False):
            warnings.append(ConfigWarning(
                'MISMATCH',
                'Battery optimization setting differs between GridMate and EMHASS'
            ))

        return warnings
```

If EMHASS exposes its current config via API, GridMate reads it for validation. Otherwise, the user can manually trigger a sync check.

---

## 11. API Endpoints

### 11.1 Settings Routes (in `web/routes/settings/optimization.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/settings/optimization` | Optimization settings page |
| GET/POST | `/settings/optimization/devices` | Configure which devices participate |
| GET | `/settings/optimization/setup` | Setup wizard (step-by-step) |
| POST | `/api/optimization/device/<device_id>/toggle` | Enable/disable a device |

### 11.2 Dashboard Routes (in `web/routes/dashboards/optimization.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard/optimization` | Main optimization dashboard |
| GET | `/api/optimization/status` | JSON: current optimization status |
| GET | `/api/optimization/schedule` | JSON: current schedule data for charts |
| POST | `/api/optimization/run` | Trigger optimization now |
| POST | `/api/optimization/override/<device_id>` | Set device override (force on/off/skip) |
| DELETE | `/api/optimization/override/<device_id>` | Clear device override |

### 11.3 EMHASS Proxy Routes (diagnostics)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/optimization/emhass/status` | Check EMHASS connectivity |
| GET | `/api/optimization/emhass/config` | View effective EMHASS config (read-only) |
| GET | `/api/optimization/emhass/generated-config` | Generated EMHASS config from GridMate data |

---

## 12. UI Specifications

### 12.1 Optimization Settings Page (`/settings/optimization`)

**Layout:** Form-based settings page, consistent with existing GridMate settings pages.

**Sections:**

1. **EMHASS Connection**
   - URL field (text input, default: `http://localhost:5000`)
   - Entity prefix field (text input, default: empty)
   - Connection status indicator (green/red dot)
   - "Test Connection" button
   - "Generate EMHASS Config" button (produces config.json for copy-paste)
   - "Sync & Validate" button (checks consistency with EMHASS)

2. **Optimization Mode**
   - Enable/disable toggle (master switch)
   - Cost function selector (radio buttons): Profit / Cost / Self-Consumption (with tooltips)
   - Mode selector (radio buttons): Day-Ahead Only / MPC Only / Day-Ahead + MPC (recommended)

3. **Schedule Configuration**
   - Day-ahead run time (time picker, default: 05:30)
   - MPC frequency (dropdown: 5/15/30/60 min)
   - Time step (dropdown: 15/30/60 min — must match EMHASS config)
   - Forecast horizon (dropdown: 12/24/48 hours)

4. **Grid Constraints**
   - Max import power (number input, W)
   - Max export power (number input, W)

5. **Battery Optimization** (only shown if a `home_battery` device exists)
   - Enable battery optimisation toggle
   - Min SOC slider (0-100%)
   - Max SOC slider (0-100%)
   - Target SOC slider (0-100%)
   - Allow grid charging checkbox
   - Allow grid discharge checkbox

6. **Load Sensor Configuration**
   - Total household load sensor entity picker (in EMHASS Connection section)
   - Solar sensor auto-populated from solar panels config (shown as info banner, not editable here)
   - Info box explaining the `sensor_power_load_no_var_loads` requirement

7. **Actuation Mode**
   - Radio buttons: Manual / Notify / Automatic
   - Warning text for Automatic mode

8. **Advanced** (collapsible)
   - Solver timeout (seconds)
   - Debug mode toggle

### 12.2 Device Optimization Configuration

Device-level optimisation settings are integrated into the existing device edit form (`/settings/edit-device/<device_id>`). When a device has the `deferrable_load` secondary type, additional fields appear for:

| Parameter | Label | Type | Unit |
|---|---|---|---|
| `opt_enabled` | Optimization Enabled | bool | — |
| `opt_nominal_power` | Nominal Power | float | W |
| `opt_duration_hours` | Operating Duration | float | hours |
| `opt_constant_power` | Constant Power | bool | — |
| `opt_continuous_operation` | Continuous Operation | bool | — |
| `opt_earliest_start` | Earliest Start Time | string (HH:MM) | — |
| `opt_latest_end` | Latest End Time | string (HH:MM) | — |
| `opt_startup_penalty` | Startup Penalty | float | € |
| `opt_priority` | Priority | int (1-10) | — |

### 12.3 Optimization Dashboard (`/dashboard/optimization`)

**Layout:** Full-width dashboard with multiple visualisation panels.

**Components:**

1. **Status Bar** (top)
   - Optimisation status: Enabled/Disabled, Last Run time, Next Run time
   - EMHASS connection status
   - "Run Now" button (primary action)
   - Current cost function badge

2. **Schedule Timeline** (main area)
   - Horizontal Gantt-chart style timeline showing 24 hours
   - Each deferrable load gets a coloured row
   - Blocks show when each device is scheduled to run
   - Current time marker (vertical line)
   - Battery SOC overlaid as a line chart
   - Interactive: clicking a device block opens override options

3. **Power Flow Forecast** (below timeline)
   - Stacked area chart showing:
     - Solar production (yellow/orange)
     - Load consumption (grey)
     - Grid import (red)
     - Grid export (green)
     - Battery charge/discharge (blue)
   - 24-hour x-axis, kW y-axis

4. **Summary Cards** (side panel or below)
   - Estimated cost today: €X.XX
   - Estimated savings vs. no optimisation: €X.XX
   - Self-consumption rate: XX%
   - Grid independence today: XX%
   - Next device activation: "Boiler at 14:30"

5. **Device Schedule Cards** (bottom)
   - One card per deferrable load device
   - Shows: device name, scheduled time window, power, status (waiting/running/completed)
   - Override button: "Force On Now" / "Force Off" / "Skip Today"
   - Visual status indicator (icon + colour)

### 12.4 Manual Override UX

When a user clicks "Force On Now" for a device:
1. A confirmation modal appears: "Force [Device Name] on now? This overrides the optimization schedule."
2. User can set an expiry: "Until manually cancelled" / "For X hours" / "Until next optimization run"
3. GridMate immediately sends the control command to HA (via `control_entity`)
4. The override is recorded and excluded from the next MPC run
5. The dashboard shows the device as "Manually Active" with a distinct visual style

### 12.5 Initial Setup Wizard (`/settings/optimization/setup`)

A guided wizard reduces the barrier to entry:

**Step 1: EMHASS Connection**
- Enter EMHASS URL
- Test connection
- If connected, read EMHASS's current config to pre-populate GridMate fields

**Step 2: Cost Configuration**
- Auto-detect: "You have a Variable energy contract component using [sensor name]. Use this for optimization cost forecasts?" → Yes/No
- Choose cost function (with clear explanations)

**Step 3: Device Selection**
- Show all devices with `automatable_device` type
- Checkboxes to select which should be optimised
- For each selected device, prompt for nominal power and duration

**Step 4: Battery** (conditional)
- If `home_battery` device exists: "Include your home battery in optimization?" → Yes/No
- Pre-populate from existing battery settings

**Step 5: Review & Activate**
- Summary of all settings
- "Activate Optimization" button
- Provides the HA automation YAML to copy-paste
- Provides the generated EMHASS `config.json` to copy-paste

The wizard stores partial progress in the session.

---

## 13. Persistence

### 13.1 Settings JSON Structure

The existing `optimization` key in `settings.json` (currently `{}`) is expanded:

```json
{
  "optimization": {
    "emhass_url": "http://localhost:5000",
    "emhass_entity_prefix": "",
    "enabled": false,
    "cost_function": "profit",
    "optimization_mode": "dayahead_mpc",
    "optimization_time_step": 30,
    "dayahead_schedule_time": "05:30",
    "forecast_horizon_hours": 24,
    "mpc_frequency_minutes": 30,
    "mpc_prediction_horizon": 10,
    "max_grid_import_w": 9000,
    "max_grid_export_w": 9000,
    "optimize_battery": false,
    "battery_min_soc": 0.2,
    "battery_max_soc": 0.9,
    "battery_target_soc": 0.6,
    "allow_grid_charging": true,
    "allow_grid_discharge": false,
    "optimize_pv": false,
    "pv_power_sensor": "",
    "load_power_sensor": "",
    "actuation_mode": "manual",
    "active_overrides": {},
    "device_run_tracking": {},
    "last_tracking_reset": null,
    "last_optimization_run": null,
    "last_optimization_status": "",
    "last_updated": "2026-03-01T00:00:00"
  }
}
```

### 13.2 Optimization Result Storage

Stored separately to avoid bloating `settings.json`:

- **File:** `data/optimization_latest.json`
- **Content:** Serialised `OptimizationResult` with full timeseries data
- **Updated:** After every successful optimisation run
- **Size management:** Only the latest result in this file. Daily summaries logged to `data/optimization_history/` (one file per day, last N days retained).

---

## 14. DataConnector Extensions

### 14.1 New Methods on `DataConnector`

```python
# Optimization Config
def get_optimization_config(self) -> OptimizationConfig
def set_optimization_config(self, config: OptimizationConfig) -> None
def update_optimization_config(self, updates: Dict) -> None

# Optimization Results (stored in separate file)
def get_latest_optimization_result(self) -> Optional[OptimizationResult]
def save_optimization_result(self, result: OptimizationResult) -> None
```

### 14.2 `OptimizationManager`

```python
class OptimizationManager:
    def __init__(self, connector: DataConnector):
        self.connector = connector

    def get_config(self) -> OptimizationConfig
    def save_config(self, config: OptimizationConfig) -> None

    def get_deferrable_loads(self) -> List[DeferrableLoadConfig]:
        """
        Build DeferrableLoadConfig list from devices that have
        the 'deferrable_load' secondary type and opt_enabled=True.
        Ordered by opt_priority (ascending).
        """

    def set_override(self, device_id: str, override: DeviceOverride) -> None
    def clear_override(self, device_id: str) -> None
    def clear_expired_overrides(self) -> None

    def get_latest_result(self) -> Optional[OptimizationResult]
    def get_device_schedule(self, device_id: str) -> Optional[DeviceSchedule]
```

---

## 15. Forms

### 15.1 `OptimizationSettingsForm`

Replaces the existing basic `EnergyOptimizationForm` in `web/forms/optimization.py`:

```python
class OptimizationSettingsForm(FlaskForm):
    # Connection
    emhass_url = StringField('EMHASS URL', default='http://localhost:5000')
    emhass_entity_prefix = StringField('Entity Prefix', default='')

    # Global
    enabled = BooleanField('Enable Optimization')
    cost_function = SelectField('Cost Function', choices=[
        ('profit', 'Maximize Profit'),
        ('cost', 'Minimize Grid Cost'),
        ('self-consumption', 'Maximize Self-Consumption'),
    ])
    optimization_mode = SelectField('Optimization Mode', choices=[
        ('dayahead', 'Day-Ahead Only'),
        ('mpc', 'MPC Only'),
        ('dayahead_mpc', 'Day-Ahead + MPC (Recommended)'),
    ])
    optimization_time_step = SelectField('Time Step', choices=[
        ('15', '15 minutes'), ('30', '30 minutes'), ('60', '60 minutes'),
    ])

    # Day-ahead
    dayahead_schedule_time = StringField('Day-Ahead Run Time', default='05:30')
    forecast_horizon_hours = SelectField('Forecast Horizon', choices=[
        ('12', '12 hours'), ('24', '24 hours'), ('48', '48 hours'),
    ])

    # MPC
    mpc_frequency_minutes = SelectField('MPC Frequency', choices=[
        ('5', 'Every 5 minutes'), ('15', 'Every 15 minutes'),
        ('30', 'Every 30 minutes'), ('60', 'Every hour'),
    ])

    # Grid
    max_grid_import_w = IntegerField('Max Grid Import (W)', default=9000)
    max_grid_export_w = IntegerField('Max Grid Export (W)', default=9000)

    # Battery
    optimize_battery = BooleanField('Optimize Battery')
    battery_min_soc = IntegerField('Min SOC (%)', default=20)
    battery_max_soc = IntegerField('Max SOC (%)', default=90)
    battery_target_soc = IntegerField('Target SOC (%)', default=60)
    allow_grid_charging = BooleanField('Allow Grid Charging', default=True)
    allow_grid_discharge = BooleanField('Allow Grid Discharge')

    # Sensors (pv_power_sensor removed from form — auto-populated from solar config)
    load_power_sensor = StringField('Load Power Sensor')

    # Actuation
    actuation_mode = SelectField('Actuation Mode', choices=[
        ('manual', 'Manual — show schedule only'),
        ('notify', 'Notify — send HA notifications'),
        ('automatic', 'Automatic — control devices directly'),
    ])

    submit = SubmitField('Save Settings')
```

---

## 16. Templates & Static Assets

### New templates:

```
web/templates/
  dashboard/
    optimization.html              # Main optimization dashboard
  settings/
    optimization/
      settings.html                # Optimization settings page
      setup.html                   # Setup wizard
```

### New static assets:

```
web/static/
  css/
    dashboard/
      optimization.css             # Dashboard styles
  js/
    optimization-dashboard.js      # Timeline chart, power flow chart, override UX
    optimization-settings.js       # Settings form interactivity
```

---

## 17. Navigation & Blueprint Registration

### 17.1 Navigation Updates

Add new entries to `layout.html` navigation:

**Dashboard submenu:**
- Add "Optimization" link → `/dashboard/optimization`

**Settings submenu:**
- Add "Optimization" link → `/settings/optimization`

### 17.2 Blueprint Registration

Update `web/routes/routes.py`:

```python
from web.routes.settings.optimization import settings_optimization_bp
from web.routes.dashboards.optimization import dashboard_optimization_bp

def register_blueprints(app):
    # ... existing blueprints ...
    app.register_blueprint(settings_optimization_bp)
    app.register_blueprint(dashboard_optimization_bp)
```

---

## 18. Home Assistant Automation Integration

GridMate does NOT implement its own scheduler daemon. Instead, users create HA automations that call GridMate's API at scheduled times. This keeps the architecture simple and leverages HA's robust scheduling system.

```yaml
# Example HA automation: Day-ahead optimization at 05:30
automation:
  - alias: "GridMate Day-Ahead Optimization"
    trigger:
      - platform: time
        at: "05:30:00"
    action:
      - service: rest_command.gridmate_run_dayahead

  - alias: "GridMate MPC Optimization"
    trigger:
      - platform: time_pattern
        minutes: "/30"
    action:
      - service: rest_command.gridmate_run_mpc

rest_command:
  gridmate_run_dayahead:
    url: "http://localhost:8000/api/optimization/run"
    method: POST
    content_type: "application/json"
    payload: '{"type": "dayahead"}'

  gridmate_run_mpc:
    url: "http://localhost:8000/api/optimization/run"
    method: POST
    content_type: "application/json"
    payload: '{"type": "mpc"}'
```

The setup wizard generates this YAML for users to copy-paste into their HA configuration.

**Future consideration:** A background APScheduler thread inside Flask could be revisited if users find HA automation setup burdensome.

---

## 19. File Structure Summary

### New files to create:

```
web/
  model/
    optimization/
      __init__.py
      models.py              # DeferrableLoadConfig, OptimizationConfig, DeviceOverride,
                              # OptimizationResult, DeviceSchedule, etc.
      connector.py            # OptimizerConnector ABC
      emhass_connector.py     # EmhassConnector implementation
      scheduler.py            # OptimizationScheduler service
      result_store.py         # OptimizationResultStore
      config_validator.py     # EmhassConfigValidator
      solar_forecast.py       # SolarForecastService — PV power forecast generation
      cost_forecast.py        # CostForecastService — load cost and production price forecasts
  routes/
    settings/
      optimization.py         # Settings routes + setup wizard
    dashboards/
      optimization.py         # Dashboard routes
    api/
      optimization.py         # API endpoints
  forms/
    optimization.py           # (EXISTING — extend/replace)
  templates/
    dashboard/
      optimization.html
    settings/
      optimization/
        settings.html
        setup.html
  static/
    css/
      dashboard/
        optimization.css
    js/
      optimization-dashboard.js
      optimization-settings.js
```

### Modified files:

```
web/model/device/device_types.py          # Add deferrable_load device type
web/model/energy/models.py            # Remove old Optimization class
web/model/data/data_connector.py      # Add optimization config/result methods
web/routes/routes.py                  # Register new blueprints
web/templates/layout.html             # Add navigation entries
data/settings.json                    # Extended optimization section
```

---

## 20. Implementation Phases

### Phase 1: Foundation (Estimated: 2-3 weeks)
1. Create `web/model/optimization/` module with all domain models
2. Implement `OptimizerConnector` ABC and `EmhassConnector`
3. Add `deferrable_load` device type to defaults
4. Implement `OptimizationConfig` persistence in `DataConnector`
5. Remove old `Optimization` class from `web/model/energy/models.py`
6. Create settings page for optimisation configuration
7. Implement cost forecast generation from `EnergyContract` (including capacity tariff)

### Phase 2: Core Optimization Loop (Estimated: 2-3 weeks)
1. Implement `OptimizationScheduler` with day-ahead and MPC support (including shrinking horizon tracking)
2. Implement result parsing and `OptimizationResultStore`
3. Create API endpoints for triggering optimisation and retrieving results
4. Implement device override logic
5. Create HA automation templates for scheduling
6. Implement EMHASS config generation and validation

### Phase 3: Dashboard (Estimated: 2-3 weeks)
1. Build optimisation dashboard template
2. Implement timeline/Gantt chart with Chart.js
3. Implement power flow forecast chart
4. Build summary cards
5. Implement override UX (modals, confirmations)
6. Add navigation entries

### Phase 4: Polish & Safety (Estimated: 1-2 weeks)
1. Implement device actuation service with safety checks
2. Build setup wizard
3. Error handling and graceful degradation
4. Documentation and HA automation guide
5. Testing (see section 20.1)

### 20.1 Testing Strategy

Each component should be testable in isolation:

1. **`EmhassConnector._build_runtime_params()`** — unit test with mock config, verify all EMHASS parameters are correctly formed (including kW→W conversion)
2. **Cost forecast generation** — unit test with a known `EnergyContract` and mock price sensor data (including capacity tariff and P(t-24h) fallback)
3. **Time window conversion** — unit test with various time strings, optimisation start times, time steps, and overnight windows
4. **Result parsing** — unit test with mock EMHASS API responses (including W→kW conversion)
5. **Override logic** — unit test that overrides correctly modify the deferrable loads list
6. **MPC shrinking horizon** — unit test that `_prepare_mpc_params` correctly adjusts operating hours and passes `def_current_state`
7. **Config validation** — unit test that mismatches between GridMate and EMHASS configs are detected
8. **Integration test** — mock EMHASS API server, run full optimisation flow end-to-end

---

## 21. Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| EMHASS API changes between versions | Breaking changes in connector | Pin EMHASS version in docs; use API version check |
| User does not install EMHASS | Feature unavailable | Clear pre-requisite docs; graceful degradation (page shows "EMHASS not connected") |
| Cost forecast inaccuracy | Sub-optimal schedules | Allow manual override; show forecast vs. actual comparison; P(t-24h) fallback |
| EMHASS config out of sync with GridMate | Optimisation errors | Config validation with actionable warnings; config generation |
| Device actuation failure | Device doesn't turn on/off | Retry mechanism; clear error display; default to manual mode |
| Large number of deferrable loads | EMHASS solver performance | Document recommended limits (~10 loads); warn if exceeded |
| Network issues between containers | Optimisation fails | Retry with backoff; last-known-good schedule continues; status indicator |
| Power unit mismatch (kW vs W) | Wrong EMHASS parameters | Centralised conversion in `EmhassConnector` only |

---

## 22. Architectural Decisions

| Decision | Rationale |
|---|---|
| **Vendor abstraction via ABC** | Allows replacing EMHASS without redesigning GridMate |
| **Deferrable load as a device type** | Reuses existing device/type system; no new storage concepts |
| **Cost forecast from EnergyContract** | Leverages GridMate's most powerful existing feature; no double config |
| **Capacity tariff as marginal penalty** | Includes peak-demand cost in optimisation for more accurate scheduling |
| **Sensor-based price forecasts** | Vendor-independent; works with Nord Pool or any pricing integration |
| **P(t-24h) price fallback** | Reasonable baseline when no forecast sensor is configured |
| **HA automations for scheduling** | Simple, transparent, leverages HA ecosystem |
| **Manual actuation mode as default** | Safety first; users explicitly opt into automatic control |
| **Optimisation params in device `custom_parameters`** | No schema changes to `Device` model |
| **Separate file for optimisation results** | Avoids `settings.json` bloat |
| **Centralised kW↔W conversion** | Prevents unit mismatch bugs; one place to audit |
| **EMHASS config generation from GridMate** | Users don't re-configure things already set up (solar, battery, etc.) |
| **MPC shrinking horizon with run tracking** | Accurate remaining-hours calculation for intra-day re-optimisation |

---

# Appendices

## Appendix A: EMHASS API Endpoints Used by GridMate

| Endpoint | Method | Body | Purpose |
|---|---|---|---|
| `/action/dayahead-optim` | POST | JSON runtimeparams | Run day-ahead optimisation |
| `/action/naive-mpc-optim` | POST | JSON runtimeparams | Run MPC optimisation |
| `/action/publish-data` | POST | — | Republish latest optimisation results |
| `/` | GET | — | Health check / connectivity test |

## Appendix B: Example `runtimeparams` Payload

```json
{
    "load_cost_forecast": [0.28, 0.28, 0.27, 0.26, 0.24, 0.22, 0.20, 0.19,
                           0.18, 0.17, 0.16, 0.15, 0.14, 0.13, 0.12, 0.12,
                           0.13, 0.14, 0.16, 0.18, 0.20, 0.22, 0.25, 0.27,
                           0.28, 0.29, 0.30, 0.31, 0.31, 0.30, 0.28, 0.26,
                           0.24, 0.22, 0.21, 0.20, 0.19, 0.18, 0.17, 0.16,
                           0.18, 0.20, 0.22, 0.24, 0.26, 0.27, 0.28, 0.28],
    "prod_price_forecast": [0.20, 0.20, 0.19, 0.18, 0.16, 0.14, 0.12, 0.11,
                            0.10, 0.09, 0.08, 0.07, 0.06, 0.05, 0.04, 0.04,
                            0.05, 0.06, 0.08, 0.10, 0.12, 0.14, 0.17, 0.19,
                            0.20, 0.21, 0.22, 0.23, 0.23, 0.22, 0.20, 0.18,
                            0.16, 0.14, 0.13, 0.12, 0.11, 0.10, 0.09, 0.08,
                            0.10, 0.12, 0.14, 0.16, 0.18, 0.19, 0.20, 0.20],
    "number_of_deferrable_loads": 2,
    "nominal_power_of_deferrable_loads": [2000, 3000],
    "operating_hours_of_each_deferrable_load": [3, 2],
    "treat_deferrable_load_as_semi_cont": [true, true],
    "set_deferrable_load_single_constant": [false, true],
    "set_deferrable_startup_penalty": [0.0, 0.5],
    "start_timesteps_of_each_deferrable_load": [0, 8],
    "end_timesteps_of_each_deferrable_load": [0, 36],
    "def_current_state": [false, false],
    "battery_minimum_state_of_charge": 0.2,
    "battery_maximum_state_of_charge": 0.9,
    "battery_target_state_of_charge": 0.6,
    "battery_charge_power_max": 2000,
    "battery_discharge_power_max": 800
}
```

**Mapping to GridMate devices in this example:**
- Deferrable load 0: "Gym Chauffage Smartplug" (electric_heating) — 2kW, 3 hours, interruptible, no time constraint
- Deferrable load 1: "Boiler Smartplug" (water_heater) — 3kW, 2 hours, single constant run, window 04:00–18:00, startup penalty €0.50

## Appendix C: Existing Codebase Integration Points

| Existing Component | Integration |
|---|---|
| `DataConnector` | Extended with optimisation config/result methods |
| `HAConnector` | Used by `EmhassConnector` to read sensor states and actuate devices |
| `Device` model | Unchanged — `deferrable_load` is a secondary type with `custom_parameters` |
| `DeviceType` model | Unchanged — new type added to defaults |
| `EnergyContract` | Read-only — used to generate cost forecasts for EMHASS |
| `Solar` config | Read-only — solar sensor entity used for EMHASS solar configuration and config generation |
| `EnergyFeed` | Read-only — load sensor entity used for EMHASS load configuration |
| `Battery` model | Read-only — battery parameters forwarded to EMHASS and used for config generation |
| Existing device forms | Extended — `deferrable_load` type adds optimisation fields to device edit form |
| Navigation (`layout.html`) | Extended — new menu entries for optimisation dashboard and settings |

## Appendix D: Glossary

| Term | Definition |
|---|---|
| **Cost Function** | The mathematical objective EMHASS optimises (profit, cost, self-consumption) |
| **Day-Ahead** | Optimisation run once daily covering the next 24 hours |
| **MPC** | Model Predictive Control — frequent re-optimisation with shrinking horizon |
| **Deferrable Load** | A device whose operation can be shifted in time by the optimiser |
| **Semi-Continuous** | A deferrable load variable that is either at nominal power or zero (on/off) |
| **Single Constant** | A deferrable load that must operate as one uninterrupted block |
| **Timestep Index** | EMHASS's relative position in the optimisation window (0 = start) |
| **Runtime Params** | Dynamic parameters passed to EMHASS per API call, overriding base config |
| **SOC** | State of Charge — battery charge level as fraction (0.0–1.0) |
| **Shrinking Horizon** | MPC technique where remaining operating hours decrease as loads complete during the day |
| **Actuation Mode** | How GridMate handles scheduled device control (manual/notify/automatic) |
| **Capacity Tariff** | A cost component based on peak 15-minute power draw in a billing period |
