import logging
from datetime import datetime, timedelta
from typing import Dict, List

from web.model.data.data_connector import DataConnector, PriceProviderManager
from web.model.data.ha_connector import HAConnector
from web.model.energy.models import (
    FixedComponent,
    PercentageComponent,
    VariableComponent,
)

logger = logging.getLogger(__name__)


class CostForecastService:
    def build_load_cost_forecast(self, ha_connector: HAConnector, time_step: int, horizon_hours: int) -> List[float]:
        data_connector = DataConnector()
        contract = data_connector.get_energy_contract()

        if not contract or not contract.components:
            return []

        now = datetime.now()
        num_steps = (horizon_hours * 60) // time_step
        start = now
        end = now + timedelta(minutes=(num_steps - 1) * time_step)
        timestamps = [now + timedelta(minutes=i * time_step) for i in range(num_steps)]

        price_provider_manager = PriceProviderManager(data_connector)

        component_indices: Dict[int, int] = {}
        variable_components = []
        fixed_components = []
        percentage_components = []

        for idx, c in enumerate(contract.components):
            if isinstance(c, VariableComponent) and not c.is_injection_reward:
                component_indices[id(c)] = idx
                variable_components.append(c)
            elif isinstance(c, FixedComponent) and not c.is_injection_reward:
                component_indices[id(c)] = idx
                fixed_components.append(c)
            elif isinstance(c, PercentageComponent):
                percentage_components.append(c)

        forecast_prices = {}
        for vc in variable_components:
            provider = price_provider_manager.get_by_name(vc.price_provider_name)
            if provider:
                prices = provider.get_kwh_prices(start, end, ha_connector)
                forecast_prices[vc.price_provider_name] = prices

        cost_forecast = []
        for i, ts in enumerate(timestamps):
            costs_by_index: Dict[int, float] = {}

            for vc in variable_components:
                prices = forecast_prices.get(vc.price_provider_name, {})
                ts_ms = int(ts.timestamp() * 1000)
                price = self._find_closest_price(prices, ts_ms)
                effective_price = (price * vc.variable_price_multiplier) + vc.variable_price_constant
                costs_by_index[component_indices[id(vc)]] = effective_price * vc.multiplier

            for fc in fixed_components:
                costs_by_index[component_indices[id(fc)]] = fc.fixed_price * fc.multiplier

            marginal_cost = sum(costs_by_index.values())

            for pc in percentage_components:
                base = sum(costs_by_index.get(idx, 0.0) for idx in pc.applies_to_indices)
                marginal_cost += base * (pc.percentage / 100.0) * pc.multiplier

            cost_forecast.append(round(marginal_cost, 6))

        return cost_forecast

    def build_prod_price_forecast(self, ha_connector: HAConnector, time_step: int, horizon_hours: int) -> List[float]:
        data_connector = DataConnector()
        contract = data_connector.get_energy_contract()

        if not contract or not contract.components:
            return []

        now = datetime.now()
        num_steps = (horizon_hours * 60) // time_step
        start = now
        end = now + timedelta(minutes=(num_steps - 1) * time_step)
        timestamps = [now + timedelta(minutes=i * time_step) for i in range(num_steps)]

        price_provider_manager = PriceProviderManager(data_connector)

        component_indices: Dict[int, int] = {}
        variable_injection = []
        fixed_injection = []
        percentage_components = []

        for idx, c in enumerate(contract.components):
            if isinstance(c, VariableComponent) and c.is_injection_reward:
                component_indices[id(c)] = idx
                variable_injection.append(c)
            elif isinstance(c, FixedComponent) and c.is_injection_reward:
                component_indices[id(c)] = idx
                fixed_injection.append(c)
            elif isinstance(c, PercentageComponent):
                percentage_components.append(c)

        forecast_prices = {}
        for vc in variable_injection:
            provider = price_provider_manager.get_by_name(vc.price_provider_name)
            if provider:
                prices = provider.get_kwh_prices(start, end, ha_connector)
                forecast_prices[vc.price_provider_name] = prices

        price_forecast = []
        for i, ts in enumerate(timestamps):
            costs_by_index: Dict[int, float] = {}

            for vc in variable_injection:
                prices = forecast_prices.get(vc.price_provider_name, {})
                ts_ms = int(ts.timestamp() * 1000)
                price = self._find_closest_price(prices, ts_ms)
                effective_price = (price * vc.variable_price_multiplier) + vc.variable_price_constant
                costs_by_index[component_indices[id(vc)]] = effective_price * vc.multiplier

            for fc in fixed_injection:
                costs_by_index[component_indices[id(fc)]] = abs(fc.fixed_price) * fc.multiplier

            marginal_price = sum(costs_by_index.values())

            for pc in percentage_components:
                base = sum(costs_by_index.get(idx, 0.0) for idx in pc.applies_to_indices)
                marginal_price += base * (pc.percentage / 100.0) * pc.multiplier

            price_forecast.append(round(marginal_price, 6))

        return price_forecast

    def _find_closest_price(self, prices: Dict[int, float], target_ms: int) -> float:
        if not prices:
            return 0.0
        if target_ms in prices:
            return prices[target_ms] or 0.0
        closest_key = min(prices.keys(), key=lambda k: abs(k - target_ms))
        return prices[closest_key] or 0.0
