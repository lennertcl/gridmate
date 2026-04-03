import logging
from datetime import datetime

from web.model.data.ha_connector import HAConnector
from web.model.optimization.connector import OptimizerConnector
from web.model.optimization.models import (
    OptimizationConfig,
    OptimizationResult,
)
from web.model.optimization.result_store import OptimizationResultStore

logger = logging.getLogger(__name__)


class OptimizationDisabledError(Exception):
    pass


class OptimizerUnavailableError(Exception):
    pass


class OptimizationScheduler:
    def __init__(
        self, connector: OptimizerConnector, ha_connector: HAConnector, result_store: OptimizationResultStore = None
    ):
        self.connector = connector
        self.ha = ha_connector
        self.result_store = result_store or OptimizationResultStore()

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
        elif config.actuation_mode == 'notify':
            self._send_notifications(result)

        config.last_optimization_run = datetime.now()
        config.last_optimization_status = 'success'

        return result

    def _actuate_devices(self, result: OptimizationResult) -> None:
        now = datetime.now()
        for device_id, schedule in result.device_schedules.items():
            should_be_on = False
            for entry in schedule.schedule_entries:
                if entry.start_time <= now <= entry.end_time and entry.is_active:
                    should_be_on = True
                    break

            self._control_device(device_id, should_be_on)

    def _control_device(self, device_id: str, turn_on: bool) -> None:
        from web.model.data.data_connector import DataConnector

        data_connector = DataConnector()
        device = data_connector.get_device(device_id)

        if not device:
            logger.warning(f'Device {device_id} not found for actuation')
            return

        control_entity = device.custom_parameters.get('control_entity', '')
        if not control_entity:
            logger.warning(f'Device {device_id} has no control_entity')
            return

        try:
            domain = control_entity.split('.')[0]
            service = 'turn_on' if turn_on else 'turn_off'
            self.ha.call_service(domain, service, {'entity_id': control_entity})
        except Exception as e:
            logger.error(f'Failed to actuate {device_id}: {e}')

    def _send_notifications(self, result: OptimizationResult) -> None:
        now = datetime.now()
        for device_id, schedule in result.device_schedules.items():
            for entry in schedule.schedule_entries:
                if entry.is_active and entry.start_time > now:
                    minutes_until = int((entry.start_time - now).total_seconds() / 60)
                    if minutes_until <= 30:
                        logger.info(
                            f'Notification: {schedule.device_name} scheduled to start '
                            f'at {entry.start_time.strftime("%H:%M")}'
                        )
