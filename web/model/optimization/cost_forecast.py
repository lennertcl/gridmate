from datetime import datetime, timedelta
from typing import Any, Dict, List

from web.model.data.data_connector import DataConnector, PriceProviderManager
from web.model.data.ha_connector import HAConnector


class CostForecastService:
    def build_load_cost_forecast(self, ha_connector: HAConnector, time_step: int, horizon_hours: int) -> List[float]:
        return self._build_price_forecast(
            ha_connector=ha_connector,
            time_step=time_step,
            horizon_hours=horizon_hours,
            is_injection_reward=False,
        )

    def build_prod_price_forecast(self, ha_connector: HAConnector, time_step: int, horizon_hours: int) -> List[float]:
        return self._build_price_forecast(
            ha_connector=ha_connector,
            time_step=time_step,
            horizon_hours=horizon_hours,
            is_injection_reward=True,
        )

    def _build_price_forecast(
        self,
        ha_connector: HAConnector,
        time_step: int,
        horizon_hours: int,
        is_injection_reward: bool,
    ) -> List[float]:
        data_connector = DataConnector()
        contract = data_connector.get_energy_contract()

        if not contract or not contract.components:
            return []

        price_provider_manager = PriceProviderManager(data_connector)
        price_providers = self._build_price_provider_map(contract.components, price_provider_manager)
        timestamps = self._build_timestamps(time_step, horizon_hours)
        components = [
            component
            for component in contract.components
            if getattr(component, 'is_injection_reward', False) == is_injection_reward
        ]

        return [
            round(
                sum(
                    component.calculate_kwh_unit_price(
                        timestamp,
                        ha_connector=ha_connector,
                        price_providers=price_providers,
                    )
                    for component in components
                ),
                6,
            )
            for timestamp in timestamps
        ]

    def _build_timestamps(self, time_step: int, horizon_hours: int) -> List[datetime]:
        now = datetime.now()
        num_steps = (horizon_hours * 60) // time_step
        return [now + timedelta(minutes=i * time_step) for i in range(num_steps)]

    def _build_price_provider_map(self, components: List[Any], manager: PriceProviderManager) -> Dict[str, Any]:
        price_provider_names = {
            component.price_provider_name for component in components if getattr(component, 'price_provider_name', '')
        }
        return {provider_name: manager.get_by_name(provider_name) for provider_name in price_provider_names}
