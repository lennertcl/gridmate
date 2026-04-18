let current_component_type = null;
let current_edit_index = null;
let current_provider_type = null;
let current_provider_edit_index = null;

function show_component_form(type) {
    const form_ids = ['constantForm', 'fixedForm', 'variableForm', 'capacityForm', 'percentageForm'];
    for (const form_id of form_ids) {
        const form_element = document.getElementById(form_id);
        if (form_element) {
            form_element.style.display = 'none';
        }
    }
    const visible_form = document.getElementById(type + 'Form');
    if (visible_form) {
        visible_form.style.display = 'block';
    }
}

function set_submit_button_label(type, label) {
    const button_id = type + 'SubmitButton';
    const button_element = document.getElementById(button_id);
    if (button_element) {
        button_element.textContent = label;
    }
}

function open_add_component_dialog(type) {
    current_component_type = type;
    current_edit_index = null;
    document.getElementById('addComponentModal').style.display = 'flex';
    document.getElementById('modalTitle').textContent = 'Add New Component';
    show_component_form(type);
    set_submit_button_label(type, 'Add Component');

    document.getElementById(type + 'Action').value = 'add_component';
    document.getElementById(type + 'Index').value = '';

    if (type === 'constant') {
        document.getElementById('constant_name').value = '';
        document.getElementById('constant_price_constant').value = '';
        document.getElementById('constant_period').value = 'month';
        document.getElementById('constant_multiplier').value = '1.0';
    } else if (type === 'fixed') {
        document.getElementById('fixed_name').value = '';
        document.getElementById('fixed_fixed_price').value = '';
        document.getElementById('fixed_energy_sensor').value = window.defaultEnergySensor || 'total_consumption';
        document.getElementById('fixed_multiplier').value = '1.0';
        document.getElementById('fixed_is_injection_reward').checked = false;
    } else if (type === 'variable') {
        document.getElementById('variable_name').value = '';
        document.getElementById('variable_price_provider_name').value = '';
        document.getElementById('variable_variable_price_multiplier').value = '1.0';
        document.getElementById('variable_variable_price_constant').value = '0.0';
        document.getElementById('variable_energy_sensor').value = window.defaultEnergySensor || 'total_consumption';
        document.getElementById('variable_multiplier').value = '1.0';
        document.getElementById('variable_is_injection_reward').checked = false;
    } else if (type === 'capacity') {
        document.getElementById('capacity_name').value = '';
        document.getElementById('capacity_capacity_price_multiplier').value = '';
        document.getElementById('capacity_period').value = 'month';
        document.getElementById('capacity_multiplier').value = '1.0';
    } else if (type === 'percentage') {
        document.getElementById('percentage_name').value = '';
        document.getElementById('percentage_percentage').value = '';
        document.getElementById('percentage_multiplier').value = '1.0';
        render_applies_to_checkboxes(null, []);
    }
}

function open_edit_component_dialog(index, component_class_name, component_data) {
    const type_map = {
        ConstantComponent: 'constant',
        FixedComponent: 'fixed',
        VariableComponent: 'variable',
        CapacityComponent: 'capacity',
        PercentageComponent: 'percentage',
    };
    const type = type_map[component_class_name];
    if (!type) {
        return;
    }

    current_component_type = type;
    current_edit_index = index;
    document.getElementById('addComponentModal').style.display = 'flex';
    document.getElementById('modalTitle').textContent = 'Edit Component';
    show_component_form(type);
    set_submit_button_label(type, 'Update Component');

    document.getElementById(type + 'Action').value = 'update_component';
    document.getElementById(type + 'Index').value = index;

    if (type === 'constant') {
        document.getElementById('constant_name').value = component_data.name || '';
        document.getElementById('constant_price_constant').value = component_data.price_constant ?? 0;
        document.getElementById('constant_period').value = component_data.period || 'month';
        document.getElementById('constant_multiplier').value = component_data.multiplier ?? 1.0;
    } else if (type === 'fixed') {
        document.getElementById('fixed_name').value = component_data.name || '';
        document.getElementById('fixed_fixed_price').value = component_data.fixed_price ?? 0;
        document.getElementById('fixed_energy_sensor').value = component_data.energy_sensor || window.defaultEnergySensor || 'total_consumption';
        document.getElementById('fixed_multiplier').value = component_data.multiplier ?? 1.0;
        document.getElementById('fixed_is_injection_reward').checked = component_data.is_injection_reward || false;
    } else if (type === 'variable') {
        document.getElementById('variable_name').value = component_data.name || '';
        document.getElementById('variable_price_provider_name').value = component_data.price_provider_name || '';
        document.getElementById('variable_variable_price_multiplier').value = component_data.variable_price_multiplier ?? 1.0;
        document.getElementById('variable_variable_price_constant').value = component_data.variable_price_constant ?? 0.0;
        document.getElementById('variable_energy_sensor').value = component_data.energy_sensor || window.defaultEnergySensor || 'total_consumption';
        document.getElementById('variable_multiplier').value = component_data.multiplier ?? 1.0;
        document.getElementById('variable_is_injection_reward').checked = component_data.is_injection_reward || false;
    } else if (type === 'capacity') {
        document.getElementById('capacity_name').value = component_data.name || '';
        document.getElementById('capacity_capacity_price_multiplier').value = component_data.capacity_price_multiplier ?? 0;
        document.getElementById('capacity_period').value = component_data.period || 'month';
        document.getElementById('capacity_multiplier').value = component_data.multiplier ?? 1.0;
    } else if (type === 'percentage') {
        document.getElementById('percentage_name').value = component_data.name || '';
        document.getElementById('percentage_percentage').value = component_data.percentage ?? 0;
        document.getElementById('percentage_multiplier').value = component_data.multiplier ?? 1.0;
        render_applies_to_checkboxes(index, component_data.applies_to_indices || []);
    }
}

function close_add_component_dialog() {
    document.getElementById('addComponentModal').style.display = 'none';
    if (current_component_type) {
        set_submit_button_label(current_component_type, 'Add Component');
    }
    current_component_type = null;
    current_edit_index = null;
}

function render_applies_to_checkboxes(own_index, selected_indices) {
    const container = document.getElementById('percentageAppliesTo');
    container.innerHTML = '';
    const components = window.contractComponents || [];
    components.forEach(function(comp, idx) {
        if (idx === own_index) {
            return;
        }
        if (comp.type === 'PercentageComponent') {
            return;
        }
        const wrapper = document.createElement('label');
        wrapper.className = 'applies-to-option';
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.name = 'applies_to_indices';
        checkbox.value = idx;
        checkbox.checked = selected_indices.indexOf(idx) !== -1;
        wrapper.appendChild(checkbox);
        wrapper.appendChild(document.createTextNode(' ' + comp.name));
        container.appendChild(wrapper);
    });
    if (container.children.length === 0) {
        container.textContent = 'Add other components first';
    }
}

function show_provider_form(type) {
    const form_ids = ['staticProviderForm', 'sensorProviderForm', 'nordpoolProviderForm', 'actionProviderForm'];
    for (const form_id of form_ids) {
        const form_element = document.getElementById(form_id);
        if (form_element) {
            form_element.style.display = 'none';
        }
    }
    const visible_form = document.getElementById(type + 'ProviderForm');
    if (visible_form) {
        visible_form.style.display = 'block';
    }
}

function set_provider_submit_button_label(type, label) {
    const button_id = type + 'ProviderSubmitButton';
    const button_element = document.getElementById(button_id);
    if (button_element) {
        button_element.textContent = label;
    }
}

function open_add_provider_dialog(type) {
    current_provider_type = type;
    current_provider_edit_index = null;
    document.getElementById('addProviderModal').style.display = 'flex';
    document.getElementById('providerModalTitle').textContent = 'Add New Provider';
    show_provider_form(type);
    set_provider_submit_button_label(type, 'Add Provider');

    document.getElementById(type + 'ProviderAction').value = 'add_provider';
    document.getElementById(type + 'ProviderIndex').value = '';

    if (type === 'static') {
        document.getElementById('static_provider_name').value = '';
        document.getElementById('static_provider_price_per_kwh').value = '';
    } else if (type === 'sensor') {
        document.getElementById('sensor_provider_name').value = '';
        document.getElementById('sensor_provider_price_sensor').value = '';
    } else if (type === 'nordpool') {
        document.getElementById('nordpool_provider_name').value = '';
        document.getElementById('nordpool_provider_area').value = '';
    } else if (type === 'action') {
        document.getElementById('action_provider_name').value = '';
        document.getElementById('action_provider_action_domain').value = '';
        document.getElementById('action_provider_action_service').value = '';
        document.getElementById('action_provider_action_data').value = '';
        document.getElementById('action_provider_response_price_key').value = '';
    }
}

function open_edit_provider_dialog(index, provider_type, provider_data) {
    current_provider_type = provider_type;
    current_provider_edit_index = index;
    document.getElementById('addProviderModal').style.display = 'flex';
    document.getElementById('providerModalTitle').textContent = 'Edit Provider';
    show_provider_form(provider_type);
    set_provider_submit_button_label(provider_type, 'Update Provider');

    document.getElementById(provider_type + 'ProviderAction').value = 'update_provider';
    document.getElementById(provider_type + 'ProviderIndex').value = index;

    if (provider_type === 'static') {
        document.getElementById('static_provider_name').value = provider_data.name || '';
        document.getElementById('static_provider_price_per_kwh').value = provider_data.price_per_kwh ?? '';
    } else if (provider_type === 'sensor') {
        document.getElementById('sensor_provider_name').value = provider_data.name || '';
        document.getElementById('sensor_provider_price_sensor').value = provider_data.price_sensor || '';
    } else if (provider_type === 'nordpool') {
        document.getElementById('nordpool_provider_name').value = provider_data.name || '';
        document.getElementById('nordpool_provider_area').value = provider_data.area || '';
    } else if (provider_type === 'action') {
        document.getElementById('action_provider_name').value = provider_data.name || '';
        document.getElementById('action_provider_action_domain').value = provider_data.action_domain || '';
        document.getElementById('action_provider_action_service').value = provider_data.action_service || '';
        document.getElementById('action_provider_action_data').value = provider_data.action_data ? JSON.stringify(provider_data.action_data) : '';
        document.getElementById('action_provider_response_price_key').value = provider_data.response_price_key || '';
    }
}

function close_add_provider_dialog() {
    document.getElementById('addProviderModal').style.display = 'none';
    if (current_provider_type) {
        set_provider_submit_button_label(current_provider_type, 'Add Provider');
    }
    current_provider_type = null;
    current_provider_edit_index = null;
}
