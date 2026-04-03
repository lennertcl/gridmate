import { get_ha_connection } from './ha-connection.js';
import { subscribeEntities } from 'https://esm.sh/home-assistant-js-websocket@9.6.0';

let ha_connection = null;
let produced_this_hour_kwh = 0;
let last_production_timestamp = null;
let last_production_value = null;
const FULL_DAY_MS = 24 * 60 * 60 * 1000;

function format_power(value) {
    if (value === null || value === undefined || isNaN(value)) return '--';
    return parseFloat(value).toFixed(2) + ' kW';
}

function format_energy(value) {
    if (value === null || value === undefined || isNaN(value)) return '--';
    var num = parseFloat(value);
    if (num >= 1000) return (num / 1000).toFixed(1) + ' MWh';
    return num.toFixed(1) + ' kWh';
}

function get_entity_value(entities, entity_id) {
    if (!entity_id || !entities[entity_id]) return null;
    var state = parseFloat(entities[entity_id].state);
    return isNaN(state) ? null : state;
}

function update_text(element_id, text) {
    var el = document.getElementById(element_id);
    if (el) el.innerText = text;
}

function format_datetime_local(date) {
    const pad = n => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function get_solar_start_time() {
    return new Date(document.getElementById('solar-range-start').value);
}

function get_solar_end_time() {
    return new Date(document.getElementById('solar-range-end').value);
}

function init_solar_range_defaults() {
    var now = new Date();
    var start_of_day = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var end_of_day = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);
    document.getElementById('solar-range-start').value = format_datetime_local(start_of_day);
    document.getElementById('solar-range-end').value = format_datetime_local(end_of_day);
}

function shift_solar_range(offset_ms) {
    var start_input = document.getElementById('solar-range-start');
    var end_input = document.getElementById('solar-range-end');
    var new_start = new Date(new Date(start_input.value).getTime() + offset_ms);
    var new_end = new Date(new Date(end_input.value).getTime() + offset_ms);
    start_input.value = format_datetime_local(new_start);
    end_input.value = format_datetime_local(new_end);
    on_solar_range_change();
}

function on_solar_range_change() {
    var start_time = get_solar_start_time();
    var end_time = get_solar_end_time();
    if (typeof update_solar_chart_range === 'function') {
        update_solar_chart_range(start_time, end_time);
    }
    reload_solar_history();
}

function init_solar_range_controls() {
    init_solar_range_defaults();
    document.getElementById('solar-range-start').addEventListener('change', on_solar_range_change);
    document.getElementById('solar-range-end').addEventListener('change', on_solar_range_change);
    document.getElementById('solar-range-back').addEventListener('click', () => shift_solar_range(-FULL_DAY_MS));
    document.getElementById('solar-range-forward').addEventListener('click', () => shift_solar_range(FULL_DAY_MS));
}

async function reload_solar_history() {
    if (typeof clear_solar_charts === 'function') {
        clear_solar_charts();
    }
    if (ha_connection) {
        await fetch_production_history(ha_connection);
        await fetch_forecast_history(ha_connection);
    }

}

function update_dashboard(entities) {
    var sensors = window.SOLAR_CONFIG.sensors;

    var actual_prod = get_entity_value(entities, sensors.actual_production);
    var energy_today = get_entity_value(entities, sensors.energy_production_today);
    var est_today = get_entity_value(entities, sensors.estimated_energy_production_today);
    var est_hour = get_entity_value(entities, sensors.estimated_energy_production_hour);
    var est_next_hour = get_entity_value(entities, sensors.estimated_energy_production_offset_hour);
    var est_tomorrow_energy = get_entity_value(entities, sensors.estimated_energy_production_offset_day);

    var now = new Date();
    var current_hour_start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours());

    if (actual_prod !== null && last_production_timestamp !== null && last_production_value !== null) {
        if (last_production_timestamp < current_hour_start) {
            produced_this_hour_kwh = 0;
            last_production_timestamp = current_hour_start;
        }
        var dt_hours = (now.getTime() - last_production_timestamp.getTime()) / 3600000;
        var avg_power = (last_production_value + actual_prod) / 2;
        produced_this_hour_kwh += avg_power * dt_hours;
    }
    if (actual_prod !== null) {
        last_production_value = actual_prod;
        last_production_timestamp = now;
    }

    update_text('solar-current-power', format_power(actual_prod));
    update_text('solar-produced-hour', format_energy(produced_this_hour_kwh > 0 ? produced_this_hour_kwh : null));
    update_text('solar-today', energy_today !== null ? format_energy(energy_today) : '--');
    update_text('solar-estimated-today', est_today !== null ? format_energy(est_today) : '--');
    update_text('solar-est-hour', est_hour !== null ? format_energy(est_hour) : '--');
    update_text('solar-est-next-hour', est_next_hour !== null ? format_energy(est_next_hour) : '--');
    update_text('solar-est-tomorrow-energy', est_tomorrow_energy !== null ? format_energy(est_tomorrow_energy) : '--');

    if (typeof update_solar_production_chart_realtime === 'function') {
        update_solar_production_chart_realtime(now, actual_prod);
    }
}

async function fetch_production_history(connection) {
    var sensors = window.SOLAR_CONFIG.sensors;
    var entity_id = sensors.actual_production;
    if (!entity_id) return;

    var start_time = get_solar_start_time();
    var end_time = get_solar_end_time();
    var now = new Date();
    if (end_time > now) {
        end_time = now;
    }

    try {
        var history_data = await connection.sendMessagePromise({
            type: 'history/history_during_period',
            start_time: start_time.toISOString(),
            end_time: end_time.toISOString(),
            entity_ids: [entity_id],
            minimal_response: true,
            no_attributes: true
        });

        if (history_data && history_data[entity_id]) {
            var entries = history_data[entity_id];
            var current_hour_start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours());
            var hour_energy = 0;
            var prev_ts = null;
            var prev_val = null;

            entries.forEach(function(item) {
                var val = parseFloat(item.s);
                if (!isNaN(val)) {
                    var ts = new Date(item.lu * 1000);
                    if (typeof solar_production_chart !== 'undefined' && solar_production_chart) {
                        solar_production_chart.data.datasets[0].data.push({ x: ts, y: val });
                    }
                    if (ts >= current_hour_start && prev_ts !== null && prev_val !== null) {
                        var effective_start = prev_ts < current_hour_start ? current_hour_start : prev_ts;
                        var dt_hours = (ts.getTime() - effective_start.getTime()) / 3600000;
                        hour_energy += ((prev_val + val) / 2) * dt_hours;
                    }
                    prev_ts = ts;
                    prev_val = val;
                }
            });
            produced_this_hour_kwh = hour_energy;
            if (prev_ts && prev_val !== null) {
                last_production_timestamp = prev_ts;
                last_production_value = prev_val;
            }
            update_text('solar-produced-hour', format_energy(produced_this_hour_kwh > 0 ? produced_this_hour_kwh : null));

            if (typeof solar_production_chart !== 'undefined' && solar_production_chart) {
                solar_production_chart.update('none');
            }
        }
    } catch (error) {
        console.error('Error fetching production history:', error);
    }
}

async function fetch_forecast_history(connection) {
    var sensors = window.SOLAR_CONFIG.sensors;
    var est_entity_id = sensors.estimated_actual_production;
    var offset_entity_id = sensors.estimated_actual_production_offset_day;
    var start_time = get_solar_start_time();
    var end_time = get_solar_end_time();
    var now = new Date();
    var twenty_four_hours = 24 * 60 * 60 * 1000;

    if (est_entity_id) {
        var est_end = end_time > now ? now : end_time;
        try {
            var est_history = await connection.sendMessagePromise({
                type: 'history/history_during_period',
                start_time: start_time.toISOString(),
                end_time: est_end.toISOString(),
                entity_ids: [est_entity_id],
                minimal_response: true,
                no_attributes: true
            });

            if (est_history && est_history[est_entity_id]) {
                est_history[est_entity_id].forEach(function(item) {
                    var val = parseFloat(item.s);
                    if (!isNaN(val)) {
                        var ts = new Date(item.lu * 1000);
                        if (typeof solar_production_chart !== 'undefined' && solar_production_chart) {
                            solar_production_chart.data.datasets[1].data.push({ x: ts, y: val });
                        }
                    }
                });
            }
        } catch (error) {
            console.error('Error fetching forecast history:', error);
        }
    }

    if (offset_entity_id) {
        var offset_start = new Date(start_time.getTime() - twenty_four_hours);
        var offset_end = new Date(Math.min(end_time.getTime() - twenty_four_hours, now.getTime()));

        if (offset_end > offset_start) {
            try {
                var offset_history = await connection.sendMessagePromise({
                    type: 'history/history_during_period',
                    start_time: offset_start.toISOString(),
                    end_time: offset_end.toISOString(),
                    entity_ids: [offset_entity_id],
                    minimal_response: true,
                    no_attributes: true
                });

                if (offset_history && offset_history[offset_entity_id]) {
                    offset_history[offset_entity_id].forEach(function(item) {
                        var val = parseFloat(item.s);
                        if (!isNaN(val)) {
                            var shifted_ts = new Date(item.lu * 1000 + twenty_four_hours);
                            if (shifted_ts > now && typeof solar_production_chart !== 'undefined' && solar_production_chart) {
                                solar_production_chart.data.datasets[1].data.push({ x: shifted_ts, y: val });
                            }
                        }
                    });
                }
            } catch (error) {
                console.error('Error fetching offset forecast history:', error);
            }
        }
    }

    if (typeof solar_production_chart !== 'undefined' && solar_production_chart) {
        solar_production_chart.data.datasets[1].data.sort(function(a, b) { return a.x - b.x; });
        solar_production_chart.update('none');
    }
}

document.addEventListener('DOMContentLoaded', async function() {
    if (typeof create_solar_production_chart === 'function') {
        create_solar_production_chart();
    }

    init_solar_range_controls();

    try {
        ha_connection = await get_ha_connection();

        await fetch_production_history(ha_connection);
        await fetch_forecast_history(ha_connection);

        subscribeEntities(ha_connection, function(entities) {
            update_dashboard(entities);
        });
    } catch (error) {
        console.error('Failed to connect to Home Assistant:', error);
    }
});
