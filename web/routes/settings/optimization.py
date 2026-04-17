import json
import logging
import os

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from web.forms.optimization import OptimizationSettingsForm
from web.model.data.data_connector import DataConnector
from web.model.data.ha_connector import HAConnector
from web.model.optimization.emhass_connector import EmhassConnector, resolve_emhass_url
from web.model.optimization.ha_automation_manager import HAAutomationManager
from web.model.optimization.models import LoadPowerConfig, LoadPowerScheduleBlock, WeeklySchedule
from web.model.optimization.optimization_manager import OptimizationManager

logger = logging.getLogger(__name__)

settings_optimization_bp = Blueprint('settings_optimization', __name__)

data_connector = DataConnector()
optimization_manager = OptimizationManager(data_connector)


@settings_optimization_bp.route('/settings/optimization', methods=['GET', 'POST'])
def optimization_settings():
    form = OptimizationSettingsForm()
    config = optimization_manager.get_config()

    if form.validate_on_submit():
        config.emhass_url = form.emhass_url.data or ''
        config.enabled = form.enabled.data
        config.dayahead_schedule_time = form.dayahead_schedule_time.data or '05:30'
        config.max_grid_import_w = form.max_grid_import_w.data or 9000
        config.max_grid_export_w = form.max_grid_export_w.data or 9000
        config.actuation_mode = form.actuation_mode.data

        load_power_config = LoadPowerConfig(
            source_type=form.load_power_source_type.data or 'sensor',
            sensor_entity=form.load_power_sensor_entity.data or '',
        )

        schedule_json = request.form.get('load_power_schedule_blocks', '[]')
        try:
            blocks_data = json.loads(schedule_json)
            load_power_config.schedule_blocks = [LoadPowerScheduleBlock.from_dict(b) for b in blocks_data]
        except (json.JSONDecodeError, TypeError):
            load_power_config.schedule_blocks = []

        config.load_power_config = load_power_config

        weekly_schedule_json = request.form.get('weekly_schedule_data', '{}')
        try:
            schedule_data = json.loads(weekly_schedule_json)
            config.weekly_schedule = WeeklySchedule.from_dict(schedule_data)
        except (json.JSONDecodeError, TypeError):
            pass

        optimization_manager.save_config(config)
        optimization_manager.sync_config_to_emhass(config)

        ha_connector = HAConnector()
        automation_manager = HAAutomationManager(ha_connector, data_connector)

        if config.enabled:
            automation_manager.ensure_trigger_automation(config)
            if config.actuation_mode != 'automatic':
                automation_manager.cleanup_device_automations()
        else:
            automation_manager.cleanup_all_automations()

        flash('Optimization settings saved successfully!', 'success')
        return redirect(url_for('settings_optimization.optimization_settings'))

    is_local_dev = os.environ.get('LOCAL_DEV', '').lower() == 'true'
    prefill_emhass_url = resolve_emhass_url('')

    if request.method == 'GET':
        form.emhass_url.data = config.emhass_url or ''
        form.enabled.data = config.enabled
        form.dayahead_schedule_time.data = config.dayahead_schedule_time
        form.max_grid_import_w.data = config.max_grid_import_w
        form.max_grid_export_w.data = config.max_grid_export_w
        form.actuation_mode.data = config.actuation_mode
        form.load_power_source_type.data = config.load_power_config.source_type
        form.load_power_sensor_entity.data = config.load_power_config.sensor_entity

    deferrable_loads = optimization_manager.get_deferrable_loads()
    devices = data_connector.get_devices()
    device_names = {d.device_id: d.name for d in devices}
    device_defaults = {
        load.device_id: {
            'earliest_start_time': load.earliest_start_time,
            'latest_end_time': load.latest_end_time,
        }
        for load in deferrable_loads
    }

    return render_template(
        'settings/optimization.html',
        form=form,
        config=config,
        schedule_blocks_json=json.dumps([b.to_dict() for b in config.load_power_config.schedule_blocks]),
        weekly_schedule_json=json.dumps(config.weekly_schedule.to_dict()),
        deferrable_loads=deferrable_loads,
        device_names=device_names,
        device_defaults_json=json.dumps(device_defaults),
        prefill_emhass_url=prefill_emhass_url,
        is_addon_mode=not is_local_dev,
    )


@settings_optimization_bp.route('/api/optimization/emhass/status')
def emhass_status():
    url = request.args.get('url')
    if not url:
        config = optimization_manager.get_config()
        url = resolve_emhass_url(config.emhass_url)
    ha_connector = HAConnector()
    connector = EmhassConnector(url, ha_connector)
    available = connector.is_available()
    return jsonify({'available': available, 'url': url})


@settings_optimization_bp.route('/api/optimization/emhass/config')
def emhass_config():
    config = optimization_manager.get_config()
    emhass_cfg = optimization_manager.get_emhass_config(config)
    if emhass_cfg is None:
        return jsonify({'error': 'Could not fetch EMHASS config'}), 503
    return jsonify(emhass_cfg)


@settings_optimization_bp.route('/api/optimization/device/<device_id>/toggle', methods=['POST'])
def toggle_device_optimization(device_id):
    device = data_connector.get_device(device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404

    current = device.custom_parameters.get('opt_enabled', True)
    device.custom_parameters['opt_enabled'] = not current
    data_connector.update_device(device_id, device)

    return jsonify(
        {
            'success': True,
            'device_id': device_id,
            'opt_enabled': not current,
        }
    )
