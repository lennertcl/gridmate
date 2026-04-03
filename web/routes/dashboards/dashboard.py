import json
import logging
import os
from datetime import datetime

import requests as http_requests
from flask import Blueprint, jsonify, render_template, request

from web.forms.energy import EnergyCostsForm
from web.model.data.data_connector import (
    DataConnector,
    DeviceManager,
    DeviceTypeManager,
    EnergyContractManager,
    EnergyDataService,
    SolarManager,
)
from web.model.energy.cost_calculator import CostCalculationService
from web.model.energy.models import EnergyPeriodData

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)

CUSTOM_DASHBOARD_TEMPLATES = {
    'home_battery': 'dashboard/device/home-battery.html',
}

data_connector = DataConnector()
energy_contract_manager = EnergyContractManager(data_connector)
energy_data_service = EnergyDataService(data_connector)
device_manager = DeviceManager(data_connector)
device_type_manager = DeviceTypeManager(data_connector)
solar_manager = SolarManager(data_connector)


@dashboard_bp.route('/dashboard/live')
def live():
    energy_feed = data_connector.get_energy_feed()
    solar = solar_manager.get_config()

    ha_sensors = {
        'actual_consumption_sensor': energy_feed.actual_consumption,
        'actual_injection_sensor': energy_feed.actual_injection,
        'actual_usage_sensor': energy_feed.actual_usage if energy_feed.usage_mode == 'manual' else '',
        'actual_production_sensor': solar.sensors.actual_production if solar.sensors.has_any else '',
        'usage_mode': energy_feed.usage_mode,
    }

    return render_template('dashboard/live.html', **ha_sensors)


@dashboard_bp.route('/api/ha/config')
def ha_config():
    """Return HA connection config for frontend WebSocket auth.

    In LOCAL_DEV mode: uses environment variables (HA_URL, HA_TOKEN).
    In addon mode: reads ha_token from /data/options.json (addon settings)
    and auto-detects the HA URL from the Supervisor API.
    """
    is_local_dev = os.environ.get('LOCAL_DEV', '').lower() == 'true'

    if is_local_dev:
        token = os.environ.get('HA_TOKEN')
        ha_url = os.environ.get('HA_URL', 'http://homeassistant.local:8123')
    else:
        token = _get_addon_option('ha_token', '')
        ha_url = _detect_ha_url()

    return jsonify({'hass_url': ha_url, 'access_token': token})


def _get_addon_option(key, default=''):
    try:
        with open('/data/options.json', 'r') as f:
            options = json.load(f)
        return options.get(key, default)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _detect_ha_url():
    supervisor_token = os.environ.get('SUPERVISOR_TOKEN')
    if not supervisor_token:
        return 'http://homeassistant.local:8123'
    try:
        response = http_requests.get(
            'http://supervisor/core/api/config', headers={'Authorization': f'Bearer {supervisor_token}'}, timeout=5
        )
        if response.status_code == 200:
            config = response.json()
            return config.get('internal_url') or config.get('external_url') or 'http://homeassistant.local:8123'
    except http_requests.RequestException:
        pass
    return 'http://homeassistant.local:8123'


@dashboard_bp.route('/dashboard/solar')
def solar():
    solar_config = solar_manager.get_config()
    energy_feed = data_connector.get_energy_feed()

    solar_sensors = {
        'actual_production': solar_config.sensors.actual_production,
        'energy_production_today': solar_config.sensors.energy_production_today,
        'energy_production_lifetime': solar_config.sensors.energy_production_lifetime,
        'estimated_actual_production': solar_config.estimation_sensors.estimated_actual_production,
        'estimated_energy_production_remaining_today': solar_config.estimation_sensors.estimated_energy_production_remaining_today,
        'estimated_energy_production_today': solar_config.estimation_sensors.estimated_energy_production_today,
        'estimated_energy_production_hour': solar_config.estimation_sensors.estimated_energy_production_hour,
        'estimated_actual_production_offset_day': solar_config.estimation_sensors.estimated_actual_production_offset_day,
        'estimated_energy_production_offset_day': solar_config.estimation_sensors.estimated_energy_production_offset_day,
        'estimated_energy_production_offset_hour': solar_config.estimation_sensors.estimated_energy_production_offset_hour,
        'actual_consumption': energy_feed.actual_consumption,
        'actual_injection': energy_feed.actual_injection,
    }

    return render_template(
        'dashboard/solar.html',
        solar_sensors=solar_sensors,
        is_configured=solar_config.is_configured,
    )


@dashboard_bp.route('/dashboard/devices')
def devices():
    filter_type = request.args.get('type')
    if filter_type:
        all_devices = device_manager.get_devices_by_type(filter_type)
    else:
        all_devices = device_manager.list_all_devices()
    type_registry = device_type_manager.get_registry()
    filter_type_name = type_registry.get(filter_type, {})
    if hasattr(filter_type_name, 'name'):
        filter_type_name = filter_type_name.name
    else:
        filter_type_name = None
    return render_template(
        'dashboard/devices.html',
        devices=all_devices,
        type_registry=type_registry,
        filter_type=filter_type,
        filter_type_name=filter_type_name,
    )


@dashboard_bp.route('/dashboard/device/<device_id>')
def device_detail(device_id):
    device = device_manager.get_device(device_id)
    if not device:
        return render_template('errors/404.html'), 404

    type_registry = device_type_manager.get_registry()

    for type_id in device.get_all_type_ids():
        custom_template = CUSTOM_DASHBOARD_TEMPLATES.get(type_id)
        if custom_template:
            all_type_params = device.get_all_parameters(type_registry)
            default_params = {k: '' for k in all_type_params}
            default_params.update(device.custom_parameters)
            return render_template(
                custom_template,
                device=device,
                type_registry=type_registry,
                **default_params,
            )

    primary_type = type_registry.get(device.primary_type)
    all_params = device.get_all_parameters(type_registry)
    return render_template(
        'dashboard/device-detail.html',
        device=device,
        primary_type=primary_type,
        all_params=all_params,
        type_registry=type_registry,
    )


@dashboard_bp.route('/dashboard/costs')
def energy_costs():
    form = EnergyCostsForm()

    period_type = request.args.get('period_type', 'month')
    month = request.args.get('month', type=int) or datetime.now().month
    year = request.args.get('year', type=int) or datetime.now().year

    # Validate date range
    if month < 1 or month > 12:
        month = datetime.now().month
    if year < 2000:
        year = datetime.now().year

    form.period_type.data = period_type
    form.month.data = str(month)
    form.year.data = year

    contract = energy_contract_manager.get_config()
    calculator = CostCalculationService(contract)

    # Fetch real energy data from Home Assistant
    ha_available = energy_data_service.is_ha_available()

    if ha_available:
        try:
            if period_type == 'month':
                period_data = energy_data_service.get_period_data(year, month, contract=contract)
            else:
                period_data = energy_data_service.get_period_data(year, contract=contract)
            data_source = 'home_assistant'
        except Exception as e:
            logger.warning(f'Failed to fetch data from Home Assistant: {e}')
            period_data = EnergyPeriodData()
            data_source = 'unavailable'
    else:
        logger.info('Home Assistant not available, showing empty data')
        period_data = EnergyPeriodData()
        data_source = 'unavailable'

    if period_type == 'month':
        total_cost, breakdowns = calculator.calculate_monthly_costs(period_data)
        is_monthly = True
    else:
        total_cost, breakdowns = calculator.calculate_yearly_costs(period_data)
        is_monthly = False

    meter_readings = calculator.get_meter_readings_summary(period_data)
    cost_summary = calculator.get_cost_summary(period_data, is_monthly)

    # Sort breakdowns by absolute cost descending
    breakdowns_sorted = sorted(
        [b.to_dict() for b in breakdowns],
        key=lambda x: x['cost'],
        reverse=True,
    )

    # Daily evolution data for meter readings chart
    energy_feed = energy_data_service.get_energy_feed()
    daily_evolution = calculator.get_daily_evolution(period_data, energy_feed)

    # Prepare navigation data
    current_month_name = datetime(year, month, 1).strftime('%B')

    # Calculate previous and next periods
    prev_month = None
    next_month = None

    if period_type == 'month':
        if month == 1:
            prev_month, prev_year = 12, year - 1
        else:
            prev_month, prev_year = month - 1, year

        if month == 12:
            next_month, next_year = 1, year + 1
        else:
            next_month, next_year = month + 1, year
    else:  # year
        prev_year = year - 1
        next_year = year + 1

    context = {
        'form': form,
        'period_type': period_type,
        'month': month,
        'year': year,
        'current_month_name': current_month_name,
        'meter_readings': meter_readings,
        'cost_summary': cost_summary,
        'total_cost': round(total_cost, 2),
        'breakdowns': breakdowns_sorted,
        'has_contract': bool(contract and contract.components),
        'daily_evolution': daily_evolution,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'data_source': data_source,
        'ha_available': ha_available,
    }

    return render_template('dashboard/costs.html', **context)
