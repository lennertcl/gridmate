# Energy Feed Configuration

## Overview

The Energy Feed Configuration allows you to connect your home's electricity meter data to GridMate. This configuration links your Home Assistant DSMR (Dutch Smart Meter) sensors to the energy management system, enabling real-time monitoring and optimization of your energy usage.

## Naming Conventions

GridMate uses consistent terminology throughout the system to avoid confusion between different types of energy measurements:

### Grid-Level Measurements (Meter Readings)

These measurements represent energy flowing to or from the electrical grid, as measured by your smart electricity meter:

- **Consumption**: Energy you purchase from the grid (power flowing from grid → to your home)
  - Example: `total_consumption_high_tariff` = 1250 kWh (you bought 1250 kWh during high tariff periods)
  
- **Injection**: Energy you feed back to the grid, typically from solar panels or local generation (power flowing from your home → to grid)
  - Example: `total_injection_low_tariff` = 450 kWh (you sold 450 kWh back to the grid during low tariff periods)

### Appliance/Device Level Measurements (Usage/Production)

These represent energy actually used by the household. Usage accounts for both grid consumption and local production (solar):

- **Usage**: Total energy consumed by the household = Consumption from grid + Solar production − Injection to grid
  - Example: You consume 3 kW from grid and produce 2 kW solar, injecting 0.5 kW → usage = 3 + 2 − 0.5 = 4.5 kW

Usage can be calculated automatically (default) or provided via dedicated sensor entities (manual mode).

### Power vs Energy

- **Power** (Instantaneous): Measured in **kW (kilowatts)** - the rate of energy flow at a specific moment
  - Example: `actual_consumption` = 2.5 kW (right now, you're using 2.5 kilowatts)
  - Updated every few seconds

- **Energy** (Cumulative): Measured in **kWh (kilowatt-hours)** - the total amount accumulated over time
  - Example: `total_consumption_high_tariff` = 1250 kWh (total accumulated consumption on high tariff)
  - Only increases, never decreases (historical counter)

## What is DSMR?

DSMR (Digitale Slimme Meter Aflezing) is the Dutch standard for smart electricity and gas metering. Home Assistant provides extensive support for DSMR meters through its DSMR integration, which reads data directly from your meter's P1 port or a compatible device. The Energy Feed Configuration uses the standard sensor names provided by Home Assistant's DSMR component.

## Connection Overview

```
Your Smart Meter → Home Assistant DSMR Integration → Home Assistant Sensors → GridMate
```

## Measurement Categories

The Energy Feed Configuration organizes sensors into logical groups for easy setup:

### Total Energy Consumption (from Grid)
Cumulative energy consumed from the grid, split by tariff rate:

- **High Tariff**: Total energy consumed when higher rate applies (usually daytime)
- **Low Tariff**: Total energy consumed when lower rate applies (usually nighttime)

These are meter counters that only increase over time.

### Total Energy Injection (to Grid)
Cumulative energy injected/delivered to the grid, split by tariff rate. Typically from solar panels:

- **High Tariff**: Total energy delivered to grid during high tariff period
- **Low Tariff**: Total energy delivered to grid during low tariff period

These are meter counters that only increase over time.

### Current Power (Live)
Real-time instantaneous power measurements updated every few seconds:

- **Consumption**: Current rate of power being drawn from the grid (in kW)
- **Injection**: Current rate of power being delivered to the grid (in kW)

### Energy Usage

Usage represents total household energy consumption (grid + self-consumed solar). Two modes are available:

- **Auto** (default): Usage is calculated as `consumption + production − injection`. Requires solar production sensor to be configured in Solar Panel Settings. No additional sensors needed.
- **Manual**: Usage is read from dedicated HA sensor entities. Requires the following sensors:
  - `actual_usage` — Current instantaneous usage power (kW)
  - `total_usage_high_tariff` — Cumulative usage at high tariff (kWh)
  - `total_usage_low_tariff` — Cumulative usage at low tariff (kWh)

The usage mode is configured on the Energy Feed settings page. In auto mode, the manual sensor fields are hidden.

## Unit Configuration

All measurements use fixed, standardized units throughout GridMate:

- **Power Unit**: Always **kW (kilowatts)** for instantaneous measurements
- **Energy Unit**: Always **kWh (kilowatt-hours)** for cumulative counters

This ensures consistent calculations and display throughout the system.

## Flexible Configuration

All sensor fields are optional:

- **Minimal Setup**: Start with just consumption and delivery meter counters for basic monitoring
- **Enhanced Setup**: Add live power measurements for real-time visibility
- **Easy to Modify**: Change sensor mappings at any time without losing historical data

## Finding Your Sensor IDs

To find your Home Assistant sensor IDs:

1. Open Home Assistant
2. Go to Settings → Devices & Services → Entities
3. Search for "electricity" or "dsmr" to see available sensors
4. Copy the entity ID (e.g., `sensor.electricity_used_tariff_1`)

Most sensors follow this pattern: `sensor.{meter_type}_{measurement_name}`

## Common Sensor Patterns

### Energy Counters (Cumulative)
- `sensor.electricity_used_tariff_1` - Total consumed at high tariff
- `sensor.electricity_used_tariff_2` - Total consumed at low tariff
- `sensor.electricity_delivered_tariff_1` - Total delivered at high tariff
- `sensor.electricity_delivered_tariff_2` - Total delivered at low tariff

### Live Power (Current)
- `sensor.current_electricity_usage` - Current consumption (grid → home)
- `sensor.current_electricity_delivery` - Current injection (home → grid)

## Why Sensors Are Optional

The MVP implementation focuses on core consumption and injection measurements. Future enhancements will support:

- Per-phase power measurements for three-phase analysis
- Voltage and current monitoring for grid diagnostics
- Additional M-Bus connected devices (gas, water, heat meters)

## Data Persistence

Your Energy Feed Configuration is automatically saved and persisted. Changes take effect immediately without requiring a system restart.

## Next Steps

After configuring your Energy Feed, you can:

1. View real-time energy consumption on the dashboard
2. Set up energy contracts to calculate costs
3. Enable energy optimization to minimize costs or emissions
4. Monitor historical trends and patterns
5. Receive alerts for unusual consumption patterns

## Troubleshooting

If you're unsure about your sensor IDs:

- Check the Home Assistant DSMR component documentation
- Verify your meter is properly connected to Home Assistant
- Start with just the total consumption and delivery sensors, then verify they update

## Standards and Specifications

This implementation follows the official [Home Assistant DSMR specification](https://github.com/home-assistant/core/blob/dev/homeassistant/components/dsmr/sensor.py), ensuring compatibility with standard Home Assistant DSMR integrations.

