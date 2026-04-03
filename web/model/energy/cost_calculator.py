"""
Cost Calculator Service for Energy Costs Dashboard

Calculates energy costs based on meter readings and energy contracts.
Supports monthly and yearly cost calculations with detailed breakdowns.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .models import EnergyContract, EnergyCostBreakdown, EnergyPeriodData


class CostCalculationService:
    """Service to calculate energy costs from meter readings and contracts"""

    def __init__(self, energy_contract: Optional[EnergyContract] = None):
        """Initialize with an optional energy contract

        Args:
            energy_contract: EnergyContract instance for cost calculation
        """
        self.contract = energy_contract or EnergyContract()

    def get_month_date_range(self, year: int, month: int) -> Tuple[date, date]:
        """Get start and end dates for a given month

        Args:
            year: The year
            month: The month (1-12)

        Returns:
            Tuple of (start_date, end_date)
        """
        start_date = date(year, month, 1)

        # Last day of month
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        return start_date, end_date

    def get_year_date_range(self, year: int) -> Tuple[date, date]:
        """Get start and end dates for a given year

        Args:
            year: The year

        Returns:
            Tuple of (start_date, end_date)
        """
        return date(year, 1, 1), date(year, 12, 31)

    def calculate_monthly_costs(self, period_data: EnergyPeriodData) -> Tuple[float, List[EnergyCostBreakdown]]:
        """Calculate monthly costs with breakdown

        Args:
            period_data: Energy measurements for the month

        Returns:
            Tuple of (total_cost_euros, list_of_breakdowns)
        """
        if not self.contract or not self.contract.components:
            return 0.0, []

        return self.contract.calculate_monthly_cost(period_data)

    def calculate_yearly_costs(self, period_data: EnergyPeriodData) -> Tuple[float, List[EnergyCostBreakdown]]:
        """Calculate yearly costs with breakdown

        Args:
            period_data: Energy measurements for the year

        Returns:
            Tuple of (total_cost_euros, list_of_breakdowns)
        """
        if not self.contract or not self.contract.components:
            return 0.0, []

        return self.contract.calculate_yearly_cost(period_data)

    def get_cost_summary(self, period_data: EnergyPeriodData, is_monthly: bool = True) -> Dict:
        """Get comprehensive cost summary including breakdown and totals

        Args:
            period_data: Energy period data
            is_monthly: True for monthly, False for yearly

        Returns:
            Dictionary with cost analysis
        """
        if is_monthly:
            total_cost, breakdowns = self.calculate_monthly_costs(period_data)
            period_text = 'month'
        else:
            total_cost, breakdowns = self.calculate_yearly_costs(period_data)
            period_text = 'year'

        # Group costs by component type
        cost_by_type = {}
        for breakdown in breakdowns:
            if breakdown.component_type not in cost_by_type:
                cost_by_type[breakdown.component_type] = []
            cost_by_type[breakdown.component_type].append(breakdown)

        return {
            'total_cost': round(total_cost, 2),
            'total_consumption': round(period_data.get_total_consumption(), 2),
            'total_injection': round(period_data.get_total_injection(), 2),
            'breakdowns': [b.to_dict() for b in breakdowns],
            'cost_by_type': {
                component_type: sum(b.cost for b in breakdowns_list)
                for component_type, breakdowns_list in cost_by_type.items()
            },
            'period': period_text,
        }

    def get_meter_readings_summary(self, period_data: EnergyPeriodData) -> Dict:
        return {
            'consumption_high_tariff': round(period_data.consumption_high_tariff, 2),
            'consumption_low_tariff': round(period_data.consumption_low_tariff, 2),
            'total_consumption': round(period_data.get_total_consumption(), 2),
            'injection_high_tariff': round(period_data.injection_high_tariff, 2),
            'injection_low_tariff': round(period_data.injection_low_tariff, 2),
            'total_injection': round(period_data.get_total_injection(), 2),
            'max_power_kw': round(period_data.max_power_kw, 2),
            'max_power_timestamp': period_data.max_power_timestamp,
            'consumption_high_start': round(period_data.consumption_high_start, 2),
            'consumption_high_end': round(period_data.consumption_high_end, 2),
            'consumption_low_start': round(period_data.consumption_low_start, 2),
            'consumption_low_end': round(period_data.consumption_low_end, 2),
            'injection_high_start': round(period_data.injection_high_start, 2),
            'injection_high_end': round(period_data.injection_high_end, 2),
            'injection_low_start': round(period_data.injection_low_start, 2),
            'injection_low_end': round(period_data.injection_low_end, 2),
        }

    def get_daily_evolution(self, period_data: EnergyPeriodData, energy_feed) -> List[Dict]:
        daily_data = defaultdict(
            lambda: {
                'consumption_high': 0.0,
                'consumption_low': 0.0,
                'injection_high': 0.0,
                'injection_low': 0.0,
                'max_power': 0.0,
            }
        )

        sensor_map = {
            energy_feed.total_consumption_high_tariff: 'consumption_high',
            energy_feed.total_consumption_low_tariff: 'consumption_low',
            energy_feed.total_injection_high_tariff: 'injection_high',
            energy_feed.total_injection_low_tariff: 'injection_low',
        }

        for sensor_id, key in sensor_map.items():
            if not sensor_id:
                continue
            entries = period_data.sensor_history.get(sensor_id, [])
            for entry in entries:
                start_ms = entry.get('start', 0)
                if not start_ms:
                    continue
                day = datetime.fromtimestamp(start_ms / 1000.0).strftime('%Y-%m-%d')
                if entry.get('change') > 10000:
                    continue
                daily_data[day][key] += entry.get('change') or 0.0

        power_sensor = energy_feed.actual_consumption
        if power_sensor:
            power_entries = period_data.sensor_history.get(power_sensor, [])
            for entry in power_entries:
                start_ms = entry.get('start', 0)
                if not start_ms:
                    continue
                day = datetime.fromtimestamp(start_ms / 1000.0).strftime('%Y-%m-%d')
                mean_val = entry.get('mean') or 0.0
                if mean_val > daily_data[day]['max_power']:
                    daily_data[day]['max_power'] = mean_val

        sorted_days = sorted(daily_data.keys())
        result = []

        for day in sorted_days:
            result.append(
                {
                    'date': day,
                    'consumption_high': round(daily_data[day]['consumption_high'], 2),
                    'consumption_low': round(daily_data[day]['consumption_low'], 2),
                    'injection_high': round(daily_data[day]['injection_high'], 2),
                    'injection_low': round(daily_data[day]['injection_low'], 2),
                    'max_power': round(daily_data[day]['max_power'], 3),
                }
            )

        return result
