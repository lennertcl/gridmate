from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from web.forms import (
    AddDeviceForm,
    EditDeviceForm,
    SolarConfigForm,
)
from web.model.data.data_connector import DataConnector, DeviceManager, DeviceTypeManager, SolarManager

data_connector = DataConnector()
device_manager = DeviceManager(data_connector)
device_type_manager = DeviceTypeManager(data_connector)
solar_manager = SolarManager(data_connector)

settings_device_bp = Blueprint('settings_device', __name__)


@settings_device_bp.route('/settings/devices', methods=['GET', 'POST'])
def devices():
    devices = device_manager.list_all_devices()
    type_registry = device_type_manager.get_registry()
    return render_template('settings/device/devices.html', devices=devices, type_registry=type_registry)


@settings_device_bp.route('/settings/edit-device/<device_id>', methods=['GET', 'POST'])
def edit_device(device_id):
    device = device_manager.get_device(device_id)
    if not device:
        flash('Device not found.', 'error')
        return redirect(url_for('settings_device.devices'))

    type_registry = device_type_manager.get_registry()
    form = EditDeviceForm()
    form.primary_type.choices = device_type_manager.get_type_choices()

    if form.validate_on_submit():
        primary_type = form.primary_type.data
        secondary_types = request.form.getlist('secondary_types')
        secondary_types = [t for t in secondary_types if t != primary_type]

        all_type_ids = [primary_type] + secondary_types
        combined_params = {}
        for tid in all_type_ids:
            dt = type_registry.get(tid)
            if dt:
                combined_params.update(dt.custom_parameters)

        custom_parameters = {}
        for param_name, param_def in combined_params.items():
            if param_def.param_type == 'bool':
                custom_parameters[param_name] = request.form.get(f'param_{param_name}') == 'on'
            else:
                value = request.form.get(f'param_{param_name}', '').strip()
                if value:
                    custom_parameters[param_name] = value
                elif param_def.default_value is not None:
                    custom_parameters[param_name] = param_def.default_value

        success = device_manager.update_device(
            device_id=device_id,
            name=form.device_name.data,
            primary_type=primary_type,
            secondary_types=secondary_types,
            custom_parameters=custom_parameters,
        )
        if success:
            flash(f'Device "{form.device_name.data}" updated successfully!', 'success')
            return redirect(url_for('settings_device.devices'))
        else:
            flash(f'Error updating device "{form.device_name.data}".', 'error')
        return redirect(url_for('settings_device.edit_device', device_id=device_id))

    form.device_name.data = device.name
    form.primary_type.data = device.primary_type

    all_params = device.get_all_parameters(type_registry)

    return render_template(
        'settings/device/edit-device.html',
        form=form,
        device=device,
        all_params=all_params,
        type_registry=type_registry,
    )


@settings_device_bp.route('/settings/add-device', methods=['GET', 'POST'])
def add_device():
    form = AddDeviceForm()
    type_registry = device_type_manager.get_registry()
    form.primary_type.choices = device_type_manager.get_type_choices()

    if form.validate_on_submit():
        primary_type = form.primary_type.data
        secondary_types = request.form.getlist('secondary_types')
        secondary_types = [t for t in secondary_types if t != primary_type]

        device_id = f'{primary_type}_{int(datetime.now().timestamp())}'

        all_type_ids = [primary_type] + secondary_types
        combined_params = {}
        for tid in all_type_ids:
            dt = type_registry.get(tid)
            if dt:
                combined_params.update(dt.custom_parameters)

        custom_parameters = {}
        for param_name, param_def in combined_params.items():
            if param_def.param_type == 'bool':
                custom_parameters[param_name] = request.form.get(f'param_{param_name}') == 'on'
            else:
                value = request.form.get(f'param_{param_name}', '').strip()
                if value:
                    custom_parameters[param_name] = value
                elif param_def.default_value is not None:
                    custom_parameters[param_name] = param_def.default_value

        success = device_manager.add_device(
            device_id=device_id,
            name=form.device_name.data,
            primary_type=primary_type,
            secondary_types=secondary_types,
            custom_parameters=custom_parameters,
        )
        if success:
            flash(f'Device "{form.device_name.data}" saved successfully!', 'success')
        else:
            flash(f'Error saving device "{form.device_name.data}".', 'error')
        return redirect(url_for('settings_device.devices'))

    return render_template(
        'settings/device/add-device.html',
        form=form,
        type_registry=type_registry,
    )


@settings_device_bp.route('/settings/remove-device/<device_id>', methods=['GET', 'POST'])
def remove_device(device_id):
    success = device_manager.remove_device(device_id)
    if success:
        flash('Device removed successfully!', 'success')
    else:
        flash('Error removing device.', 'error')
    return redirect(url_for('settings_device.devices'))


@settings_device_bp.route('/api/device-types/parameters')
def device_types_parameters():
    type_ids = request.args.get('types', '').split(',')
    type_ids = [t.strip() for t in type_ids if t.strip()]
    type_registry = device_type_manager.get_registry()
    combined_params = {}
    types_info = []
    for tid in type_ids:
        dt = type_registry.get(tid)
        if dt:
            combined_params.update({k: v.to_dict() for k, v in dt.custom_parameters.items()})
            types_info.append({'type_id': dt.type_id, 'name': dt.name, 'icon': dt.icon, 'description': dt.description})
    return jsonify(
        {
            'parameters': combined_params,
            'types': types_info,
        }
    )


@settings_device_bp.route('/settings/solar-panels', methods=['GET', 'POST'])
def solar_panels():
    form = SolarConfigForm()

    if form.validate_on_submit():
        solar_manager.set_sensors(
            {
                'actual_production': form.actual_production.data or '',
                'energy_production_today': form.energy_production_today.data or '',
                'energy_production_lifetime': form.energy_production_lifetime.data or '',
            }
        )

        solar_manager.set_estimation_sensors(
            {
                'estimated_actual_production': form.estimated_actual_production.data or '',
                'estimated_energy_production_remaining_today': form.estimated_energy_production_remaining_today.data
                or '',
                'estimated_energy_production_today': form.estimated_energy_production_today.data or '',
                'estimated_energy_production_hour': form.estimated_energy_production_hour.data or '',
                'estimated_actual_production_offset_day': form.estimated_actual_production_offset_day.data or '',
                'estimated_energy_production_offset_day': form.estimated_energy_production_offset_day.data or '',
                'estimated_energy_production_offset_hour': form.estimated_energy_production_offset_hour.data or '',
            }
        )

        flash('Solar configuration saved successfully!', 'success')
        return redirect(url_for('settings_device.solar_panels'))

    solar_config = solar_manager.get_config()
    if request.method == 'GET':
        form.actual_production.data = solar_config.sensors.actual_production
        form.energy_production_today.data = solar_config.sensors.energy_production_today
        form.energy_production_lifetime.data = solar_config.sensors.energy_production_lifetime

        form.estimated_actual_production.data = solar_config.estimation_sensors.estimated_actual_production
        form.estimated_energy_production_remaining_today.data = (
            solar_config.estimation_sensors.estimated_energy_production_remaining_today
        )
        form.estimated_energy_production_today.data = solar_config.estimation_sensors.estimated_energy_production_today
        form.estimated_energy_production_hour.data = solar_config.estimation_sensors.estimated_energy_production_hour
        form.estimated_actual_production_offset_day.data = (
            solar_config.estimation_sensors.estimated_actual_production_offset_day
        )
        form.estimated_energy_production_offset_day.data = (
            solar_config.estimation_sensors.estimated_energy_production_offset_day
        )
        form.estimated_energy_production_offset_hour.data = (
            solar_config.estimation_sensors.estimated_energy_production_offset_hour
        )

    return render_template('settings/device/solar-panels.html', form=form, solar=solar_config)
