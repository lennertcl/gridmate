import { get_ha_connection } from './ha-connection.js';
import { subscribeEntities } from 'https://esm.sh/home-assistant-js-websocket@9.6.0';

const GAUGE_CIRCUMFERENCE = 2 * Math.PI * 85;
const HISTORY_HOURS = 24;

let ha_connection = null;
let level_chart = null;
let power_chart = null;
let last_power = null;
let mode_initialized = false;

function get_config() {
    return window.BATTERY_CONFIG || {};
}

function get_battery_status(power_kw) {
    const val = power_kw || 0;
    if (val > 0.05) return 'charging';
    if (val < -0.05) return 'discharging';
    return 'idle';
}

function get_effective_power(power_kw) {
    const val = power_kw || 0;
    return { display: Math.abs(val).toFixed(2) + ' kW', raw: val };
}

function update_gauge(level_pct) {
    const fill = document.getElementById('gauge-fill');
    if (!fill) return;

    const clamped = Math.max(0, Math.min(100, level_pct));
    const offset = GAUGE_CIRCUMFERENCE * (1 - clamped / 100);
    fill.setAttribute('stroke-dashoffset', offset.toString());
}

function update_gauge_color(status) {
    const fill = document.getElementById('gauge-fill');
    if (!fill) return;
    fill.classList.remove('gauge-charging', 'gauge-discharging', 'gauge-idle');
    fill.classList.add('gauge-' + status);
}

function update_battery_level(level_pct) {
    const el = document.getElementById('battery-level');
    if (el) el.textContent = Math.round(level_pct);
    update_gauge(level_pct);
}

function update_stored_energy(level_pct) {
    const config = get_config();
    const el = document.getElementById('battery-stored');
    if (!el || !config.capacity_kwh) return;
    const stored = (config.capacity_kwh * level_pct / 100).toFixed(1);
    el.textContent = stored + ' kWh';
}

function update_power_display(power_kw) {
    const status = get_battery_status(power_kw);
    const power = get_effective_power(power_kw);

    const power_el = document.getElementById('battery-power');
    if (power_el) power_el.textContent = power.display;

    const status_el = document.getElementById('battery-status-text');
    if (status_el) {
        const labels = { charging: 'Charging', discharging: 'Discharging', idle: 'Idle' };
        status_el.textContent = labels[status];
    }

    update_gauge_color(status);
    update_charge_rate(power_kw);
}

function update_charge_rate(power_kw) {
    const config = get_config();
    const charge_fill = document.getElementById('charge-fill');
    const discharge_fill = document.getElementById('discharge-fill');
    const indicator = document.getElementById('charge-rate-indicator');
    const value_el = document.getElementById('charge-rate-value');
    const val = power_kw || 0;

    if (charge_fill) {
        if (val > 0 && config.max_charge_power) {
            const pct = Math.min(100, (val / config.max_charge_power) * 100);
            charge_fill.style.width = pct + '%';
        } else {
            charge_fill.style.width = '0%';
        }
    }

    if (discharge_fill) {
        if (val < 0 && config.max_discharge_power) {
            const pct = Math.min(100, (Math.abs(val) / config.max_discharge_power) * 100);
            discharge_fill.style.width = pct + '%';
        } else {
            discharge_fill.style.width = '0%';
        }
    }

    if (indicator && value_el) {
        const abs_val = Math.abs(val);
        if (abs_val < 0.01) {
            value_el.textContent = '';
            indicator.style.left = '50%';
        } else {
            value_el.textContent = abs_val.toFixed(2) + ' kW';
            let position = 50;
            if (val > 0 && config.max_charge_power) {
                const pct = Math.min(100, (val / config.max_charge_power) * 100);
                position = 50 + (pct / 2);
            } else if (val < 0 && config.max_discharge_power) {
                const pct = Math.min(100, (Math.abs(val) / config.max_discharge_power) * 100);
                position = 50 - (pct / 2);
            }
            indicator.style.left = position + '%';
        }
    }
}

function update_cumulative_energy(level_pct) {
    const config = get_config();
    const el = document.getElementById('cumulative-energy-stored');
    if (!el || !config.capacity_kwh) return;
    const stored = (config.capacity_kwh * level_pct / 100).toFixed(2);
    el.textContent = stored;

    const subtext_el = document.getElementById('cumulative-energy-subtext');
    if (subtext_el.textContent !== '') return;

    const common_operations = {
        'EV Charges': 60,
        'AC Hours': 3.5,
        'Oven Hours': 2.5,
        'Dryer Cycles': 3.25,
        'Washer Cycles': 0.75,
        'Dishwasher Cycles': 1.3,
        'Refrigerator Hours': 0.1,
        'Kettle Boils': 0.125,
        'Shower Minutes': 0.175,
        'Vacuum Hours': 1.05,
        'TV Hours': 0.075,
        'Laptop Hours': 0.035,
        'Euros Saved': 3.3,
    };

    if (subtext_el) {
        const pick = Object.keys(common_operations)[Math.floor(Math.random() * Object.keys(common_operations).length)];
        const savings = (stored / common_operations[pick]).toFixed(1);
        subtext_el.textContent = `That's ${savings} ${pick}`;
    }
}

function init_level_chart() {
    const canvas = document.getElementById('battery-level-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    level_chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Battery Level (%)',
                    data: [],
                    borderColor: '#00d97e',
                    backgroundColor: 'rgba(0, 217, 126, 0.08)',
                    tension: 0.35,
                    fill: true,
                    pointRadius: 0,
                    borderWidth: 2,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            return 'Battery: ' + ctx.parsed.y.toFixed(1) + '%';
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { maxTicksLimit: 8, font: { size: 11 } },
                    grid: { display: false }
                },
                y: {
                    type: 'linear',
                    position: 'left',
                    min: 0,
                    max: 100,
                    ticks: { callback: v => v + '%', font: { size: 11 } },
                    grid: { color: 'rgba(0,0,0,0.04)' },
                    title: { display: true, text: 'Battery Level', font: { size: 12 } }
                }
            }
        }
    });
}

function init_power_chart() {
    const canvas = document.getElementById('battery-power-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    power_chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Power (kW)',
                    data: [],
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.35,
                    fill: 'origin',
                    segment: {
                        borderColor: function(ctx) {
                            return (ctx.p0.parsed.y + ctx.p1.parsed.y) / 2 >= 0
                                ? '#00d97e' : '#ff8c42';
                        },
                        backgroundColor: function(ctx) {
                            return (ctx.p0.parsed.y + ctx.p1.parsed.y) / 2 >= 0
                                ? 'rgba(0, 217, 126, 0.15)' : 'rgba(255, 140, 66, 0.15)';
                        }
                    }
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            const val = ctx.parsed.y;
                            const status = val >= 0 ? 'Charging' : 'Discharging';
                            return status + ': ' + Math.abs(val).toFixed(2) + ' kW';
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { maxTicksLimit: 8, font: { size: 11 } },
                    grid: { display: false }
                },
                y: {
                    type: 'linear',
                    ticks: { callback: v => v + ' kW', font: { size: 11 } },
                    grid: { color: 'rgba(0,0,0,0.04)' },
                    title: { display: true, text: 'Power', font: { size: 12 } }
                }
            }
        }
    });
}

async function fetch_history(connection) {
    const config = get_config();
    const entities = [];
    if (config.battery_level_sensor) entities.push(config.battery_level_sensor);
    if (config.power_sensor) entities.push(config.power_sensor);

    if (entities.length === 0 || (!level_chart && !power_chart)) return;

    const end = new Date();
    const start = new Date(end.getTime() - HISTORY_HOURS * 3600 * 1000);
    const start_iso = start.toISOString();

    try {
        const result = await connection.sendMessagePromise({
            type: 'history/history_during_period',
            start_time: start_iso,
            end_time: end.toISOString(),
            entity_ids: entities,
            minimal_response: true,
            significant_changes_only: false,
        });

        populate_chart(result, config);
    } catch {
        try {
            const result = await connection.sendMessagePromise({
                type: 'history/period',
                start_time: start_iso,
                entity_ids: entities,
            });
            populate_chart(result, config);
        } catch (e) {
            console.error('Failed to load history:', e);
        }
    }
}

function populate_chart(result, config) {
    if (!result) return;

    const level_data = [];
    const power_data = [];
    const level_labels = [];
    const power_labels = [];

    const level_history = result[config.battery_level_sensor] || [];

    for (const entry of level_history) {
        const ts = new Date(entry.lu ? entry.lu * 1000 : entry.last_changed || entry.last_updated);
        const val = parseFloat(entry.s !== undefined ? entry.s : entry.state);
        if (!isNaN(val)) {
            level_labels.push(ts.getHours().toString().padStart(2, '0') + ':' + ts.getMinutes().toString().padStart(2, '0'));
            level_data.push(val);
        }
    }

    if (config.power_sensor) {
        const power_history = result[config.power_sensor] || [];
        for (const entry of power_history) {
            const ts = new Date(entry.lu ? entry.lu * 1000 : entry.last_changed || entry.last_updated);
            const val = parseFloat(entry.s !== undefined ? entry.s : entry.state);
            if (!isNaN(val)) {
                power_labels.push(ts.getHours().toString().padStart(2, '0') + ':' + ts.getMinutes().toString().padStart(2, '0'));
                power_data.push(val);
            }
        }
    }

    if (level_chart) {
        level_chart.data.labels = level_labels;
        level_chart.data.datasets[0].data = level_data;
        level_chart.update();
    }

    if (power_chart) {
        power_chart.data.labels = power_labels;
        power_chart.data.datasets[0].data = power_data;
        power_chart.update();
    }
}

function handle_entity_update(entities) {
    const config = get_config();

    if (config.battery_level_sensor && entities[config.battery_level_sensor]) {
        const val = parseFloat(entities[config.battery_level_sensor].state);
        if (!isNaN(val)) {
            update_battery_level(val);
            update_stored_energy(val);
            update_cumulative_energy(val);
        }
    }

    if (config.power_sensor && entities[config.power_sensor]) {
        const val = parseFloat(entities[config.power_sensor].state);
        if (!isNaN(val)) {
            last_power = val;
        }
    }

    update_power_display(last_power);

    if (config.mode_select_entity && entities[config.mode_select_entity]) {
        update_mode_display(entities[config.mode_select_entity]);
    }
}

function update_mode_display(entity) {
    const value_el = document.getElementById('battery-mode-value');
    if (value_el) value_el.textContent = entity.state;

    if (!mode_initialized) {
        const select_el = document.getElementById('battery-mode-select');
        const apply_btn = document.getElementById('battery-mode-apply');
        if (!select_el) return;

        const options = entity.attributes.options || [];
        if (options.length > 0) {
            select_el.innerHTML = '';
            options.forEach(function(opt) {
                const option_el = document.createElement('option');
                option_el.value = opt;
                option_el.textContent = opt;
                if (opt === entity.state) option_el.selected = true;
                select_el.appendChild(option_el);
            });
            select_el.disabled = false;
            if (apply_btn) apply_btn.disabled = false;
            mode_initialized = true;
        }
    }
}

function init_mode_control() {
    const config = get_config();
    if (!config.mode_select_entity) return;

    const select_el = document.getElementById('battery-mode-select');
    const apply_btn = document.getElementById('battery-mode-apply');
    if (!apply_btn || !select_el) return;

    apply_btn.addEventListener('click', async function() {
        if (!ha_connection) return;

        const selected_option = select_el.value;
        const entity_domain = config.mode_select_entity.split('.')[0];
        const msg = {
            type: 'call_service',
            domain: entity_domain,
            service: 'select_option',
            target: {
                entity_id: config.mode_select_entity,
            },
            service_data: {
                option: selected_option,
            },
        };
        apply_btn.disabled = true;
        apply_btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        try {
            await ha_connection.sendMessagePromise(msg);
        } catch (e) {
            console.error('Failed to set battery mode:', e);
        }

        apply_btn.innerHTML = '<i class="fas fa-check"></i> Apply';
        apply_btn.disabled = false;
    });
}

async function init_battery_dashboard() {
    const config = get_config();
    if (!config.battery_level_sensor) return;

    init_level_chart();
    init_power_chart();

    try {
        ha_connection = await get_ha_connection();

        init_mode_control();
        subscribeEntities(ha_connection, handle_entity_update);
        fetch_history(ha_connection);
    } catch (e) {
        console.error('Failed to connect to Home Assistant:', e);
    }
}

document.addEventListener('DOMContentLoaded', init_battery_dashboard);
