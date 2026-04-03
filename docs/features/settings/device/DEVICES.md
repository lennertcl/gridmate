# Device Configuration

## Overview

The device configuration feature allows users to register and manage their smart home devices within the energy management system. Devices are assigned a **primary type** and zero or more **secondary types**, which together define the parameter schema for that device. There is no restriction on which types can be used as primary or secondary — any device type can serve in either role. Each device type specifies its own mandatory and optional custom parameters (such as HA entity IDs for sensors and controls). A device's full parameter set is the union of parameters from all its assigned types.

The system ships with 14 built-in device types defined as Python subclasses of the `DeviceType` base class:
- **Appliances**: `WashingMachine`, `Dryer`, `Dishwasher` (no own parameters — add other types for capabilities)
- **Vehicles & Charging**: `ElectricVehicle`, `ChargingStation`
- **Heating & Climate**: `WaterHeater`, `ElectricHeating`, `HeatPump`
- **Storage**: `HomeBattery`, `BatteryDevice`
- **Monitoring & Control**: `EnergyReportingDevice`, `AutomatableDevice`, `DurationReportingDevice`
- **Optimization**: `DeferrableLoad` — provides scheduling parameters for the EMHASS optimizer

Device types are defined as classes in code and are not user-editable. Each subclass defines its `type_id`, `name`, `icon`, `description` as class attributes and overrides `_define_parameters()` to declare its parameter schema. Types are auto-registered into the global registry via `__init_subclass__`. The power of the system lies in combining multiple types per device to match its capabilities.

## Relevant Artefacts

- [devices.html](../../../web/templates/settings/device/devices.html) — Device list settings page
- [add-device.html](../../../web/templates/settings/device/add-device.html) — Add device form
- [edit-device.html](../../../web/templates/settings/device/edit-device.html) — Edit device form
- [device.py](../../../web/routes/settings/device.py) — Settings routes for devices
- [device_type.py](../../../web/model/device/device_type.py) — DeviceType base class and registry
- [device_types.py](../../../web/model/device/device_types.py) — Concrete device type subclasses (BatteryDevice, HomeBattery, DeferrableLoad, etc.)
- [models.py](../../../web/model/device/models.py) — Domain models (Device, CustomParameterDefinition)
- [data_connector.py](../../../web/model/data/data_connector.py) — DataConnector, DeviceManager, DeviceTypeManager
- [device.py](../../../web/forms/device.py) — WTForms for devices
- [device-form.js](../../../web/static/js/device-form.js) — Dynamic multi-type parameter loading for device forms

## Models

### Device

The core device model. A device must have a `primary_type` and can optionally have additional `secondary_types`.

| Field | Type | Required | Description |
|---|---|---|---|
| `device_id` | str | auto | Unique identifier, auto-generated on creation |
| `name` | str | yes | Human-readable device name |
| `primary_type` | str | yes | Main DeviceType `type_id` |
| `secondary_types` | list[str] | no | Additional DeviceType `type_id`s providing extra capabilities |
| `custom_parameters` | dict | no | Key-value pairs of configured parameters |
| `created_at` | datetime | auto | Creation timestamp |
| `last_updated` | datetime | auto | Last modification timestamp |

`custom_parameters` stores the user-provided values for parameters defined by all the device's assigned types. A device must provide all mandatory parameters from its primary type and all secondary types. Example:

```json
{
    "device_id": "electric_vehicle_1707000000",
    "name": "Volkswagen ID.4",
    "primary_type": "electric_vehicle",
    "secondary_types": ["battery_device", "energy_reporting_device", "automatable_device"],
    "custom_parameters": {
        "range_sensor": "sensor.vw_id4_range",
        "battery_level_sensor": "sensor.vw_id4_battery_level",
        "power_sensor": "sensor.vw_id4_charger_power",
        "control_entity": "switch.vw_id4_charging"
    }
}
```

Key methods:
- `get_all_type_ids()` — Returns `[primary_type] + secondary_types`
- `get_all_parameters(type_registry)` — Returns the union of parameters from all assigned types

### DeviceType

Base class for all device types, defined in `device_type.py`. Concrete types subclass `DeviceType` in `device_types.py` and are auto-registered into the global registry via `__init_subclass__` when their module is imported.

| Class Attribute | Type | Description |
|---|---|---|
| `type_id` | str | Unique identifier (snake_case). Empty string on the base class; concrete subclasses set a non-empty value to trigger auto-registration. |
| `name` | str | Human-readable name |
| `icon` | str | FontAwesome CSS class for display |
| `description` | str | Explanatory text |

| Instance Attribute | Type | Description |
|---|---|---|
| `custom_parameters` | dict[str, CustomParameterDefinition] | Parameters defined by this type, populated by `_define_parameters()` |

Key methods:
- `_define_parameters()` — Override in subclasses to return the parameter dict. Base returns `{}`.
- `get_mandatory_parameters()` — Returns parameters where `required=True`
- `get_optional_parameters()` — Returns parameters where `required=False`
- `to_dict()` — Serializes the type to a dict

To add a new device type, create a subclass with a non-empty `type_id` class attribute:

```python
class PoolPump(DeviceType):
    type_id = 'pool_pump'
    name = 'Pool Pump'
    icon = 'fas fa-water'
    description = 'A swimming pool pump'

    def _define_parameters(self):
        return {
            'flow_rate_sensor': CustomParameterDefinition(
                name='flow_rate_sensor',
                label='Flow Rate Sensor',
                param_type='entity',
                unit='L/min',
                description='HA entity that reports pump flow rate',
            ),
        }
```

### CustomParameterDefinition

Defines a single parameter within a device type.

| Field | Type | Description |
|---|---|---|
| `name` | str | Parameter key (snake_case) |
| `label` | str | Human-readable label |
| `param_type` | str | One of: `string`, `float`, `int`, `bool`, `entity`, `time` |
| `unit` | str | Display unit (e.g., kW, %, °C) |
| `required` | bool | Whether devices must provide this parameter |
| `description` | str | Help text shown in forms |
| `placeholder` | str | Input placeholder text |

The `param_type` determines how the field is rendered in forms:
- `bool` renders a checkbox. Unchecked = `False`, checked = `True`. Falls back to `default_value` when not present.
- `time` renders an HTML time picker in 24-hour notation (HH:MM).
- All other types render a standard text input.

### Built-in Device Types

The following types are defined in `device_types.py` as `DeviceType` subclasses, each declaring its parameters via `_define_parameters()`:

| Type ID | Name | Own Parameters |
|---|---|---|
| `battery_device` | Battery Device | battery_level_sensor, capacity_kwh, power_sensor |
| `automatable_device` | Automatable Device | control_entity, status_sensor |
| `energy_reporting_device` | Energy Reporting Device | power_sensor, energy_sensor |
| `duration_reporting_device` | Duration Reporting Device | remaining_time_sensor |
| `washing_machine` | Washing Machine | *(none — add capabilities via secondary types)* |
| `dryer` | Dryer | *(none)* |
| `dishwasher` | Dishwasher | *(none)* |
| `electric_vehicle` | Electric Vehicle | range_sensor, charging_state_sensor |
| `home_battery` | Home Battery | opt_enabled, max_charge_power, max_discharge_power, mode_select_entity, charge_efficiency, discharge_efficiency, min_charge_level, max_charge_level, target_soc |
| `water_heater` | Water Heater | temperature_sensor |
| `electric_heating` | Electric Heating | temperature_sensor, thermostat_entity |
| `heat_pump` | Heat Pump | temperature_sensor, cop_sensor |
| `charging_station` | Charging Station | max_charge_rate, session_energy_sensor |
| `deferrable_load` | Deferrable Load | opt_enabled, opt_nominal_power, opt_duration_hours, opt_continuous_operation, opt_earliest_start, opt_latest_end, opt_startup_penalty, opt_priority |

A typical device configuration uses a concrete type as primary and adds other types as secondary:
- **Washing Machine**: primary=`washing_machine`, secondary=[`automatable_device`, `energy_reporting_device`, `duration_reporting_device`, `deferrable_load`]
- **Volkswagen ID.4**: primary=`electric_vehicle`, secondary=[`battery_device`, `energy_reporting_device`, `automatable_device`]
- **Water Heater**: primary=`water_heater`, secondary=[`energy_reporting_device`, `automatable_device`, `deferrable_load`]

## Services

### DeviceManager

Provides device CRUD operations via the `DataConnector`.

- `add_device(device_id, name, primary_type, secondary_types, custom_parameters)` — Creates a new device
- `update_device(device_id, name, primary_type, secondary_types, custom_parameters)` — Updates an existing device
- `remove_device(device_id)` — Deletes a device
- `list_all_devices()` — Returns all registered devices
- `get_device(device_id)` — Returns a single device
- `get_devices_by_type(type_id)` — Filters devices that have the given type as primary or secondary

### DeviceTypeManager

Provides read-only access to the built-in device type registry defined in `device_types.py`.

- `get_registry()` — Returns the full dict of all device types
- `get_type(type_id)` — Returns a single type
- `get_type_choices()` — Returns `(type_id, name)` tuples for form select fields
- `get_devices_using_type(type_id)` — Finds devices that reference a type (primary or secondary)

## Forms

### AddDeviceForm / EditDeviceForm

Minimal forms with `device_name` and `primary_type` (select). Primary type choices are populated dynamically from the type registry. Secondary types are submitted as checkbox values from the template. Custom parameter fields are loaded via JavaScript from the `/api/device-types/parameters` endpoint when the user selects or changes types. Parameter values are submitted as `param_<name>` form fields.

## Routes

### Devices

| Route | Method | Description |
|---|---|---|
| `/settings/devices` | GET | Device list with type icons and parameter counts |
| `/settings/add-device` | GET/POST | Add device form with multi-type selection and dynamic parameters |
| `/settings/edit-device/<device_id>` | GET/POST | Edit form pre-populated with device data |
| `/settings/remove-device/<device_id>` | GET/POST | Delete a device with confirmation |

### API

| Route | Method | Description |
|---|---|---|
| `/api/device-types/parameters` | GET | Returns combined parameters for multiple types. Accepts `?types=type1,type2,...` query parameter. Returns `{ parameters, types }` JSON. |

## Frontend

### Device List (`devices.html`)

Shows a table of all configured devices using a 4-column grid layout (`device-config-table`). Each row is a clickable link (`.device-row-link`) that navigates to the device detail dashboard page. Columns: device name with icon (`.device-name-with-icon`), type badges, parameter count, and edit/remove actions. The icon is displayed inline left-aligned next to the device name. Action buttons use `stopPropagation` to prevent the row link from firing when clicking edit or remove.

### Add/Edit Device (`add-device.html`, `edit-device.html`)

The form provides a primary type dropdown and a checkbox grid of secondary types. When types are selected or changed, `device-form.js` fetches `/api/device-types/parameters?types=...` and renders combined input fields for all parameters across all selected types. Fields are rendered according to their `param_type`: `bool` as checkboxes, `time` as 24-hour time pickers, and all others as text inputs. The primary type's checkbox is automatically hidden from the secondary types grid. Required parameters are marked with an asterisk. On edit, existing parameter values and secondary types are pre-populated.

When the user changes secondary types, any values already entered in parameter fields are preserved for fields that remain visible after the change. This is handled by capturing current form values before re-rendering and restoring them into matching fields.

When a primary type is selected that defines `default_secondary_types`, those secondary types are automatically pre-checked in the form. This only applies when adding a new device, not when editing an existing one. The defaults map is defined in `device-form.js` (`DEFAULT_SECONDARY_TYPES`) and is purely a frontend UX convenience — it does not affect backend logic or constrain the user's choices.

Default secondary types per primary type:

| Primary Type | Default Secondary Types |
|---|---|
| Home Battery | Battery Device, Energy Reporting Device |
| Electric Vehicle | Battery Device, Energy Reporting Device |
| Washing Machine | Automatable Device, Energy Reporting Device, Duration Reporting Device, Deferrable Load |
| Dryer | Automatable Device, Energy Reporting Device, Duration Reporting Device, Deferrable Load |
| Dishwasher | Automatable Device, Energy Reporting Device, Duration Reporting Device, Deferrable Load |
| Water Heater | Energy Reporting Device, Automatable Device, Deferrable Load |
| Electric Heating | Energy Reporting Device, Deferrable Load |
| Heat Pump | Energy Reporting Device, Deferrable Load |
| Charging Station | Energy Reporting Device, Deferrable Load |
