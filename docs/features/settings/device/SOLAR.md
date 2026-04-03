# Solar Panel Settings

## Overview

The solar panel settings allow users to configure their Home Assistant solar sensor entity IDs within GridMate. This includes live production sensors from the solar inverter and optional Forecast.Solar estimation sensors. All fields are optional, enabling incremental setup.

## Relevant Artefacts

- [solar-panels.html](../../../../web/templates/settings/device/solar-panels.html) — Settings form template
- [device.py](../../../../web/routes/settings/device.py) — Settings route (`solar_panels` function)
- [solar.py](../../../../web/forms/solar.py) — SolarConfigForm
- [models.py](../../../../web/model/solar/models.py) — Solar, SolarSensors, SolarEstimationSensors
- [data_connector.py](../../../../web/model/data/data_connector.py) — SolarManager

## Models

See [Solar Dashboard documentation](../../dashboards/SOLAR.md#models) for the full model reference.

## Services

### SolarManager

Handles persistence of the `Solar` configuration via `JsonRepository`. Stores data in `settings.json` under the `solar` key.

- `get_config()` — Returns the current Solar configuration (or defaults if not yet saved)
- `set_sensors(sensors_dict)` — Updates the `sensors` sub-object with the provided dict of entity IDs
- `set_estimation_sensors(estimation_dict)` — Updates the `estimation_sensors` sub-object

## Forms

### SolarConfigForm

All fields use `Optional()` validators. Grouped into two sections:

**Solar Panel Sensors**
| Field | Description |
|---|---|
| `actual_production` | HA entity for current power production (kW) |
| `energy_production_today` | HA entity for today's cumulative production (kWh) |
| `energy_production_lifetime` | HA entity for lifetime cumulative production (kWh) |

**Solar Estimation Sensors**
| Field | Description |
|---|---|
| `estimated_actual_production` | Forecast.Solar estimated current production |
| `estimated_energy_production_remaining_today` | Estimated remaining production today |
| `estimated_energy_production_today` | Estimated total production today |
| `estimated_energy_production_hour` | Estimated production this hour |
| `estimated_actual_production_offset_day` | Estimated production at same time +24h |
| `estimated_energy_production_offset_day` | Estimated total energy +24h |
| `estimated_energy_production_offset_hour` | Estimated energy next hour |

## Routes

### GET/POST `/settings/solar-panels`

**GET**: Populates the `SolarConfigForm` from the stored `Solar` configuration and renders the form template.

**POST**: Validates the form, then:
1. Calls `solar_manager.set_sensors()` with the 3 production sensor entity IDs
2. Calls `solar_manager.set_estimation_sensors()` with the 7 estimation entity IDs
3. Flashes a success message and redirects to the same page

## Frontend

### Form Template

The template renders a standard settings form with two sections:

1. **Solar Panel Sensors** — 3 entity ID text fields with placeholder examples
2. **Solar Estimation Sensors** — 7 entity ID text fields with descriptions and a link to the Forecast.Solar integration documentation

### Sensor Discovery

Users find their sensor entity IDs in Home Assistant under Settings → Devices & Services → Entities. Common patterns:
- Solar inverter sensors: `sensor.inverter_power`, `sensor.inverter_energy_today`
- Forecast.Solar sensors: `sensor.energy_production_today`, `sensor.energy_current_hour`
