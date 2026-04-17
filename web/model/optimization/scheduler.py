import logging
from datetime import datetime

from web.model.data.data_connector import DataConnector
from web.model.data.ha_connector import HAConnector
from web.model.optimization.connector import OptimizerConnector
from web.model.optimization.ha_automation_manager import HAAutomationManager
from web.model.optimization.models import (
    OptimizationConfig,
    OptimizationResult,
)
from web.model.optimization.optimization_manager import OptimizationManager
from web.model.optimization.result_store import OptimizationResultStore

logger = logging.getLogger(__name__)


class OptimizationDisabledError(Exception):
    pass


class OptimizerUnavailableError(Exception):
    pass


class OptimizationScheduler:
    def __init__(
        self,
        connector: OptimizerConnector,
        ha_connector: HAConnector,
        result_store: OptimizationResultStore = None,
        optimization_manager: OptimizationManager = None,
    ):
        self.connector = connector
        self.ha = ha_connector
        self.result_store = result_store or OptimizationResultStore()
        self.optimization_manager = optimization_manager

    def run_scheduled_optimization(
        self, config: OptimizationConfig, deferrable_loads: list = None, force_type: str = None
    ) -> OptimizationResult:
        if not config.enabled:
            raise OptimizationDisabledError('Optimization is not enabled')

        if not self.connector.is_available():
            raise OptimizerUnavailableError('Optimization backend is not reachable')

        config.deferrable_loads = deferrable_loads or []

        opt_type = force_type or 'dayahead'

        if opt_type == 'dayahead':
            result = self.connector.run_dayahead_optimization(config)
        else:
            result = self.connector.run_mpc_optimization(config)

        self.result_store.save_result(result)

        logger.debug(f'Optimization result saved: {result.to_dict()}')

        if config.actuation_mode == 'automatic':
            self._actuate_devices(result)

        config.last_optimization_run = datetime.now()
        config.last_optimization_status = 'success'

        if self.optimization_manager and config.next_run_overrides:
            self.optimization_manager.clear_next_run_overrides(config)

        return result

    def _actuate_devices(self, result: OptimizationResult) -> None:
        data_connector = DataConnector()
        automation_manager = HAAutomationManager(self.ha, data_connector)
        try:
            automation_manager.sync_device_automations(result)
            logger.info('Device automations synced to Home Assistant')
        except Exception as e:
            logger.error(f'Failed to sync device automations: {e}')
