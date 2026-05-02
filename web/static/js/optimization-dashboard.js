var DEVICE_COLORS = [
    '#1e90ff',
    '#e056a0',
    '#8b5cf6',
    '#850324',
    '#07145e',
    '#053d09',
    '#ff3d3d',
    '#3c7d80',
    '#643711',
    '#6c6d37',
];

function get_device_name(device_id) {
    return (DEVICE_NAMES && DEVICE_NAMES[device_id]) || device_id;
}

function get_device_created_at(device_id) {
    var match = (device_id || '').match(/_(\d+)$/);
    return match ? parseInt(match[1], 10) : 0;
}

function get_device_color_index(device_id) {
    var normalized_device_id = device_id || '';
    var hash_value = 0;
    var index;

    for (index = 0; index < normalized_device_id.length; index += 1) {
        hash_value = (hash_value * 31 + normalized_device_id.charCodeAt(index)) >>> 0;
    }

    return hash_value % DEVICE_COLORS.length;
}

function build_device_color_map(device_ids) {
    var device_color_map = {};
    var used_colors = {};

    device_ids.forEach(function(device_id) {
        var color_offset;
        var preferred_index = get_device_color_index(device_id);
        var resolved_color = DEVICE_COLORS[preferred_index];

        for (color_offset = 0; color_offset < DEVICE_COLORS.length; color_offset += 1) {
            var candidate_color = DEVICE_COLORS[(preferred_index + color_offset) % DEVICE_COLORS.length];
            if (!used_colors[candidate_color]) {
                resolved_color = candidate_color;
                break;
            }
        }

        device_color_map[device_id] = resolved_color;
        used_colors[resolved_color] = true;
    });

    return device_color_map;
}

function get_value_bounds(values) {
    return values.reduce(function(bounds, value) {
        if (!Number.isFinite(value)) {
            return bounds;
        }

        bounds.min = Math.min(bounds.min, value, 0);
        bounds.max = Math.max(bounds.max, value, 0);
        return bounds;
    }, { min: 0, max: 0 });
}

function align_zero_bounds(bounds_by_axis) {
    var axis_ids = Object.keys(bounds_by_axis);
    var target_ratio = axis_ids.reduce(function(max_ratio, axis_id) {
        var bounds = bounds_by_axis[axis_id];
        var range = bounds.max - bounds.min;
        var ratio = range > 0 ? (-bounds.min) / range : 0;
        return Math.max(max_ratio, ratio);
    }, 0);

    axis_ids.forEach(function(axis_id) {
        var bounds = bounds_by_axis[axis_id];
        var range = bounds.max - bounds.min;
        var current_ratio = range > 0 ? (-bounds.min) / range : 0;

        if (target_ratio <= 0 || Math.abs(current_ratio - target_ratio) < 0.0001) {
            return;
        }

        if (current_ratio < target_ratio && bounds.max > 0) {
            bounds.min = -(target_ratio * bounds.max) / (1 - target_ratio);
            return;
        }

        if (target_ratio > 0 && bounds.min < 0) {
            bounds.max = (-bounds.min * (1 - target_ratio)) / target_ratio;
        }
    });

    return bounds_by_axis;
}

function add_bounds_margin(bounds_by_axis, margin_ratio) {
    Object.keys(bounds_by_axis).forEach(function(axis_id) {
        var bounds = bounds_by_axis[axis_id];
        var range = bounds.max - bounds.min;
        var padding = (range || 1) * margin_ratio;

        bounds.min -= padding;
        bounds.max += padding;
    });

    return bounds_by_axis;
}

function format_clean_tick(value, step, decimals) {
    var rounded_value = Math.round(value / step) * step;
    var tolerance = step / 20;

    if (Math.abs(value - rounded_value) > tolerance) {
        return '';
    }

    return String(Number(rounded_value.toFixed(decimals)));
}

document.addEventListener('DOMContentLoaded', function() {
    checkStatus();

    if (OPTIMIZATION_RESULT) {
        renderEnergyPlanChart(OPTIMIZATION_RESULT);
    }
});

function checkStatus() {
    fetch(baseUrl('/api/optimization/status'))
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var badge = document.getElementById('emhass-badge');
            if (badge) {
                if (data.emhass_available) {
                    badge.className = 'badge badge-active';
                    badge.textContent = 'Connected';
                } else {
                    badge.className = 'badge badge-danger';
                    badge.textContent = 'Offline';
                }
            }
        })
        .catch(function() {
            var badge = document.getElementById('emhass-badge');
            if (badge) {
                badge.className = 'badge badge-danger';
                badge.textContent = 'Error';
            }
        });
}

function renderEnergyPlanChart(result) {
    var canvas = document.getElementById('energy-plan-chart');
    if (!canvas) return;
    var priceValues = [];
    var pvValues = [];
    var chargeValues = [];
    var dischargeValues = [];

    var labels = result.load_forecast.map(function(p) {
        return formatTime(p.timestamp);
    });

    if (labels.length === 0) {
        labels = result.pv_forecast.map(function(p) {
            return formatTime(p.timestamp);
        });
    }

    var deviceIds = Object.keys(result.device_power_forecasts || {}).sort(function(first_device_id, second_device_id) {
        var created_at_difference = get_device_created_at(first_device_id) - get_device_created_at(second_device_id);
        if (created_at_difference !== 0) {
            return created_at_difference;
        }

        var name_comparison = get_device_name(first_device_id).localeCompare(get_device_name(second_device_id));
        if (name_comparison !== 0) {
            return name_comparison;
        }

        return first_device_id.localeCompare(second_device_id);
    });

    var devicePowerArrays = {};
    var deviceColorMap = build_device_color_map(deviceIds);
    deviceIds.forEach(function(deviceId) {
        var points = result.device_power_forecasts[deviceId] || [];
        devicePowerArrays[deviceId] = points.map(function(p) { return p.value; });
    });

    var baseLoad = result.load_forecast.map(function(p) {
        return p.value;
    });

    var datasets = [];

    datasets.push({
        label: 'Base Load',
        data: baseLoad,
        backgroundColor: 'rgba(100, 116, 139, 0.6)',
        borderColor: 'rgba(100, 116, 139, 0.8)',
        borderWidth: 1,
        stack: 'consumption',
        order: 2,
    });

    deviceIds.forEach(function(deviceId) {
        var color = deviceColorMap[deviceId] || DEVICE_COLORS[get_device_color_index(deviceId)];
        var deviceName = get_device_name(deviceId);
        datasets.push({
            label: deviceName,
            data: devicePowerArrays[deviceId],
            backgroundColor: hexToRgba(color, 0.7),
            borderColor: color,
            borderWidth: 1,
            stack: 'consumption',
            order: 2,
        });
    });

    if (result.pv_forecast && result.pv_forecast.length > 0) {
        pvValues = result.pv_forecast.map(function(p) { return p.value; });
        datasets.push({
            label: 'Solar Production',
            data: pvValues,
            type: 'line',
            borderColor: '#ebe730',
            backgroundColor: 'rgba(235, 231, 48, 0.15)',
            fill: true,
            tension: 0,
            borderWidth: 2.5,
            pointRadius: 0,
            pointHitRadius: 8,
            order: 1,
        });
    }

    if (result.load_cost_forecast && result.load_cost_forecast.length > 0) {
        priceValues = priceValues.concat(result.load_cost_forecast.map(function(p) { return p.value; }));
        datasets.push({
            label: 'Consumption Price',
            data: result.load_cost_forecast.map(function(p) { return p.value; }),
            type: 'line',
            borderColor: '#ff8c42',
            backgroundColor: 'rgba(0, 217, 126, 0.12)',
            yAxisID: 'y_price',
            fill: false,
            tension: 0,
            stepped: 'after',
            borderWidth: 2,
            pointRadius: 0,
            pointHitRadius: 8,
            order: 0,
        });
    }

    if (result.prod_price_forecast && result.prod_price_forecast.length > 0) {
        priceValues = priceValues.concat(result.prod_price_forecast.map(function(p) { return p.value; }));
        datasets.push({
            label: 'Injection Price',
            data: result.prod_price_forecast.map(function(p) { return p.value; }),
            type: 'line',
            borderColor: '#00d97e',
            backgroundColor: 'rgba(255, 140, 66, 0.12)',
            yAxisID: 'y_price',
            fill: false,
            tension: 0,
            stepped: 'after',
            borderWidth: 2,
            pointRadius: 0,
            pointHitRadius: 8,
            order: 0,
        });
    }

    if (result.battery_power_forecast && result.battery_power_forecast.length > 0) {
        chargeValues = result.battery_power_forecast.map(function(p) {
            return p.value < 0 ? -p.value : 0;
        });
        dischargeValues = result.battery_power_forecast.map(function(p) {
            return p.value > 0 ? -p.value : 0;
        });

        datasets.push({
            label: 'Battery Charging',
            data: chargeValues,
            backgroundColor: 'rgba(15, 118, 110, 0.6)',
            borderColor: '#0f766e',
            borderWidth: 1,
            stack: 'consumption',
            order: 2,
        });
        datasets.push({
            label: 'Battery Discharging',
            data: dischargeValues,
            backgroundColor: 'rgba(255, 140, 66, 0.6)',
            borderColor: '#ff8c42',
            borderWidth: 1,
            stack: 'consumption',
            order: 2,
        });
    }

    var powerBounds = labels.reduce(function(bounds, _, index) {
        var positivePower = (baseLoad[index] || 0) + (chargeValues[index] || 0);
        var negativePower = dischargeValues[index] || 0;

        deviceIds.forEach(function(deviceId) {
            var value = (devicePowerArrays[deviceId] || [])[index] || 0;
            if (value >= 0) {
                positivePower += value;
            } else {
                negativePower += value;
            }
        });

        bounds.min = Math.min(bounds.min, negativePower, pvValues[index] || 0);
        bounds.max = Math.max(bounds.max, positivePower, pvValues[index] || 0);
        return bounds;
    }, { min: 0, max: 0 });

    var alignedBounds = priceValues.length > 0
        ? align_zero_bounds({ y: powerBounds, y_price: get_value_bounds(priceValues) })
        : { y: powerBounds };

    alignedBounds = add_bounds_margin(alignedBounds, 0.03);

    new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 16,
                        font: { size: 12 },
                    },
                },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            if (ctx.dataset.yAxisID === 'y_price') {
                                return ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(3) + ' €/kWh';
                            }
                            return ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(2) + ' kW';
                        },
                    },
                },
            },
            scales: {
                x: {
                    stacked: true,
                    grid: { display: false },
                    ticks: {
                        maxTicksLimit: 16,
                        font: { size: 11 },
                    },
                },
                y: {
                    stacked: true,
                    min: alignedBounds.y.min,
                    max: alignedBounds.y.max,
                    title: {
                        display: true,
                        text: 'Power (kW)',
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)',
                    },
                    ticks: {
                        callback: function(value) {
                            return format_clean_tick(value, 0.5, 1);
                        },
                    },
                },
                y_price: {
                    position: 'right',
                    min: alignedBounds.y_price ? alignedBounds.y_price.min : undefined,
                    max: alignedBounds.y_price ? alignedBounds.y_price.max : undefined,
                    title: {
                        display: true,
                        text: 'Price (€/kWh)',
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                    ticks: {
                        callback: function(value) {
                            return format_clean_tick(value, 0.05, 2);
                        },
                    },
                },
            },
        },
    });
}

function hexToRgba(hex, alpha) {
    var r = parseInt(hex.slice(1, 3), 16);
    var g = parseInt(hex.slice(3, 5), 16);
    var b = parseInt(hex.slice(5, 7), 16);
    return 'rgba(' + r + ', ' + g + ', ' + b + ', ' + alpha + ')';
}

function formatTime(isoStr) {
    if (!isoStr) return '';
    var d = new Date(isoStr);
    var h = d.getHours().toString().padStart(2, '0');
    var m = d.getMinutes().toString().padStart(2, '0');
    return h + ':' + m;
}

function runOptimization(type) {
    var btn = document.getElementById('btn-run-optimization');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
    }

    var body = {};
    if (type) {
        body.type = type;
    }

    fetch(baseUrl('/api/optimization/run'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            window.location.reload();
        } else {
            alert('Optimization failed: ' + (data.error || 'Unknown error'));
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-play"></i> Run Now';
            }
        }
    })
    .catch(function(err) {
        alert('Optimization request failed: ' + err.message);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-play"></i> Run Now';
        }
    });
}

function toggleDeviceOptimization(checkbox, deviceId) {
    fetch(baseUrl('/api/optimization/device/' + deviceId + '/toggle'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (!data.success) {
            checkbox.checked = !checkbox.checked;
        }
    })
    .catch(function() {
        checkbox.checked = !checkbox.checked;
    });
}

function toggleOverrideControls(deviceId) {
    var el = document.getElementById('override-controls-' + deviceId);
    if (!el) return;
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

function setDeviceOverride(deviceId) {
    var card = document.querySelector('[data-device-id="' + deviceId + '"]');
    if (!card) return;

    var cyclesInput = card.querySelector('.override-num-cycles');
    var gapInput = card.querySelector('.override-gap');
    var startInput = card.querySelector('.override-start');
    var endInput = card.querySelector('.override-end');

    var defaults = (typeof DEVICE_DEFAULTS !== 'undefined' && DEVICE_DEFAULTS[deviceId]) || {};

    var startTime = startInput ? startInput.value : '';
    var endTime = endInput ? endInput.value : '';
    if (startTime === defaults.earliest_start_time) startTime = '';
    if (endTime === defaults.latest_end_time) endTime = '';

    var body = {
        num_cycles: cyclesInput ? parseInt(cyclesInput.value) || 0 : 1,
        hours_between_runs: gapInput ? parseFloat(gapInput.value) || 0 : 0,
        earliest_start_time: startTime,
        latest_end_time: endTime,
    };

    fetch(baseUrl('/api/optimization/device/' + deviceId + '/override'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(function(err) {
        alert('Failed to set override: ' + err.message);
    });
}

function clearDeviceOverride(deviceId) {
    fetch(baseUrl('/api/optimization/device/' + deviceId + '/clear-override'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(function(err) {
        alert('Failed to clear override: ' + err.message);
    });
}

function getScheduleInputStepSeconds() {
    if (OPTIMIZATION_RESULT && OPTIMIZATION_RESULT.time_step_minutes) {
        return OPTIMIZATION_RESULT.time_step_minutes * 60;
    }

    return 1800;
}

function openScheduleEditor(deviceId, windowIndex, trigger) {
    var card = document.querySelector('[data-device-id="' + deviceId + '"]');
    if (!card) return;

    var editor = document.getElementById('schedule-editor-' + deviceId);
    var deleteButton = card.querySelector('.schedule-delete-btn');
    var indexInput = card.querySelector('.schedule-window-index');
    var startInput = card.querySelector('.schedule-edit-start');
    var endInput = card.querySelector('.schedule-edit-end');
    var defaults = (typeof DEVICE_DEFAULTS !== 'undefined' && DEVICE_DEFAULTS[deviceId]) || {};

    if (!editor || !indexInput || !startInput || !endInput) return;

    startInput.step = getScheduleInputStepSeconds();
    endInput.step = getScheduleInputStepSeconds();

    if (windowIndex === null || typeof windowIndex === 'undefined') {
        indexInput.value = '';
        startInput.value = defaults.earliest_start_time || '';
        endInput.value = defaults.latest_end_time || '';
        if (deleteButton) {
            deleteButton.style.display = 'none';
        }
    } else {
        indexInput.value = String(windowIndex);
        startInput.value = trigger ? (trigger.getAttribute('data-start') || '') : '';
        endInput.value = trigger ? (trigger.getAttribute('data-end') || '') : '';
        if (deleteButton) {
            deleteButton.style.display = 'inline-flex';
        }
    }

    editor.style.display = 'block';
    startInput.focus();
}

function closeScheduleEditor(deviceId) {
    var editor = document.getElementById('schedule-editor-' + deviceId);
    var card = document.querySelector('[data-device-id="' + deviceId + '"]');
    var deleteButton = card ? card.querySelector('.schedule-delete-btn') : null;
    if (!editor) return;
    editor.style.display = 'none';
    if (deleteButton) {
        deleteButton.style.display = 'none';
    }
}

function saveDeviceScheduleWindow(deviceId) {
    var card = document.querySelector('[data-device-id="' + deviceId + '"]');
    if (!card) return;

    var indexInput = card.querySelector('.schedule-window-index');
    var startInput = card.querySelector('.schedule-edit-start');
    var endInput = card.querySelector('.schedule-edit-end');
    var body = {
        start_time: startInput ? startInput.value : '',
        end_time: endInput ? endInput.value : '',
    };

    if (!body.start_time || !body.end_time) {
        alert('Start and end time are required');
        return;
    }

    if (indexInput && indexInput.value !== '') {
        body.window_index = parseInt(indexInput.value, 10);
    }

    fetch(baseUrl('/api/optimization/device/' + deviceId + '/schedule-window'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    })
    .then(function(response) {
        return response.json().then(function(data) {
            if (!response.ok) {
                throw new Error(data.error || 'Failed to update scheduled window');
            }
            return data;
        });
    })
    .then(function(data) {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(function(err) {
        alert('Failed to save scheduled window: ' + err.message);
    });
}

function deleteDeviceScheduleWindow(deviceId) {
    var card = document.querySelector('[data-device-id="' + deviceId + '"]');
    if (!card) return;

    var indexInput = card.querySelector('.schedule-window-index');
    var windowIndex = indexInput && indexInput.value !== '' ? parseInt(indexInput.value, 10) : NaN;

    if (!Number.isInteger(windowIndex)) {
        return;
    }

    fetch(baseUrl('/api/optimization/device/' + deviceId + '/schedule-window'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'delete',
            window_index: windowIndex,
        }),
    })
    .then(function(response) {
        return response.json().then(function(data) {
            if (!response.ok) {
                throw new Error(data.error || 'Failed to delete scheduled window');
            }
            return data;
        });
    })
    .then(function(data) {
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(function(err) {
        alert('Failed to delete scheduled window: ' + err.message);
    });
}
