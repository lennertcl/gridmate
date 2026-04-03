# Energy Costs Dashboard

## Overview

The energy costs dashboard provides visually pleasing, easy-to-understand and useful insights into a user's energy usage and how it translates to costs. Users can select a time period (monthly or yearly) and the dashboard displays detailed meter readings, cost breakdowns, and charts that visualize energy consumption patterns and cost components.

## Relevant Artefacts

- [costs.html](../../web/templates/dashboard/costs.html) — Dashboard template
- [dashboard.py](../../web/routes/dashboards/dashboard.py) — Dashboard routes
- [cost_calculator.py](../../web/model/energy/cost_calculator.py) — Cost calculation service
- [models.py](../../web/model/energy/models.py) — Energy domain models (EnergyPeriodData, EnergyContract, EnergyCostBreakdown, etc.)
- [data_connector.py](../../web/model/data/data_connector.py) — EnergyDataService for fetching HA data
- [costs.css](../../web/static/css/dashboard/costs.css) — Page-specific styles

## Models

### EnergyPeriodData

Stores all energy measurements for a specific period. Key fields:

| Field | Type | Description |
|---|---|---|
| `consumption_high_tariff` | float | Total energy consumed at high tariff (kWh delta) |
| `consumption_low_tariff` | float | Total energy consumed at low tariff (kWh delta) |
| `total_consumption` | float | Total consumption over the period (`high + low`) |
| `injection_high_tariff` | float | Total energy injected at high tariff (kWh delta) |
| `injection_low_tariff` | float | Total energy injected at low tariff (kWh delta) |
| `total_injection` | float | Total injection over the period (`high + low`) |
| `consumption_high_start/end` | float | Absolute meter reading at start/end of period |
| `consumption_low_start/end` | float | Absolute meter reading at start/end of period |
| `injection_high_start/end` | float | Absolute meter reading at start/end of period |
| `injection_low_start/end` | float | Absolute meter reading at start/end of period |
| `max_power_kw` | float | Peak 15-minute mean power draw (kW) |
| `max_power_timestamp` | str | Timestamp of peak power occurrence |
| `sensor_history` | dict | Raw 15-minute interval statistics per sensor |

### EnergyCostBreakdown

Provides per-component cost details with a `to_dict()` method that includes a friendly `component_type_label` (e.g., "Constant", "Fixed", "Variable", "Capacity") for display consistency across the dashboard and settings pages. The `details` string shows the calculation formula; the multiplier is only included in the detail text when it differs from 1.0.

## Services

### CostCalculationService

Orchestrates cost calculations. Key methods:

- `calculate_monthly_costs(period_data)` / `calculate_yearly_costs(period_data)` — Returns `(total_cost, list[EnergyCostBreakdown])`
- `get_meter_readings_summary(period_data)` — Returns a dict with all start/end readings, tariff deltas, totals, and peak power
- `get_cost_summary(period_data, is_monthly)` — Returns dict with total cost, consumption/injection totals, cost grouped by type
- `get_daily_evolution(period_data, energy_feed)` — Aggregates 15-min sensor history into daily state values for the evolution chart. For each meter sensor, it uses the first available 15-minute mean window of each day; for power, it scans the full day and keeps the maximum 15-minute mean. Returns daily consumption/injection per tariff and daily max power

### EnergyDataService

Fetches statistics from Home Assistant and populates `EnergyPeriodData`. Uses a hybrid fetching strategy to ensure complete data coverage regardless of the selected time range:

- **Recent data** (within the last 10 days): Fetches 5-minute short-term statistics and aggregates them into 15-minute intervals at :00/:15/:30/:45 boundaries
- **Older data** (beyond 10 days): Falls back to hourly long-term statistics, which are never purged by HA's recorder
- **Mixed ranges** (e.g. a full month): Splits the request at the retention boundary, fetching hourly data for the older portion and 5-minute data for the recent portion, then merges both

This is necessary because Home Assistant automatically purges the `statistics_short_term` table (5-minute aggregates) after 10 days by default, while the `statistics` table (hourly aggregates) is retained indefinitely.

The service also creates preselectable sensor aliases for contract components (`consumption_high_tariff`, `consumption_low_tariff`, `total_consumption`, `injection_high_tariff`, `injection_low_tariff`, `total_injection`) and dynamically fetches custom contract energy sensors when they are not present yet in `sensor_history`.

## Forms

### EnergyCostsForm

Handles time period selection with fields for `period_type` (SelectField with Monthly/Yearly choices), `month` (SelectField with named month choices January-December), and `year` (IntegerField).

## Routes

### GET `/dashboard/costs`

Main energy costs dashboard route. Accepts query parameters `period_type`, `month`, `year` for time period selection. The route:

1. Loads the energy contract and creates a `CostCalculationService`
2. Fetches period data from Home Assistant (falls back to empty data if unavailable)
3. Calculates costs and breakdowns
4. Sorts breakdowns by absolute cost (largest first) for the breakdown table
5. Computes daily evolution data for the meter readings chart
6. Renders the template with all computed context

## Frontend

### Meter Readings Section

Displays a table with four columns:
- **Meter**: Label for each tariff (Consumption High, Consumption Low, Injection High, Injection Low)
- **Start of Period**: Absolute meter reading at the beginning of the selected period
- **Current**: Absolute meter reading at the end of the period
- **Difference**: Energy delta during the period (kWh)

Total rows aggregate high and low tariffs. Below the table, a card highlights the peak 15-minute mean power draw with timestamp.

Below the meter table, a 3-card metrics row provides:
- **Peak 15-minute mean power** (kW + timestamp)
- **Total consumption** for the selected period (kWh)
- **Total injection** for the selected period (kWh)

The consumption and injection cards use dedicated color accents to make import/export energy totals visually distinct.

### Energy Over Time Chart

A stacked bar + line chart with:
- **Stacked bars**: Daily consumption/injection by tariff (consumption above zero, injection below zero)
- **Line overlay**: Daily net energy (kWh)

Uses the daily evolution data computed by `get_daily_evolution()`.

### Power Over Time Chart

A dedicated power chart with:
- **Bar dataset**: Daily peak 15-minute mean power draw (kW)

Uses the daily evolution data computed by `get_daily_evolution()`.

### Cost Summary Bar

A compact green bar at the top of the cost breakdown section showing the total cost estimate, average daily cost, and cost per kWh consumed. Replaces the previously large full-width cost display.

### Cost Breakdown Table

Sorted by absolute cost (largest first). Columns:
- Component name
- Type (colored badge matching the energy contract page: Constant, Fixed, Variable, Capacity)
- Cost (negative values shown in green for injection rewards/deductions)
- Calculation details

### Cost by Component Chart

A horizontal bar chart showing each component's cost individually (grouped by component name, not type). Sorted by absolute cost. Each component is colored by its type (Constant, Fixed, Variable, Capacity) regardless of whether the cost is positive or negative.
