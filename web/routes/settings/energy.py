from flask import Blueprint, flash, redirect, render_template, request, url_for

from web.forms import (
    CapacityComponentForm,
    ConstantComponentForm,
    EnergyFeedConfigForm,
    EnergyOptimizationForm,
    FixedComponentForm,
    PercentageComponentForm,
    VariableComponentForm,
)
from web.model.data.data_connector import DataConnector, EnergyContractManager, EnergyFeedManager
from web.model.energy.models import (
    ENERGY_SENSOR_DEFAULT,
    ENERGY_SENSOR_OPTION_LABELS,
    CapacityComponent,
    ConstantComponent,
    EnergyContract,
    EnergyFeed,
    FixedComponent,
    PercentageComponent,
    VariableComponent,
)

# Initialize data connector and managers
data_connector = DataConnector()
energy_feed_manager = EnergyFeedManager(data_connector)
energy_contract_manager = EnergyContractManager(data_connector)

settings_energy_bp = Blueprint('settings_energy', __name__)


@settings_energy_bp.route('/settings/energy-feed', methods=['GET', 'POST'])
def energy_feed():
    form = EnergyFeedConfigForm()

    if form.validate_on_submit():
        feed = EnergyFeed(
            total_consumption_high_tariff=form.total_consumption_high_tariff.data or '',
            total_consumption_low_tariff=form.total_consumption_low_tariff.data or '',
            total_injection_high_tariff=form.total_injection_high_tariff.data or '',
            total_injection_low_tariff=form.total_injection_low_tariff.data or '',
            actual_consumption=form.actual_consumption.data or '',
            actual_injection=form.actual_injection.data or '',
            usage_mode=form.usage_mode.data or 'auto',
            actual_usage=form.actual_usage.data or '',
            total_usage_high_tariff=form.total_usage_high_tariff.data or '',
            total_usage_low_tariff=form.total_usage_low_tariff.data or '',
            power_unit='kW',
            energy_unit='kWh',
        )

        data_connector.set_energy_feed(feed)
        flash('Energy feed configuration saved successfully!', 'success')
        return redirect(url_for('settings_energy.energy_feed'))

    energy_feed = energy_feed_manager.get_config()
    if energy_feed and request.method == 'GET':
        form.total_consumption_high_tariff.data = energy_feed.total_consumption_high_tariff
        form.total_consumption_low_tariff.data = energy_feed.total_consumption_low_tariff
        form.total_injection_high_tariff.data = energy_feed.total_injection_high_tariff
        form.total_injection_low_tariff.data = energy_feed.total_injection_low_tariff
        form.actual_consumption.data = energy_feed.actual_consumption
        form.actual_injection.data = energy_feed.actual_injection
        form.usage_mode.data = energy_feed.usage_mode
        form.actual_usage.data = energy_feed.actual_usage
        form.total_usage_high_tariff.data = energy_feed.total_usage_high_tariff
        form.total_usage_low_tariff.data = energy_feed.total_usage_low_tariff

    return render_template('settings/energy/energy-feed.html', form=form, feed=energy_feed)


FORM_CLASSES = {
    'constant': ConstantComponentForm,
    'fixed': FixedComponentForm,
    'variable': VariableComponentForm,
    'capacity': CapacityComponentForm,
    'percentage': PercentageComponentForm,
}


@settings_energy_bp.route('/settings/energy-contract', methods=['GET', 'POST'])
def energy_contract():
    contract = energy_contract_manager.get_config()
    energy_feed = energy_feed_manager.get_config()

    available_sensors = [
        {'id': sensor_key, 'label': sensor_label} for sensor_key, sensor_label in ENERGY_SENSOR_OPTION_LABELS.items()
    ]
    default_energy_sensor = ENERGY_SENSOR_DEFAULT

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_component':
            comp_type = request.form.get('component_type')
            form_class = FORM_CLASSES.get(comp_type)
            if not form_class:
                flash('Invalid component type.', 'danger')
                return redirect(url_for('settings_energy.energy_contract'))

            form = form_class()
            if form.validate_on_submit():
                if not contract:
                    contract = EnergyContract()

                if comp_type == 'constant':
                    component = ConstantComponent(
                        name=form.name.data,
                        multiplier=form.multiplier.data,
                        price_constant=form.price_constant.data,
                        period=form.period.data,
                    )
                elif comp_type == 'fixed':
                    component = FixedComponent(
                        name=form.name.data,
                        multiplier=form.multiplier.data,
                        fixed_price=form.fixed_price.data,
                        is_injection_reward=form.is_injection_reward.data,
                        energy_sensor=form.energy_sensor.data or ENERGY_SENSOR_DEFAULT,
                    )
                elif comp_type == 'variable':
                    component = VariableComponent(
                        name=form.name.data,
                        multiplier=form.multiplier.data,
                        variable_price_sensor=form.variable_price_sensor.data,
                        variable_price_multiplier=form.variable_price_multiplier.data,
                        variable_price_constant=form.variable_price_constant.data,
                        is_injection_reward=form.is_injection_reward.data,
                        energy_sensor=form.energy_sensor.data or ENERGY_SENSOR_DEFAULT,
                    )
                elif comp_type == 'capacity':
                    component = CapacityComponent(
                        name=form.name.data,
                        multiplier=form.multiplier.data,
                        capacity_price_multiplier=form.capacity_price_multiplier.data,
                        period=form.period.data,
                    )
                elif comp_type == 'percentage':
                    component = PercentageComponent(
                        name=form.name.data,
                        multiplier=form.multiplier.data,
                        percentage=form.percentage.data,
                        applies_to_indices=request.form.getlist('applies_to_indices', type=int),
                    )

                contract.components.append(component)
                data_connector.set_energy_contract(contract)
                flash('Component added successfully!', 'success')
            else:
                first_error = next(iter(form.errors.values()))[0]
                flash(f'Validation error: {first_error}', 'danger')

            return redirect(url_for('settings_energy.energy_contract'))

        elif action == 'update_component':
            comp_type = request.form.get('component_type')
            index = request.form.get('index', type=int)
            form_class = FORM_CLASSES.get(comp_type)

            if not form_class or not contract or index is None or index < 0 or index >= len(contract.components):
                flash('Invalid component.', 'danger')
                return redirect(url_for('settings_energy.energy_contract'))

            form = form_class()
            if form.validate_on_submit():
                component = contract.components[index]
                component.name = form.name.data
                component.multiplier = form.multiplier.data

                if isinstance(component, ConstantComponent):
                    component.price_constant = form.price_constant.data
                    component.period = form.period.data
                elif isinstance(component, FixedComponent):
                    component.fixed_price = form.fixed_price.data
                    component.is_injection_reward = form.is_injection_reward.data
                    component.energy_sensor = form.energy_sensor.data or ENERGY_SENSOR_DEFAULT
                elif isinstance(component, VariableComponent):
                    component.variable_price_sensor = form.variable_price_sensor.data
                    component.variable_price_multiplier = form.variable_price_multiplier.data
                    component.variable_price_constant = form.variable_price_constant.data
                    component.is_injection_reward = form.is_injection_reward.data
                    component.energy_sensor = form.energy_sensor.data or ENERGY_SENSOR_DEFAULT
                elif isinstance(component, CapacityComponent):
                    component.capacity_price_multiplier = form.capacity_price_multiplier.data
                    component.period = form.period.data
                elif isinstance(component, PercentageComponent):
                    component.percentage = form.percentage.data
                    component.applies_to_indices = request.form.getlist('applies_to_indices', type=int)

                data_connector.set_energy_contract(contract)
                flash('Component updated successfully!', 'success')
            else:
                first_error = next(iter(form.errors.values()))[0]
                flash(f'Validation error: {first_error}', 'danger')

            return redirect(url_for('settings_energy.energy_contract'))

        elif action == 'remove_component':
            index = request.form.get('index', type=int)
            if contract and index is not None and 0 <= index < len(contract.components):
                contract.components.pop(index)
                for comp in contract.components:
                    if isinstance(comp, PercentageComponent):
                        comp.adjust_indices_after_removal(index)
                data_connector.set_energy_contract(contract)
                flash('Component removed successfully!', 'success')
            else:
                flash('Invalid component index.', 'danger')
            return redirect(url_for('settings_energy.energy_contract'))

    constant_form = ConstantComponentForm(meta={'csrf': True})
    fixed_form = FixedComponentForm(meta={'csrf': True})
    variable_form = VariableComponentForm(meta={'csrf': True})
    capacity_form = CapacityComponentForm(meta={'csrf': True})
    percentage_form = PercentageComponentForm(meta={'csrf': True})

    contract_components_json = (
        [comp.to_dict() for comp in contract.components] if contract and contract.components else []
    )

    return render_template(
        'settings/energy/energy-contract.html',
        contract=contract,
        contract_components_json=contract_components_json,
        energy_feed=energy_feed,
        available_sensors=available_sensors,
        default_energy_sensor=default_energy_sensor,
        constant_form=constant_form,
        fixed_form=fixed_form,
        variable_form=variable_form,
        capacity_form=capacity_form,
        percentage_form=percentage_form,
    )


@settings_energy_bp.route('/settings/energy-optimization', methods=['GET', 'POST'])
def energy_optimization():
    """Energy optimization configuration page"""
    form = EnergyOptimizationForm()

    if form.validate_on_submit():
        # Save to persistent storage
        data_connector.update_optimization(
            {
                'goal': form.goal.data,
                'frequency_minutes': form.optimization_frequency.data,
                'horizon_hours': form.optimization_horizon.data,
                'max_grid_draw_kw': form.max_grid_draw.data,
                'max_grid_injection_kw': form.max_grid_injection.data,
            }
        )

        flash('Energy optimization configuration saved successfully!', 'success')
        return redirect(url_for('settings_energy.energy_optimization'))

    # Load existing data into form
    optimization = data_connector.get_optimization()
    if optimization and request.method == 'GET':
        form.goal.data = optimization.get('goal', 'cost')
        form.optimization_frequency.data = optimization.get('frequency_minutes', 60)
        form.optimization_horizon.data = optimization.get('horizon_hours', 24)
        form.max_grid_draw.data = optimization.get('max_grid_draw_kw', 6.0)
        form.max_grid_injection.data = optimization.get('max_grid_injection_kw', 5.0)

    return render_template('settings/energy/energy-optimization.html', form=form, optimization=optimization)
