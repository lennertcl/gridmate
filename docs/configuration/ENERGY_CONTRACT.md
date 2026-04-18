# Energy Contract Configuration

## Overview

An `EnergyContract` is a flexible model for representing complex energy pricing structures. It consists of multiple `EnergyContractComponent` objects, each representing a different pricing mechanism or charge type, combined with a multiplier that controls how each component contributes to the total cost calculation.

Unlike weighted approaches where all weights must sum to 1.0, multipliers in this system allow complete flexibility. Each multiplier can be any positive value, and there is no requirement for them to sum to any particular number. This allows you to:
- Scale individual components independently
- Combine multiple pricing mechanisms with different relative importance
- Add or remove components without needing to rebalance remaining multipliers

## Contract Components

### Base Class: EnergyContractComponent

All components inherit from this abstract class with the following common properties:

- **name** (string): A descriptive name for the component (e.g., "Monthly Fee", "Consumption Charge")
- **multiplier** (float, default: 1.0): The scaling factor for this component's cost contribution. No minimum or maximum - values can be any positive number
- **type** (string): Automatically set to the component's class name for serialization

Each component type implements:
- `to_dict()`: Serialize component to dictionary for storage
- `from_dict()`: Deserialize component from dictionary
- `calculate_cost(period_data, is_monthly)`: Calculate component cost for a period with detailed breakdown

---

## Component Types

### 1. ConstantComponent

**Purpose**: Fixed monthly or yearly charge (e.g., subscription fee, network access charge)

**Formula**: 
```
cost = price_constant (per period) × multiplier
```

**Properties**:
- **price_constant** (float): Fixed price in € per period
- **period** (string): Either "month" or "year"
- **multiplier** (float): Scaling factor for this component

**Example**:
```yaml
name: "Monthly Network Fee"
multiplier: 1.0
price_constant: 15.00
period: "month"
```

---

### 2. FixedComponent

**Purpose**: Consumption or injection charge at a fixed rate per kWh (e.g., standard grid tariff)

**Formula**:
```
cost = fixed_price × energy_consumed_kwh × multiplier
(For injection rewards: cost = min(0, -(fixed_price × energy_injected_kwh × multiplier)))
```

**Properties**:
- **fixed_price** (float): Price in €/kWh
- **is_injection_reward** (boolean, default: False): If True, charges apply to injected energy instead of consumed energy. Injection rewards produce a negative cost that is deducted from the total bill, capped at 0 (never becomes a charge)
- **energy_sensor** (string, optional, default: `total_consumption`): Energy source for the component. Can be one of these predefined values:
  - `consumption_high_tariff`
  - `consumption_low_tariff`
  - `total_consumption`
  - `injection_high_tariff`
  - `injection_low_tariff`
  - `total_injection`
  It can also be a custom Home Assistant energy sensor ID (for example `sensor.custom_meter_delta`). Custom sensors are fetched dynamically from Home Assistant if not already loaded.
- **multiplier** (float): Scaling factor for this component

**Options**:
- Use different tariffs for high/low tariff periods
- Apply same rate to both consumption and injection
- Injection rewards always produce negative costs (deducted from bill) and are capped at 0 (never becomes a charge)

**Example**:
```yaml
name: "50% Standard Consumption"
multiplier: 0.5
fixed_price: 0.225  # €0.225/kWh
is_injection_reward: false
energy_sensor: "total_consumption"
```

**Example (Blended with Dynamic)**:
```yaml
name: "50% Standard Rate"
multiplier: 0.5
fixed_price: 0.07
is_injection_reward: false
energy_sensor: "total_consumption"
```

---

### 3. VariableComponent

**Purpose**: Dynamic pricing based on an Energy Price Provider (e.g., Nord Pool market prices, sensor-based tariffs, or static rates)

**Formula**:
```
cost = [provider_price(t) × variable_price_multiplier + variable_price_constant] × energy_kwh × multiplier
(For injection rewards: cost = min(0, -[...] × energy_injected_kwh × multiplier))
```

**Properties**:
- **price_provider_name** (string): Name of the configured Energy Price Provider to use for price data
- **variable_price_multiplier** (float): Multiplier applied to provider price (usually 1.0 or close to it)
- **variable_price_constant** (float): Additional fixed offset in €/kWh to add to each reading
- **is_injection_reward** (boolean, default: False): If True, applies to injected energy. Injection rewards produce a negative cost that is deducted from the total bill, capped at 0 (never becomes a charge)
- **energy_sensor** (string, optional, default: `total_consumption`): Same preset/custom behavior as in `FixedComponent`, but used as the interval energy source for dynamic pricing integration
- **multiplier** (float): Scaling factor for this component

**Example**:
```yaml
name: "50% Dynamic Market Price"
multiplier: 0.5
price_provider_name: "Nord Pool Belgium"
variable_price_multiplier: 1.1  # 10% markup on market price
variable_price_constant: 0.04  # Add €0.04/kWh base cost
is_injection_reward: false
energy_sensor: "total_consumption"
```

**Example (Wholesale Price with Markup)**:
```yaml
name: "Wholesale + Markup"
multiplier: 1.0
price_provider_name: "Electricity Spot Price"
variable_price_multiplier: 1.15  # 15% markup
variable_price_constant: 0.02
is_injection_reward: false
energy_sensor: "total_consumption"
```

---

### 4. CapacityComponent

**Purpose**: Charge based on maximum power consumption during a billing period (e.g., capacity-based grid fees)

**Formula**:
```
cost = capacity_price_multiplier × max_mean_power_kw × multiplier
```

**Properties**:
- **capacity_price_multiplier** (float): Price in € per kW of maximum power
- **multiplier** (float): Scaling factor for this component

**Notes**:
- Maximum power is determined by finding the highest **mean** kW consumption across all 15-minute windows in the billing period
- Windows are aligned at exactly hh:00, hh:15, hh:30, and hh:45 (not in between)
- The timestamp of the peak 15-minute window is displayed alongside the value for transparency
- This matches the Belgian capacity tariff methodology where the peak quarter-hour mean drives the charge

**Example**:
```yaml
name: "Capacity Charge"
multiplier: 1.0
capacity_price_multiplier: 5.50  # €5.50 per kW of peak power
```

---

### 5. PercentageComponent

**Purpose**: Surcharge calculated as a percentage on top of selected other components (e.g. VAT, levies)

**Formula**:
```
cost = (sum of selected components’ costs) × (percentage / 100) × multiplier
```

**Properties**:
- **percentage** (float): The percentage rate to apply (e.g. 6.0 for 6%)
- **applies_to_indices** (list of int): Indices (0-based) of the components this percentage is calculated on. Only non-percentage components can be referenced
- **multiplier** (float): Scaling factor for this component

**Behavior**:
- Percentage components are always evaluated after all other component types
- When a component is removed, the `applies_to_indices` of all percentage components are automatically adjusted (shifted down and stale references removed)
- The cost breakdown details list which components were included in the base sum

**Example**:
```yaml
name: "VAT"
multiplier: 1.0
percentage: 6.0
applies_to_indices: [0, 1, 2, 3, 4]  # all components except injection
```

---

## Multiplier Guidelines

- **No requirement to sum to 1.0**: Unlike weights, multipliers can sum to any value or not sum at all
- **Independent scaling**: Each component can be scaled independently from others
- **Flexible composition**: Add, remove, or modify components without affecting others
- **Typical use cases**:
  - Multiplier = 1.0: Full component contribution
  - Multiplier = 0.5: Component contributes 50% of its value
  - Multiplier = 0.0: Component effectively disabled
  - Multiplier > 1.0: Component amplified beyond normal value

**Example valid multipliers**:
```
Fixed Rate (50% blend): 0.5
Dynamic Rate (50% blend): 0.5
Network Fee: 1.0
Energy Tax: 1.0
Capacity Charge: 1.0
Injection Reward: 1.0
Total: 5.0 (no requirement to equal 1.0) ✓
```

---

## Energy Price Providers

Energy Price Providers are a separate abstraction that supplies price data to `VariableComponent` instances. Providers are configured independently and referenced by name from components. This decouples price sourcing from cost calculation.

### Provider Types

#### StaticPriceProvider

Returns a constant price for all timestamps.

- **price_per_kwh** (float): Fixed price in €/kWh

#### SensorPriceProvider

Fetches prices from a Home Assistant sensor's statistics (past) and forecast attribute (future).

- **price_sensor** (string): Entity ID of a HA sensor (e.g., `sensor.electricity_price`)

#### NordpoolPriceProvider

Fetches prices from the Nord Pool HA integration. Uses the derived sensors `sensor.nord_pool_{area}_current_price` and `sensor.nord_pool_{area}_next_price` for immediate fallback values, and the Home Assistant `nordpool.get_prices_for_date` action for the published day prices.

- **area** (string): Nord Pool area code (e.g., `BE`, `NL`, `DE_LU`)

Published prices are read per day through Home Assistant's Nord Pool action response and converted from `/MWh` to `/kWh`. Tomorrow's prices only become available once Nord Pool has published them through the integration.

#### ActionPriceProvider

Calls a Home Assistant action (service) to retrieve prices. Useful for custom integrations that expose price data via service calls.

- **action_domain** (string): HA domain (e.g., `nordpool`)
- **action_service** (string): Service name (e.g., `get_prices_for_date`)
- **action_data** (dict): Additional service data
- **response_price_key** (string): Key in the response containing the price list

### API Endpoint

The `/api/energy-prices` endpoint returns current price data from all defined Energy Price Providers. It fetches prices for today and tomorrow (48h window). Used by the live dashboard for price chart display.

---

## Practical Examples

### Simple Fixed-Rate Contract
```yaml
components:
  - type: ConstantComponent
    name: "Monthly Fee"
    multiplier: 1.0
    price_constant: 12.00
    period: "month"
  
  - type: FixedComponent
    name: "Energy Charge"
    multiplier: 1.0
    fixed_price: 0.20
    is_injection_reward: false
    energy_sensor: "total_consumption"
```

### 50/50 Blend: Fixed + Dynamic Pricing
```yaml
components:
  - type: FixedComponent
    name: "50% Fixed Rate"
    multiplier: 0.5
    fixed_price: 0.07
    is_injection_reward: false
    energy_sensor: "total_consumption"
  
  - type: VariableComponent
    name: "50% Dynamic (BELPEX)"
    multiplier: 0.5
    price_provider_name: "BELPEX Price"
    variable_price_multiplier: 1.1
    variable_price_constant: 0.04
    is_injection_reward: false
    energy_sensor: "total_consumption"
  
  - type: ConstantComponent
    name: "Grid Access"
    multiplier: 1.0
    price_constant: 18.00
    period: "year"
  
  - type: FixedComponent
    name: "Energy Tax"
    multiplier: 1.0
    fixed_price: 0.05
    is_injection_reward: false
    energy_sensor: "total_consumption"
  
  - type: CapacityComponent
    name: "Capacity Tariff"
    multiplier: 1.0
    capacity_price_multiplier: 53.0
    period: "year"
  
  - type: VariableComponent
    name: "Solar Injection Reward"
    multiplier: 0.2
    price_provider_name: "BELPEX Price"
    variable_price_multiplier: 1.0
    variable_price_constant: 0.0
    is_injection_reward: true
    energy_sensor: "total_injection"

  - type: PercentageComponent
    name: "VAT"
    multiplier: 1.0
    percentage: 6.0
    applies_to_indices: [0, 1, 2, 3, 4]  # All except Solar Injection Reward
```

### Complex Multi-Tariff with Solar
```yaml
components:
  - type: ConstantComponent
    name: "Network Fee"
    multiplier: 1.0
    price_constant: 10.00
    period: "month"
  
  - type: FixedComponent
    name: "High Tariff Consumption"
    multiplier: 1.0
    fixed_price: 0.25
    is_injection_reward: false
    energy_sensor: "consumption_high_tariff"
  
  - type: FixedComponent
    name: "Low Tariff Consumption"
    multiplier: 1.0
    fixed_price: 0.18
    is_injection_reward: false
    energy_sensor: "consumption_low_tariff"
  
  - type: FixedComponent
    name: "Solar Injection Reward"
    multiplier: 1.0
    fixed_price: 0.15
    is_injection_reward: true
    energy_sensor: "total_injection"
  
  - type: CapacityComponent
    name: "Demand Charge"
    multiplier: 1.0
    capacity_price_multiplier: 6.50
    period: "year"
```

---

## Cost Calculation

The system provides methods to calculate energy costs:

### Monthly Cost Calculation
```python
period_data = EnergyPeriodData(
    consumption_high_tariff=500.0,  # kWh
    consumption_low_tariff=200.0,   # kWh
    injection_high_tariff=100.0,    # kWh
    max_power_kw=5.5                # kW
)

total_cost, breakdowns = contract.calculate_monthly_cost(period_data)

# breakdowns is a list of EnergyCostBreakdown objects with per-component details
for breakdown in breakdowns:
    print(f"{breakdown.component_name}: {breakdown.cost:.2f}€")
    print(f"  Details: {breakdown.details}")
```

### Yearly Cost Calculation
```python
total_cost, breakdowns = contract.calculate_yearly_cost(period_data)
```

---

## Implementation Notes

- Components are stored in JSON format with their `type` field for deserialization
- `FixedComponent` and `VariableComponent` use `energy_sensor` and default to `total_consumption`
- Preset options are resolved directly from period totals and 15-minute histories
- Custom `energy_sensor` entity IDs are fetched dynamically from Home Assistant and added to `EnergyPeriodData.sensor_history` when needed
- Each component is independent and can be added/removed without affecting others
- Total cost calculation sums contributions from all components
- Multipliers provide flexible cost scaling
- Backward compatibility: Old weight-based contracts can be migrated by converting weights to multipliers

## Frontend

The energy contract page uses standard Flask form POST for all component operations (add, edit, remove):

- Component cards are read-only summaries by default
- Each component has an `Edit` button and a `Remove` button (inline form with confirmation dialog)
- Clicking `Edit` opens a modal dialog prefilled with existing values
- The modal contains a separate `<form method="POST">` for each component type, using WTForms-rendered fields (`ConstantComponentForm`, `FixedComponentForm`, `VariableComponentForm`, `CapacityComponentForm`, `PercentageComponentForm`)
- Hidden fields (`action`, `component_type`, `index`) determine whether the submit adds or updates a component
- The submit button label changes from `Add Component` to `Update Component` in edit mode
- On successful submit, the page reloads with a flash message confirmation

Energy sensor input behavior:

- Fixed and variable component forms use a text input with `datalist` suggestions
- Preset options are:
  - `consumption_high_tariff`
  - `consumption_low_tariff`
  - `total_consumption`
  - `injection_high_tariff`
  - `injection_low_tariff`
  - `total_injection`
- A `Custom sensor` datalist option is included; selecting it clears the field so the user can type any Home Assistant sensor ID
