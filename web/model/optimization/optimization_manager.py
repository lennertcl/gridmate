import logging
from typing import Dict, List, Optional

from web.model.optimization.models import (
    BatteryOptimizationConfig,
    DeferrableLoadConfig,
    OptimizationConfig,
    OptimizationResult,
)
from web.model.optimization.result_store import OptimizationResultStore

logger = logging.getLogger(__name__)


class OptimizationManager:
    def __init__(self, data_connector):
        self.connector = data_connector
        self.result_store = OptimizationResultStore()

    def get_config(self) -> OptimizationConfig:
        return self.connector.get_optimization_config()

    def save_config(self, config: OptimizationConfig) -> None:
        self.connector.set_optimization_config(config)

    def get_deferrable_loads(self) -> List[DeferrableLoadConfig]:
        devices = self.connector.get_devices()
        loads = []
        for device in devices:
            if 'deferrable_load' not in device.get_all_type_ids():
                continue
            loads.append(DeferrableLoadConfig.from_device(device))

        loads.sort(key=lambda l: l.priority)
        return loads

    def get_enabled_deferrable_loads(self) -> List[DeferrableLoadConfig]:
        loads = self.get_deferrable_loads()
        return [l for l in loads if l.enabled]

    def get_managed_battery(self) -> Optional[BatteryOptimizationConfig]:
        devices = self.connector.get_devices()
        for device in devices:
            if 'home_battery' in device.get_all_type_ids():
                capacity = float(device.custom_parameters.get('capacity_kwh', 0))
                if capacity > 0:
                    return BatteryOptimizationConfig.from_device(device)
        return None

    def get_latest_result(self) -> Optional[OptimizationResult]:
        return self.result_store.get_latest_result()

    def _resolve_emhass_url(self, config: OptimizationConfig) -> str:
        from web.model.optimization.emhass_connector import resolve_emhass_url

        return resolve_emhass_url(config.emhass_url)

    def sync_config_to_emhass(self, config: OptimizationConfig) -> bool:
        from web.model.data.ha_connector import HAConnector
        from web.model.optimization.emhass_connector import EmhassConnector

        deferrable_loads = self.get_enabled_deferrable_loads()
        config.deferrable_loads = deferrable_loads

        ha_connector = HAConnector()
        connector = EmhassConnector(self._resolve_emhass_url(config), ha_connector, self.connector)
        config_dict = connector.build_emhass_config_dict(config)
        logger.debug('Syncing EMHASS config: %s', config_dict)
        return connector.set_emhass_config(config_dict)

    def get_emhass_config(self, config: OptimizationConfig) -> Optional[Dict]:
        from web.model.data.ha_connector import HAConnector
        from web.model.optimization.emhass_connector import EmhassConnector

        ha_connector = HAConnector()
        connector = EmhassConnector(self._resolve_emhass_url(config), ha_connector, self.connector)
        return connector.get_emhass_config()
