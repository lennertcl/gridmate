import logging
from datetime import datetime, timedelta
from typing import Dict, List

from web.model.data.data_connector import DataConnector
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
        timestamps = [now + timedelta(minutes=i * time_step) for i in range(num_steps)]

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
            if vc.variable_price_sensor:
                prices = self._get_price_forecast(ha_connector, vc.variable_price_sensor, timestamps)
                forecast_prices[vc.variable_price_sensor] = prices

        cost_forecast = []
        for i, ts in enumerate(timestamps):
            costs_by_index: Dict[int, float] = {}

            for vc in variable_components:
                prices = forecast_prices.get(vc.variable_price_sensor, [])
                price = prices[i] if i < len(prices) else 0.0
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
        timestamps = [now + timedelta(minutes=i * time_step) for i in range(num_steps)]

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
            if vc.variable_price_sensor:
                prices = self._get_price_forecast(ha_connector, vc.variable_price_sensor, timestamps)
                forecast_prices[vc.variable_price_sensor] = prices

        price_forecast = []
        for i, ts in enumerate(timestamps):
            costs_by_index: Dict[int, float] = {}

            for vc in variable_injection:
                prices = forecast_prices.get(vc.variable_price_sensor, [])
                price = prices[i] if i < len(prices) else 0.0
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

    def _get_price_forecast(self, ha_connector, sensor_id: str, timestamps: List[datetime]) -> List[float]:
        state_data = ha_connector.get_state(sensor_id)
        if not state_data:
            return self._fallback_price_forecast(ha_connector, sensor_id, timestamps)

        attributes = state_data.get('attributes', {})
        forecast_data = attributes.get('forecast', [])

        if not forecast_data:
            forecast_data = attributes.get('forecasts', [])

        if not forecast_data:
            return self._fallback_price_forecast(ha_connector, sensor_id, timestamps)

        forecast_by_hour = {}
        for entry in forecast_data:
            if isinstance(entry, dict):
                ts_str = entry.get('start_time') or entry.get('start') or entry.get('datetime')
                value = entry.get('native_value') or entry.get('value') or entry.get('price')
                if ts_str and value is not None:
                    try:
                        ts = datetime.fromisoformat(str(ts_str).replace('Z', '+00:00'))
                        if ts.tzinfo is not None:
                            ts = ts.astimezone(tz=None)
                        forecast_by_hour[ts.replace(minute=0, second=0, microsecond=0, tzinfo=None)] = float(value)
                    except (ValueError, TypeError):
                        continue

        current_price = 0.0
        try:
            current_price = float(state_data.get('state', 0))
        except (ValueError, TypeError):
            pass

        prices = []
        for ts in timestamps:
            hour_key = ts.replace(minute=0, second=0, microsecond=0)
            if hour_key in forecast_by_hour:
                prices.append(forecast_by_hour[hour_key])
            else:
                prices.append(current_price)

        return prices

    def _fallback_price_forecast(self, ha_connector, sensor_id: str, timestamps: List[datetime]) -> List[float]:
        now = datetime.now()
        start_24h_ago = now - timedelta(hours=24)

        history = ha_connector.get_history(
            [sensor_id], start_24h_ago, now, minimal_response=False, significant_changes_only=False
        )

        if not history or not history[0]:
            current_state = ha_connector.get_state(sensor_id)
            if current_state:
                try:
                    val = float(current_state.get('state', 0))
                    return [val] * len(timestamps)
                except (ValueError, TypeError):
                    pass
            return [0.0] * len(timestamps)

        history_by_hour = {}
        for entry in history[0]:
            try:
                ts = datetime.fromisoformat(entry.get('last_changed', '').replace('Z', '+00:00'))
                if ts.tzinfo is not None:
                    ts = ts.astimezone(tz=None)
                val = float(entry.get('state', 0))
                history_by_hour[ts.replace(minute=0, second=0, microsecond=0, tzinfo=None)] = val
            except (ValueError, TypeError):
                continue

        prices = []
        for ts in timestamps:
            look_back = (ts - timedelta(hours=24)).replace(minute=0, second=0, microsecond=0)
            if look_back in history_by_hour:
                prices.append(history_by_hour[look_back])
            elif history_by_hour:
                closest = min(history_by_hour.keys(), key=lambda k: abs((k - look_back).total_seconds()))
                prices.append(history_by_hour[closest])
            else:
                prices.append(0.0)

        return prices
