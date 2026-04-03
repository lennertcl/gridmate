document.addEventListener('DOMContentLoaded', function() {
    var primarySelect = document.getElementById('primary-type-select');
    var secondaryContainer = document.getElementById('secondary-types-container');
    var paramsContainer = document.getElementById('custom-parameters-container');
    if (!primarySelect || !paramsContainer) return;

    function getSelectedTypeIds() {
        var types = [];
        var primary = primarySelect.value;
        if (primary) types.push(primary);
        if (secondaryContainer) {
            var checkboxes = secondaryContainer.querySelectorAll('input[name="secondary_types"]:checked');
            checkboxes.forEach(function(cb) {
                if (cb.value !== primary) {
                    types.push(cb.value);
                }
            });
        }
        return types;
    }

    function updateSecondaryVisibility() {
        if (!secondaryContainer) return;
        var primary = primarySelect.value;
        var options = secondaryContainer.querySelectorAll('.secondary-type-option');
        options.forEach(function(opt) {
            var typeId = opt.getAttribute('data-type-id');
            if (typeId === primary) {
                opt.style.display = 'none';
                opt.querySelector('input').checked = false;
            } else {
                opt.style.display = '';
            }
        });
    }

    var DEFAULT_SECONDARY_TYPES = {
        'home_battery': ['battery_device', 'energy_reporting_device'],
        'electric_vehicle': ['battery_device', 'energy_reporting_device'],
        'washing_machine': ['automatable_device', 'energy_reporting_device', 'duration_reporting_device', 'deferrable_load'],
        'dryer': ['automatable_device', 'energy_reporting_device', 'duration_reporting_device', 'deferrable_load'],
        'dishwasher': ['automatable_device', 'energy_reporting_device', 'duration_reporting_device', 'deferrable_load'],
        'water_heater': ['energy_reporting_device', 'automatable_device', 'deferrable_load'],
        'electric_heating': ['energy_reporting_device', 'deferrable_load'],
        'heat_pump': ['energy_reporting_device', 'deferrable_load'],
        'charging_station': ['energy_reporting_device', 'deferrable_load'],
    };

    function applyDefaultSecondaryTypes(primary) {
        if (!secondaryContainer) return;
        var defaults = DEFAULT_SECONDARY_TYPES[primary];
        if (!defaults) return;
        defaults.forEach(function(typeId) {
            if (typeId === primary) return;
            var option = secondaryContainer.querySelector('.secondary-type-option[data-type-id="' + typeId + '"] input');
            if (option && !option.checked) {
                option.checked = true;
            }
        });
    }

    function captureCurrentParams() {
        var current = {};
        var inputs = paramsContainer.querySelectorAll('[name^="param_"]');
        inputs.forEach(function(input) {
            var paramName = input.name.replace('param_', '');
            if (input.type === 'checkbox') {
                current[paramName] = input.checked;
            } else if (input.value) {
                current[paramName] = input.value;
            }
        });
        return current;
    }

    function isBoolChecked(val, defaultValue) {
        if (val === true || val === 'true' || val === 'True' || val === 'on') return true;
        if (val === false || val === 'false' || val === 'False' || val === 'off') return false;
        if (defaultValue !== undefined && defaultValue !== null) {
            return defaultValue === true || defaultValue === 'true';
        }
        return false;
    }

    function renderParamField(key, p, val) {
        var html = '';

        if (p.param_type === 'bool') {
            var checked = isBoolChecked(val, p.default_value);
            html += '<div class="form-col">';
            html += '<label for="param_' + key + '">' + p.label;
            if (p.required) html += ' <span class="param-required">*</span>';
            html += '</label>';
            html += '<label class="checkbox-label">';
            html += '<input type="checkbox" id="param_' + key + '" name="param_' + key + '"';
            if (checked) html += ' checked';
            html += '>';
            html += '</label>';
            if (p.description) {
                html += '<small class="form-help">' + p.description + '</small>';
            }
            html += '</div>';
        } else if (p.param_type === 'time') {
            html += '<div class="form-col">';
            html += '<label for="param_' + key + '">' + p.label;
            if (p.required) html += ' <span class="param-required">*</span>';
            html += '</label>';
            html += '<input type="time" id="param_' + key + '" name="param_' + key + '"';
            html += ' class="form-control"';
            html += ' value="' + (val || '') + '"';
            if (p.required) html += ' required';
            html += '>';
            if (p.description) {
                html += '<small class="form-help">' + p.description + '</small>';
            }
            html += '</div>';
        } else {
            html += '<div class="form-col">';
            html += '<label for="param_' + key + '">' + p.label;
            if (p.unit) html += ' <span class="param-unit">(' + p.unit + ')</span>';
            if (p.required) html += ' <span class="param-required">*</span>';
            html += '</label>';
            html += '<input type="text" id="param_' + key + '" name="param_' + key + '"';
            html += ' class="form-control"';
            html += ' value="' + (val || '') + '"';
            html += ' placeholder="' + (p.placeholder || '') + '"';
            if (p.required) html += ' required';
            html += '>';
            if (p.description) {
                html += '<small class="form-help">' + p.description + '</small>';
            }
            html += '</div>';
        }

        return html;
    }

    function loadCombinedParameters() {
        var currentParams = captureCurrentParams();
        var merged = Object.assign({}, window.existingParams || {}, currentParams);
        window.existingParams = merged;

        var typeIds = getSelectedTypeIds();

        if (typeIds.length === 0) {
            paramsContainer.innerHTML = '';
            return;
        }

        fetch(baseUrl('/api/device-types/parameters?types=' + typeIds.join(',')))
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var params = data.parameters || {};
                var keys = Object.keys(params);

                if (keys.length === 0) {
                    paramsContainer.innerHTML = '';
                    return;
                }

                var html = '<h4>Parameters</h4>';

                for (var i = 0; i < keys.length; i += 2) {
                    html += '<div class="form-row">';
                    for (var j = i; j < Math.min(i + 2, keys.length); j++) {
                        var key = keys[j];
                        var p = params[key];
                        var val = merged[key];
                        if (val === undefined || val === null) {
                            val = '';
                        }
                        html += renderParamField(key, p, val);
                    }
                    html += '</div>';
                }

                paramsContainer.innerHTML = html;
            });
    }

    primarySelect.addEventListener('change', function() {
        var currentParams = captureCurrentParams();
        if (!window.existingSecondaryTypes) {
            window.existingParams = {};
        } else {
            window.existingParams = Object.assign({}, window.existingParams || {}, currentParams);
        }
        updateSecondaryVisibility();

        var primary = primarySelect.value;
        if (primary && !window.existingSecondaryTypes) {
            applyDefaultSecondaryTypes(primary);
        }
        loadCombinedParameters();
    });

    if (secondaryContainer) {
        secondaryContainer.addEventListener('change', function(e) {
            if (e.target.name === 'secondary_types') {
                loadCombinedParameters();
            }
        });
    }

    updateSecondaryVisibility();

    if (primarySelect.value && !window.existingParams) {
        loadCombinedParameters();
    }
});
