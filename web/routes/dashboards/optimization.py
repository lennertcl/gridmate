import logging

from flask import Blueprint, jsonify, render_template, request

from web.model.data.data_connector import DataConnector
from web.model.data.ha_connector import HAConnector
from web.model.optimization.emhass_connector import EmhassConnector, resolve_emhass_url
from web.model.optimization.models import DeviceDayEntry, DeviceSchedule, ScheduleEntry
from web.model.optimization.optimization_manager import OptimizationManager
from web.model.optimization.scheduler import (
    OptimizationDisabledError,
    OptimizationScheduler,
    OptimizerUnavailableError,
)

logger = logging.getLogger(__name__)

dashboard_optimization_bp = Blueprint('dashboard_optimization', __name__)

data_connector = DataConnector()
optimization_manager = OptimizationManager(data_connector)


@dashboard_optimization_bp.route('/dashboard/optimization')
def optimization_dashboard():
    config = optimization_manager.get_config()
    result = optimization_manager.get_latest_result()
    deferrable_loads = optimization_manager.get_deferrable_loads()
    managed_battery = optimization_manager.get_managed_battery()
    devices = data_connector.get_devices()

    logger.debug('Rendering optimization dashboard with config: %s', config)
    logger.debug('Latest optimization result: %s', result)

    device_names = {d.device_id: d.name for d in devices}
    device_defaults = {
        load.device_id: {
            'earliest_start_time': load.earliest_start_time,
            'latest_end_time': load.latest_end_time,
        }
        for load in deferrable_loads
    }

    if result:
        for device_id, schedule in result.device_schedules.items():
            if device_id in device_names:
                schedule.device_name = device_names[device_id]

    battery_schedule = _build_battery_schedule(result) if result else None

    today_schedule = {e.device_id: e for e in config.weekly_schedule.get_today()}
    overrides = {o.device_id: o for o in config.next_run_overrides}
    next_run_time = config.dayahead_schedule_time

    return render_template(
        'dashboard/optimization.html',
        config=config,
        result=result,
        deferrable_loads=deferrable_loads,
        managed_battery=managed_battery,
        device_names=device_names,
        device_defaults=device_defaults,
        battery_schedule=battery_schedule,
        today_schedule=today_schedule,
        overrides=overrides,
        next_run_time=next_run_time,
    )


@dashboard_optimization_bp.route('/api/optimization/status')
def optimization_status():
    config = optimization_manager.get_config()
    ha_connector = HAConnector()
    emhass_url = resolve_emhass_url(config.emhass_url)
    connector = EmhassConnector(emhass_url, ha_connector, data_connector)

    return jsonify(
        {
            'enabled': config.enabled,
            'emhass_available': connector.is_available(),
            'last_run': config.last_optimization_run.isoformat() if config.last_optimization_run else None,
            'last_status': config.last_optimization_status,
            'actuation_mode': config.actuation_mode,
        }
    )


@dashboard_optimization_bp.route('/api/optimization/schedule')
def optimization_schedule():
    result = optimization_manager.get_latest_result()
    if not result:
        return jsonify({'error': 'No optimization result available'}), 404
    return jsonify(result.to_dict())


@dashboard_optimization_bp.route('/api/optimization/run', methods=['POST'])
def run_optimization():
    logger.debug('Running optimization')
    config = optimization_manager.get_config()
    deferrable_loads, load_mapping = optimization_manager.get_effective_deferrable_loads(config)
    ha_connector = HAConnector()
    emhass_url = resolve_emhass_url(config.emhass_url)
    connector = EmhassConnector(emhass_url, ha_connector, data_connector)
    scheduler = OptimizationScheduler(connector, ha_connector, optimization_manager=optimization_manager)

    data = request.get_json(silent=True) or {}
    force_type = data.get('type')
    logger.debug('Optimization run request: %s', data)

    try:
        config.deferrable_loads = deferrable_loads
        config.load_mapping = load_mapping
        sync_ok = optimization_manager.sync_config_to_emhass(config)
        if not sync_ok:
            logger.error('Failed to sync EMHASS config before optimization run')
            return jsonify({'error': 'Failed to sync configuration to EMHASS'}), 500
        logger.debug('EMHASS config synced before optimization run')

        result = scheduler.run_scheduled_optimization(config, deferrable_loads, force_type=force_type)
        optimization_manager.save_config(config)
        response = {
            'success': True,
            'optimization_type': result.optimization_type,
            'total_cost_eur': result.total_cost_eur,
            'timestamp': result.timestamp.isoformat(),
        }
        logger.debug('Optimization run response: %s', response)
        return jsonify(response)
    except OptimizationDisabledError:
        logger.error('Optimization run failed: Optimization is disabled')
        return jsonify({'error': 'Optimization is disabled'}), 400
    except OptimizerUnavailableError:
        logger.error('Optimization run failed: Optimizer is unavailable')
        return jsonify({'error': 'EMHASS is not reachable'}), 503
    except Exception as e:
        logger.error(f'Optimization failed: {e}')
        config.last_optimization_status = f'error: {str(e)}'
        optimization_manager.save_config(config)
        return jsonify({'error': str(e)}), 500


@dashboard_optimization_bp.route('/api/optimization/device/<device_id>/override', methods=['POST'])
def set_device_override(device_id):
    config = optimization_manager.get_config()
    data = request.get_json(silent=True) or {}

    num_cycles = int(data.get('num_cycles', 1))
    hours_between = float(data.get('hours_between_runs', 0.0))
    earliest_start = data.get('earliest_start_time', '')
    latest_end = data.get('latest_end_time', '')

    override = DeviceDayEntry(
        device_id=device_id,
        num_cycles=num_cycles,
        hours_between_runs=hours_between,
        earliest_start_time=earliest_start,
        latest_end_time=latest_end,
    )

    config.next_run_overrides = [o for o in config.next_run_overrides if o.device_id != device_id]
    config.next_run_overrides.append(override)
    optimization_manager.save_config(config)

    return jsonify({'success': True, 'device_id': device_id, 'override': override.to_dict()})


@dashboard_optimization_bp.route('/api/optimization/device/<device_id>/clear-override', methods=['POST'])
def clear_device_override(device_id):
    config = optimization_manager.get_config()
    config.next_run_overrides = [o for o in config.next_run_overrides if o.device_id != device_id]
    optimization_manager.save_config(config)

    return jsonify({'success': True, 'device_id': device_id})


def _build_battery_schedule(result):
    points = result.battery_power_forecast
    if not points:
        return None

    entries = []
    current_start = None
    block_values = []
    current_sign = None

    for point in points:
        value = -point.value
        is_zero = abs(value) < 0.001
        sign = 'charge' if value > 0 else 'discharge'

        if is_zero:
            if current_start is not None:
                avg_power = sum(block_values) / len(block_values)
                entries.append(
                    ScheduleEntry(
                        start_time=current_start,
                        end_time=point.timestamp,
                        power_w=avg_power,
                        is_active=True,
                    )
                )
                current_start = None
                block_values = []
                current_sign = None
        elif current_start is None or sign != current_sign:
            if current_start is not None:
                avg_power = sum(block_values) / len(block_values)
                entries.append(
                    ScheduleEntry(
                        start_time=current_start,
                        end_time=point.timestamp,
                        power_w=avg_power,
                        is_active=True,
                    )
                )
            current_start = point.timestamp
            block_values = [value]
            current_sign = sign
        else:
            block_values.append(value)

    if current_start is not None and points:
        avg_power = sum(block_values) / len(block_values)
        entries.append(
            ScheduleEntry(
                start_time=current_start,
                end_time=points[-1].timestamp,
                power_w=avg_power,
                is_active=True,
            )
        )

    schedule = DeviceSchedule(device_id='battery', device_name='Battery')
    schedule.schedule_entries = entries
    return schedule
