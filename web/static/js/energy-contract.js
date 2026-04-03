let current_component_type = null;
let current_edit_index = null;

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
        document.getElementById('variable_variable_price_sensor').value = '';
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
        document.getElementById('variable_variable_price_sensor').value = component_data.variable_price_sensor || '';
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
