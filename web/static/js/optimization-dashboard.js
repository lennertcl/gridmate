var DEVICE_COLORS = [
    '#1e90ff',
    '#e056a0',
    '#8b5cf6',
    '#850324',
    '#07145e',
];

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

    var labels = result.load_forecast.map(function(p) {
        return formatTime(p.timestamp);
    });

    if (labels.length === 0) {
        labels = result.pv_forecast.map(function(p) {
            return formatTime(p.timestamp);
        });
    }

    var deviceIds = Object.keys(result.device_power_forecasts || {});

    var devicePowerArrays = {};
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

    deviceIds.forEach(function(deviceId, index) {
        var color = DEVICE_COLORS[index % DEVICE_COLORS.length];
        var deviceName = (DEVICE_NAMES && DEVICE_NAMES[deviceId]) || deviceId;
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
        var pvValues = result.pv_forecast.map(function(p) { return p.value; });
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
        datasets.push({
            label: 'Import Price',
            data: result.load_cost_forecast.map(function(p) { return p.value; }),
            type: 'line',
            borderColor: '#00d97e',
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
        datasets.push({
            label: 'Export Price',
            data: result.prod_price_forecast.map(function(p) { return p.value; }),
            type: 'line',
            borderColor: '#ff8c42',
            backgroundColor: 'rgba(255, 140, 66, 0.12)',
            borderDash: [6, 4],
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
        var chargeValues = result.battery_power_forecast.map(function(p) {
            return p.value < 0 ? -p.value : 0;
        });
        var dischargeValues = result.battery_power_forecast.map(function(p) {
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
                    title: {
                        display: true,
                        text: 'Power (kW)',
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)',
                    },
                    beginAtZero: true,
                },
                y_price: {
                    position: 'right',
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Price (€/kWh)',
                    },
                    grid: {
                        drawOnChartArea: false,
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
