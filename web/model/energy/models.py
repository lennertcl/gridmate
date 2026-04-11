"""
Energy-related domain models
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Tuple

ENERGY_SENSOR_CONSUMPTION_HIGH_TARIFF = 'consumption_high_tariff'
ENERGY_SENSOR_CONSUMPTION_LOW_TARIFF = 'consumption_low_tariff'
ENERGY_SENSOR_TOTAL_CONSUMPTION = 'total_consumption'
ENERGY_SENSOR_INJECTION_HIGH_TARIFF = 'injection_high_tariff'
ENERGY_SENSOR_INJECTION_LOW_TARIFF = 'injection_low_tariff'
ENERGY_SENSOR_TOTAL_INJECTION = 'total_injection'
ENERGY_SENSOR_USAGE_HIGH_TARIFF = 'usage_high_tariff'
ENERGY_SENSOR_USAGE_LOW_TARIFF = 'usage_low_tariff'
ENERGY_SENSOR_TOTAL_USAGE = 'total_usage'
ENERGY_SENSOR_DEFAULT = ENERGY_SENSOR_TOTAL_CONSUMPTION

PRESELECTABLE_ENERGY_SENSORS = {
    ENERGY_SENSOR_CONSUMPTION_HIGH_TARIFF,
    ENERGY_SENSOR_CONSUMPTION_LOW_TARIFF,
    ENERGY_SENSOR_TOTAL_CONSUMPTION,
    ENERGY_SENSOR_INJECTION_HIGH_TARIFF,
    ENERGY_SENSOR_INJECTION_LOW_TARIFF,
    ENERGY_SENSOR_TOTAL_INJECTION,
    ENERGY_SENSOR_USAGE_HIGH_TARIFF,
    ENERGY_SENSOR_USAGE_LOW_TARIFF,
    ENERGY_SENSOR_TOTAL_USAGE,
}

ENERGY_SENSOR_OPTION_LABELS = {
    ENERGY_SENSOR_CONSUMPTION_HIGH_TARIFF: 'Consumption high tariff',
    ENERGY_SENSOR_CONSUMPTION_LOW_TARIFF: 'Consumption low tariff',
    ENERGY_SENSOR_TOTAL_CONSUMPTION: 'Total consumption',
    ENERGY_SENSOR_INJECTION_HIGH_TARIFF: 'Injection high tariff',
    ENERGY_SENSOR_INJECTION_LOW_TARIFF: 'Injection low tariff',
    ENERGY_SENSOR_TOTAL_INJECTION: 'Total injection',
    ENERGY_SENSOR_USAGE_HIGH_TARIFF: 'Usage high tariff',
    ENERGY_SENSOR_USAGE_LOW_TARIFF: 'Usage low tariff',
    ENERGY_SENSOR_TOTAL_USAGE: 'Total usage',
}


@dataclass
class EnergyPeriodData:
    """Energy data for a specific period (month/year)

    Contains all the energy measurements needed to calculate costs.
    Supports 15-minute interval statistics from Home Assistant's recorder.
    """

    # Total consumption and injection (kWh) - Summaries
    consumption_high_tariff: float = 0.0
    consumption_low_tariff: float = 0.0
    injection_high_tariff: float = 0.0
    injection_low_tariff: float = 0.0
    total_consumption: float = 0.0
    total_injection: float = 0.0

    # Start/end absolute meter readings (kWh)
    consumption_high_start: float = 0.0
    consumption_high_end: float = 0.0
    consumption_low_start: float = 0.0
    consumption_low_end: float = 0.0
    injection_high_start: float = 0.0
    injection_high_end: float = 0.0
    injection_low_start: float = 0.0
    injection_low_end: float = 0.0

    # Maximum power consumption (kW)
    max_power_kw: float = 0.0
    max_power_timestamp: str = ''

    # Monthly peak powers for capacity tariff calculation (month number -> peak kW)
    # Used for yearly calculations: capacity tariff = avg of monthly peaks (TTM)
    monthly_peak_powers: Dict[int, float] = field(default_factory=dict)

    # 15-minute interval statistics from Home Assistant
    # Format: { 'sensor.id': [{ 'start': ms_timestamp, 'end': ms_timestamp,
    #                            'mean': float, 'change': float,
    #                            'max': float, 'state': float }, ...] }
    sensor_history: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.total_consumption = self.consumption_high_tariff + self.consumption_low_tariff
        self.total_injection = self.injection_high_tariff + self.injection_low_tariff

        consumption_high_history = self.sensor_history.get(ENERGY_SENSOR_CONSUMPTION_HIGH_TARIFF, [])
        consumption_low_history = self.sensor_history.get(ENERGY_SENSOR_CONSUMPTION_LOW_TARIFF, [])
        injection_high_history = self.sensor_history.get(ENERGY_SENSOR_INJECTION_HIGH_TARIFF, [])
        injection_low_history = self.sensor_history.get(ENERGY_SENSOR_INJECTION_LOW_TARIFF, [])

        if (
            consumption_high_history
            and consumption_low_history
            and ENERGY_SENSOR_TOTAL_CONSUMPTION not in self.sensor_history
        ):
            self.sensor_history[ENERGY_SENSOR_TOTAL_CONSUMPTION] = self._merge_sensor_histories(
                consumption_high_history,
                consumption_low_history,
            )

        if (
            injection_high_history
            and injection_low_history
            and ENERGY_SENSOR_TOTAL_INJECTION not in self.sensor_history
        ):
            self.sensor_history[ENERGY_SENSOR_TOTAL_INJECTION] = self._merge_sensor_histories(
                injection_high_history,
                injection_low_history,
            )

    def get_total_consumption(self) -> float:
        return self.total_consumption

    def get_total_injection(self) -> float:
        return self.total_injection

    @staticmethod
    def _merge_sensor_histories(
        first_history: List[Dict[str, Any]],
        second_history: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not first_history or not second_history:
            return []

        first_by_start = {entry.get('start'): entry for entry in first_history if entry.get('start') is not None}
        second_by_start = {entry.get('start'): entry for entry in second_history if entry.get('start') is not None}

        merged_entries: List[Dict[str, Any]] = []
        for start in sorted(set(first_by_start.keys()) & set(second_by_start.keys())):
            first_entry = first_by_start[start]
            second_entry = second_by_start[start]
            merged_entries.append(
                {
                    'start': start,
                    'end': first_entry.get('end', second_entry.get('end', start)),
                    'state': (first_entry.get('state') or 0.0) + (second_entry.get('state') or 0.0),
                    'mean': (first_entry.get('mean') or 0.0) + (second_entry.get('mean') or 0.0),
                    'max': (first_entry.get('max') or 0.0) + (second_entry.get('max') or 0.0),
                    'change': (first_entry.get('change') or 0.0) + (second_entry.get('change') or 0.0),
                }
            )

        return merged_entries


@dataclass
class EnergyCostBreakdown:
    """Breakdown of costs by component

    Provides a detailed cost analysis showing contribution from each component.
    """

    component_name: str = ''
    component_type: str = ''
    cost: float = 0.0  # in € (euros)
    multiplier: float = 1.0
    details: str = ''  # Human-readable details about the calculation

    TYPE_LABELS = {
        'ConstantComponent': 'Constant',
        'FixedComponent': 'Fixed',
        'VariableComponent': 'Variable',
        'CapacityComponent': 'Capacity',
        'PercentageComponent': 'Percentage',
    }

    def to_dict(self) -> Dict:
        return {
            'component_name': self.component_name,
            'component_type': self.component_type,
            'component_type_label': self.TYPE_LABELS.get(self.component_type, self.component_type),
            'cost': round(self.cost, 2),
            'multiplier': self.multiplier,
            'details': self.details,
        }


@dataclass
class EnergyFeed:
    total_consumption_high_tariff: str = ''
    total_consumption_low_tariff: str = ''
    total_injection_high_tariff: str = ''
    total_injection_low_tariff: str = ''

    actual_consumption: str = ''
    actual_injection: str = ''

    actual_usage: str = ''
    total_usage_high_tariff: str = ''
    total_usage_low_tariff: str = ''
    usage_mode: str = 'auto'

    power_unit: str = 'kW'
    energy_unit: str = 'kWh'

    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'total_consumption_high_tariff': self.total_consumption_high_tariff,
            'total_consumption_low_tariff': self.total_consumption_low_tariff,
            'total_injection_high_tariff': self.total_injection_high_tariff,
            'total_injection_low_tariff': self.total_injection_low_tariff,
            'actual_consumption': self.actual_consumption,
            'actual_injection': self.actual_injection,
            'actual_usage': self.actual_usage,
            'total_usage_high_tariff': self.total_usage_high_tariff,
            'total_usage_low_tariff': self.total_usage_low_tariff,
            'usage_mode': self.usage_mode,
            'power_unit': self.power_unit,
            'energy_unit': self.energy_unit,
            'last_updated': self.last_updated.isoformat()
            if isinstance(self.last_updated, datetime)
            else self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'EnergyFeed':
        last_updated = data.get('last_updated')
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        elif last_updated is None:
            last_updated = datetime.now()

        return cls(
            total_consumption_high_tariff=data.get('total_consumption_high_tariff', ''),
            total_consumption_low_tariff=data.get('total_consumption_low_tariff', ''),
            total_injection_high_tariff=data.get('total_injection_high_tariff', ''),
            total_injection_low_tariff=data.get('total_injection_low_tariff', ''),
            actual_consumption=data.get('actual_consumption', ''),
            actual_injection=data.get('actual_injection', ''),
            actual_usage=data.get('actual_usage', ''),
            total_usage_high_tariff=data.get('total_usage_high_tariff', ''),
            total_usage_low_tariff=data.get('total_usage_low_tariff', ''),
            usage_mode=data.get('usage_mode', 'auto'),
            power_unit=data.get('power_unit', 'kW'),
            energy_unit=data.get('energy_unit', 'kWh'),
            last_updated=last_updated,
        )


@dataclass
class EnergyContractComponent:
    """Base class for energy contract components

    Subclasses must implement calculate_cost() to compute costs.
    """

    name: str = ''
    multiplier: float = 1.0

    def to_dict(self) -> Dict:
        return {
            'type': self.__class__.__name__,
            'name': self.name,
            'multiplier': self.multiplier,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'EnergyContractComponent':
        raise NotImplementedError('Subclasses must implement from_dict')

    def calculate_cost(
        self, period_data: 'EnergyPeriodData', is_monthly: bool = True
    ) -> Tuple[float, 'EnergyCostBreakdown']:
        """Calculate cost for a given energy period

        Args:
            period_data: EnergyPeriodData containing measurements for the period
            is_monthly: True for monthly calculation, False for yearly

        Returns:
            Tuple of (total_cost_in_euros, EnergyCostBreakdown with details)
        """
        raise NotImplementedError('Subclasses must implement calculate_cost')


@dataclass
class ConstantComponent(EnergyContractComponent):
    """Fixed monthly/yearly price component"""

    price_constant: float = 0.0  # € / month or year
    period: str = 'month'  # 'month' or 'year'

    def to_dict(self) -> Dict:
        base = super().to_dict()
        base.update(
            {
                'price_constant': self.price_constant,
                'period': self.period,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: Dict) -> 'ConstantComponent':
        return cls(
            name=data.get('name', ''),
            multiplier=data.get('multiplier', 1.0),
            price_constant=data.get('price_constant', 0.0),
            period=data.get('period', 'month'),
        )

    def calculate_cost(
        self, period_data: 'EnergyPeriodData', is_monthly: bool = True
    ) -> Tuple[float, 'EnergyCostBreakdown']:
        """Calculate constant component cost

        For monthly calculations with a yearly period, divide by 12.
        For yearly calculations with a monthly period, multiply by 12.
        """
        if self.period == 'month':
            # Monthly fee
            if is_monthly:
                cost = self.price_constant * self.multiplier
            else:
                # Yearly calculation: 12 months of fees
                cost = self.price_constant * 12 * self.multiplier
        else:  # yearly
            # Yearly fee
            if is_monthly:
                # Monthly calculation: divide yearly fee by 12
                cost = (self.price_constant / 12) * self.multiplier
            else:
                cost = self.price_constant * self.multiplier

        details = f'{self.price_constant}€/{self.period}'
        if self.multiplier != 1.0:
            details += f' × multiplier {self.multiplier}'
        breakdown = EnergyCostBreakdown(
            component_name=self.name,
            component_type=self.__class__.__name__,
            cost=cost,
            multiplier=self.multiplier,
            details=details,
        )
        return cost, breakdown


@dataclass
class FixedComponent(EnergyContractComponent):
    """Fixed price per kWh component"""

    fixed_price: float = 0.0  # €/kWh
    is_injection_reward: bool = False  # If True, applies to injection instead of consumption
    energy_sensor: str = ENERGY_SENSOR_DEFAULT

    def to_dict(self) -> Dict:
        base = super().to_dict()
        base.update(
            {
                'fixed_price': self.fixed_price,
                'is_injection_reward': self.is_injection_reward,
                'energy_sensor': self.energy_sensor,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: Dict) -> 'FixedComponent':
        return cls(
            name=data.get('name', ''),
            multiplier=data.get('multiplier', 1.0),
            fixed_price=data.get('fixed_price', 0.0),
            is_injection_reward=data.get('is_injection_reward', False),
            energy_sensor=data.get('energy_sensor') or data.get('total_consumption_sensor') or ENERGY_SENSOR_DEFAULT,
        )

    def _resolve_energy_kwh(self, period_data: 'EnergyPeriodData') -> float:
        sensor_key = self.energy_sensor or ENERGY_SENSOR_DEFAULT

        if sensor_key == ENERGY_SENSOR_CONSUMPTION_HIGH_TARIFF:
            return period_data.consumption_high_tariff
        if sensor_key == ENERGY_SENSOR_CONSUMPTION_LOW_TARIFF:
            return period_data.consumption_low_tariff
        if sensor_key == ENERGY_SENSOR_TOTAL_CONSUMPTION:
            return period_data.total_consumption
        if sensor_key == ENERGY_SENSOR_INJECTION_HIGH_TARIFF:
            return period_data.injection_high_tariff
        if sensor_key == ENERGY_SENSOR_INJECTION_LOW_TARIFF:
            return period_data.injection_low_tariff
        if sensor_key == ENERGY_SENSOR_TOTAL_INJECTION:
            return period_data.total_injection

        sensor_history = period_data.sensor_history.get(sensor_key, [])
        if len(sensor_history) <= 1:
            return 0.0

        return sum((entry.get('change') or 0.0) for entry in sensor_history[1:] if (entry.get('change') or 0.0) > 0.0)

    def calculate_cost(
        self, period_data: 'EnergyPeriodData', is_monthly: bool = True
    ) -> Tuple[float, 'EnergyCostBreakdown']:
        energy_kwh = self._resolve_energy_kwh(period_data)

        if self.is_injection_reward:
            cost = -(self.fixed_price) * energy_kwh * self.multiplier
            cost = min(0.0, cost)
        else:
            cost = self.fixed_price * energy_kwh * self.multiplier

        details = f'{self.fixed_price:.4f}€/kWh × {energy_kwh:.2f}kWh'
        if self.multiplier != 1.0:
            details += f' × multiplier {self.multiplier}'
        breakdown = EnergyCostBreakdown(
            component_name=self.name,
            component_type=self.__class__.__name__,
            cost=cost,
            multiplier=self.multiplier,
            details=details,
        )
        return cost, breakdown


@dataclass
class VariableComponent(EnergyContractComponent):
    """Variable price component based on real-time sensor

    Calculates cost using exact integration of Price(t) * Energy_Delta(t)
    """

    variable_price_sensor: str = ''
    variable_price_multiplier: float = 1.0
    variable_price_constant: float = 0.0
    is_injection_reward: bool = False
    energy_sensor: str = ENERGY_SENSOR_DEFAULT

    def to_dict(self) -> Dict:
        base = super().to_dict()
        base.update(
            {
                'variable_price_sensor': self.variable_price_sensor,
                'variable_price_multiplier': self.variable_price_multiplier,
                'variable_price_constant': self.variable_price_constant,
                'is_injection_reward': self.is_injection_reward,
                'energy_sensor': self.energy_sensor,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: Dict) -> 'VariableComponent':
        return cls(
            name=data.get('name', ''),
            multiplier=data.get('multiplier', 1.0),
            variable_price_sensor=data.get('variable_price_sensor', ''),
            variable_price_multiplier=data.get('variable_price_multiplier', 1.0),
            variable_price_constant=data.get('variable_price_constant', 0.0),
            is_injection_reward=data.get('is_injection_reward', False),
            energy_sensor=data.get('energy_sensor') or data.get('total_consumption_sensor') or ENERGY_SENSOR_DEFAULT,
        )

    def calculate_cost(
        self, period_data: 'EnergyPeriodData', is_monthly: bool = True
    ) -> Tuple[float, 'EnergyCostBreakdown']:
        """Calculates cost using 15-minute interval statistics.

        Each 15-minute interval provides:
        - 'mean': average price during the interval (for price sensors)
        - 'change': energy consumed/injected during the interval (for energy sensors)

        Cost for each interval = (mean_price * multiplier + constant) * energy_change
        This eliminates the need for complex integration or interpolation.
        """
        price_history = period_data.sensor_history.get(self.variable_price_sensor, [])
        energy_sensor_key = self.energy_sensor or ENERGY_SENSOR_DEFAULT
        energy_history = period_data.sensor_history.get(energy_sensor_key, [])

        if not price_history or not energy_history:
            return 0.0, EnergyCostBreakdown(
                self.name, self.__class__.__name__, 0.0, self.multiplier, 'No sensor history data available'
            )

        price_by_start = {entry['start']: entry.get('mean') or 0.0 for entry in price_history}

        total_cost = 0.0
        total_energy_delta = 0.0

        # First change value is not reliable
        for entry in energy_history[1:]:
            start = entry['start']
            energy_change = entry.get('change') or 0.0

            if energy_change <= 0:
                continue

            price = price_by_start.get(start, 0.0)

            effective_price = (price * self.variable_price_multiplier) + self.variable_price_constant
            segment_cost = effective_price * energy_change

            total_cost += segment_cost
            total_energy_delta += energy_change

        if self.is_injection_reward:
            final_cost = -total_cost * self.multiplier
            final_cost = min(0.0, final_cost)
        else:
            final_cost = total_cost * self.multiplier

        avg_price_display = (total_cost / total_energy_delta) if total_energy_delta > 0 else 0.0

        details = f'{avg_price_display:.4f}€/kWh × {total_energy_delta:.2f}kWh'
        if self.multiplier != 1.0:
            details += f' × multiplier {self.multiplier}'
        breakdown = EnergyCostBreakdown(
            component_name=self.name,
            component_type=self.__class__.__name__,
            cost=final_cost,
            multiplier=self.multiplier,
            details=details,
        )

        return final_cost, breakdown


@dataclass
class CapacityComponent(EnergyContractComponent):
    """Capacity charge based on maximum power consumption"""

    capacity_price_multiplier: float = 0.0  # €/kW/month or €/kW/year depending on period
    period: str = 'month'  # 'month' or 'year' - defines how the tariff is calculated

    def to_dict(self) -> Dict:
        base = super().to_dict()
        base.update(
            {
                'capacity_price_multiplier': self.capacity_price_multiplier,
                'period': self.period,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: Dict) -> 'CapacityComponent':
        return cls(
            name=data.get('name', ''),
            multiplier=data.get('multiplier', 1.0),
            capacity_price_multiplier=data.get('capacity_price_multiplier', 0.0),
            period=data.get('period', 'month'),
        )

    def calculate_cost(
        self, period_data: 'EnergyPeriodData', is_monthly: bool = True
    ) -> Tuple[float, 'EnergyCostBreakdown']:
        max_power_kw = period_data.max_power_kw
        max_power_timestamp = period_data.max_power_timestamp

        if is_monthly:
            # Monthly: use straight peak power for this month
            if self.period == 'month':
                cost = self.capacity_price_multiplier * max_power_kw * self.multiplier
            else:
                cost = (self.capacity_price_multiplier / 12) * max_power_kw * self.multiplier

            details = (
                f'{self.capacity_price_multiplier:.2f}€/kW/{self.period} × {max_power_kw:.2f}kW ({max_power_timestamp})'
            )
            if self.multiplier != 1.0:
                details += f' × multiplier {self.multiplier}'
        else:
            # Yearly: capacity tariff = average of monthly peaks (TTM)
            # Only months with data are included in the average
            monthly_peaks = period_data.monthly_peak_powers
            peaks_with_data = {m: p for m, p in monthly_peaks.items() if p > 0}

            if peaks_with_data:
                avg_monthly_peak = sum(peaks_with_data.values()) / len(peaks_with_data)
            else:
                avg_monthly_peak = max_power_kw  # fallback to overall max

            if self.period == 'month':
                cost = self.capacity_price_multiplier * 12 * avg_monthly_peak * self.multiplier
            else:
                cost = self.capacity_price_multiplier * avg_monthly_peak * self.multiplier

            months_used = len(peaks_with_data)
            details = f'{self.capacity_price_multiplier:.2f}€/kW/{self.period} × {avg_monthly_peak:.2f}kW (TTM avg of {months_used} month peaks)'
            if self.multiplier != 1.0:
                details += f' × multiplier {self.multiplier}'

        breakdown = EnergyCostBreakdown(
            component_name=self.name,
            component_type=self.__class__.__name__,
            cost=cost,
            multiplier=self.multiplier,
            details=details,
        )
        return cost, breakdown


@dataclass
class PercentageComponent(EnergyContractComponent):
    """Percentage surcharge applied on top of selected other components (e.g. VAT)"""

    percentage: float = 0.0
    applies_to_indices: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict:
        base = super().to_dict()
        base.update(
            {
                'percentage': self.percentage,
                'applies_to_indices': list(self.applies_to_indices),
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: Dict) -> 'PercentageComponent':
        return cls(
            name=data.get('name', ''),
            multiplier=data.get('multiplier', 1.0),
            percentage=data.get('percentage', 0.0),
            applies_to_indices=data.get('applies_to_indices', []),
        )

    def calculate_cost(
        self,
        period_data: 'EnergyPeriodData',
        is_monthly: bool = True,
        component_breakdowns: List['EnergyCostBreakdown'] = None,
    ) -> Tuple[float, 'EnergyCostBreakdown']:
        base_sum = 0.0
        applied_names = []
        if component_breakdowns:
            for idx in self.applies_to_indices:
                if 0 <= idx < len(component_breakdowns) and component_breakdowns[idx] is not None:
                    base_sum += component_breakdowns[idx].cost
                    applied_names.append(component_breakdowns[idx].component_name)

        cost = base_sum * (self.percentage / 100.0) * self.multiplier

        details = f'{self.percentage}% on €{base_sum:.2f}'
        if self.multiplier != 1.0:
            details += f' × multiplier {self.multiplier}'
        breakdown = EnergyCostBreakdown(
            component_name=self.name,
            component_type=self.__class__.__name__,
            cost=cost,
            multiplier=self.multiplier,
            details=details,
        )
        return cost, breakdown

    def adjust_indices_after_removal(self, removed_index: int) -> None:
        self.applies_to_indices = [
            idx - 1 if idx > removed_index else idx for idx in self.applies_to_indices if idx != removed_index
        ]


@dataclass
class EnergyContract:
    """Domain model for energy contract configuration

    A contract consists of multiple components with associated multipliers.
    Multipliers can be any positive value - they are not required to sum to 1.0.
    """

    components: List[EnergyContractComponent] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'components': [comp.to_dict() for comp in self.components],
            'last_updated': self.last_updated.isoformat()
            if isinstance(self.last_updated, datetime)
            else self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'EnergyContract':
        last_updated = data.get('last_updated')
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        elif last_updated is None:
            last_updated = datetime.now()

        components = []
        for comp_data in data.get('components', []):
            comp_type = comp_data.get('type')
            if comp_type == 'ConstantComponent':
                components.append(ConstantComponent.from_dict(comp_data))
            elif comp_type == 'FixedComponent':
                components.append(FixedComponent.from_dict(comp_data))
            elif comp_type == 'VariableComponent':
                components.append(VariableComponent.from_dict(comp_data))
            elif comp_type == 'CapacityComponent':
                components.append(CapacityComponent.from_dict(comp_data))
            elif comp_type == 'PercentageComponent':
                components.append(PercentageComponent.from_dict(comp_data))

        return cls(
            components=components,
            last_updated=last_updated,
        )

    def _calculate_cost(
        self, period_data: 'EnergyPeriodData', is_monthly: bool
    ) -> Tuple[float, List['EnergyCostBreakdown']]:
        total_cost = 0.0
        breakdowns: List['EnergyCostBreakdown'] = [None] * len(self.components)

        for i, component in enumerate(self.components):
            if not isinstance(component, PercentageComponent):
                cost, breakdown = component.calculate_cost(period_data, is_monthly=is_monthly)
                total_cost += cost
                breakdowns[i] = breakdown

        for i, component in enumerate(self.components):
            if isinstance(component, PercentageComponent):
                cost, breakdown = component.calculate_cost(
                    period_data, is_monthly=is_monthly, component_breakdowns=breakdowns
                )
                total_cost += cost
                breakdowns[i] = breakdown

        return total_cost, breakdowns

    def calculate_monthly_cost(self, period_data: 'EnergyPeriodData') -> Tuple[float, List['EnergyCostBreakdown']]:
        return self._calculate_cost(period_data, is_monthly=True)

    def calculate_yearly_cost(self, period_data: 'EnergyPeriodData') -> Tuple[float, List['EnergyCostBreakdown']]:
        return self._calculate_cost(period_data, is_monthly=False)
