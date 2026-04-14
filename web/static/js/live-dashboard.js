import { get_ha_connection } from './ha-connection.js';
import { subscribeEntities } from 'https://esm.sh/home-assistant-js-websocket@9.6.0';

const FULL_DAY_MS = 24 * 60 * 60 * 1000;

let energy_chart = null;
let consumption_chart = null;
let price_chart = null;
let ha_connection = null;
let today_history = null;

function format_power(value, unit = 'kW') {
    if (value === null || value === undefined || isNaN(value)) return `-- ${unit}`;
    return `${Number(value).toFixed(3)} ${unit}`;
}

function format_energy(value) {
    if (value === null || value === undefined || isNaN(value)) return '-- kWh';

    const normalized_value = Number(value);

    if (Math.abs(normalized_value) >= 1000) {
        return `${(normalized_value / 1000).toFixed(2)} MWh`;
    }

    return `${normalized_value.toFixed(2)} kWh`;
}

function get_start_of_day(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function compute_energy_from_points(data_points, absolute = false) {
    if (!data_points || data_points.length < 2) return 0;

    let total_kwh = 0;

    for (let index = 1; index < data_points.length; index++) {
        const previous_point = data_points[index - 1];
        const current_point = data_points[index];

        if (previous_point.y === null || current_point.y === null) {
            continue;
        }

        const previous_value = absolute ? Math.abs(previous_point.y) : previous_point.y;
        const current_value = absolute ? Math.abs(current_point.y) : current_point.y;
        const hours_between = (current_point.x - previous_point.x) / 3600000;

        total_kwh += ((previous_value + current_value) / 2) * hours_between;
    }

    return Math.max(0, total_kwh);
}

function reset_today_use_section() {
    update_text('today-total-used', '-- kWh');
    update_text('today-grid-import', '--');
    update_text('today-direct-solar', '--');
    update_text('today-grid-export', '--');
    update_text('today-self-sufficiency', '--%');
    update_text('today-net-grid-balance', '-- kWh');
    update_text('today-total-production', '-- kWh');
    reset_energy_flow();
}

function update_today_use_section() {
    if (!today_history) {
        reset_today_use_section();
        return;
    }

    const consumption_kwh = compute_energy_from_points(today_history.consumption);
    const injection_kwh = compute_energy_from_points(today_history.injection);
    const production_kwh = compute_energy_from_points(today_history.production);
    const usage_kwh = compute_energy_from_points(today_history.usage);
    const direct_solar_kwh = Math.max(0, usage_kwh - consumption_kwh);
    const net_grid_balance = injection_kwh - consumption_kwh;
    const net_balance_prefix = net_grid_balance > 0 ? '+' : net_grid_balance < 0 ? '-' : '';
    const self_sufficiency = usage_kwh > 0
        ? `${Math.round((direct_solar_kwh / usage_kwh) * 100)}%`
        : '0%';

    update_text('today-total-used', format_energy(usage_kwh));
    update_text('today-grid-import', format_energy(consumption_kwh));
    update_text('today-direct-solar', format_energy(direct_solar_kwh));
    update_text('today-grid-export', format_energy(injection_kwh));
    update_text('today-self-sufficiency', self_sufficiency);
    update_text('today-net-grid-balance', `${net_balance_prefix}${format_energy(Math.abs(net_grid_balance))}`);
    update_text('today-total-production', format_energy(production_kwh));
    update_energy_flow(consumption_kwh, direct_solar_kwh, injection_kwh, production_kwh);
}

function append_history_point(data_points, timestamp, value, nullify_zero = false) {
    if (!Array.isArray(data_points)) return;

    const normalized_value = value === null || value === undefined || isNaN(value)
        ? null
        : nullify_zero && value === 0
            ? null
            : value;
    const last_point = data_points[data_points.length - 1];

    if (last_point && last_point.x === timestamp.getTime()) {
        last_point.y = normalized_value;
        return;
    }

    data_points.push({ x: timestamp.getTime(), y: normalized_value });
}

function statistics_to_data_points(statistics, transform_value = value => value) {
    if (!statistics || statistics.length === 0) return [];

    return statistics
        .filter(stat => stat.mean !== null && stat.mean !== undefined)
        .map(stat => {
            const ts = stat.start < 1e12 ? stat.start * 1000 : stat.start;
            return { x: ts, y: transform_value(stat.mean) };
        });
}

function get_history_timestamps(series_collection) {
    return [...new Set(series_collection.flatMap(series => series.map(point => point.x)))].sort((a, b) => a - b);
}

function align_history_points(data_points, timestamps) {
    const points_by_timestamp = new Map(data_points.map(point => [point.x, point.y]));

    return timestamps.map(timestamp => ({
        x: timestamp,
        y: points_by_timestamp.get(timestamp) ?? 0,
    }));
}

function build_auto_usage_points(consumption_points, production_points, injection_points, timestamps) {
    const aligned_consumption = align_history_points(consumption_points, timestamps);
    const aligned_production = align_history_points(production_points, timestamps);
    const aligned_injection = align_history_points(injection_points, timestamps);

    return timestamps.map((timestamp, index) => ({
        x: timestamp,
        y: Math.max(
            0,
            aligned_consumption[index].y + aligned_production[index].y - aligned_injection[index].y,
        ),
    }));
}

function get_start_time() {
    return new Date(document.getElementById('range-start').value);
}

function get_end_time() {
    return new Date(document.getElementById('range-end').value);
}

function format_datetime_local(date) {
    const pad = n => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function is_realtime_window() {
    const now = new Date();
    return now >= get_start_time() && now <= get_end_time();
}

function update_live_indicator() {
    const indicator = document.getElementById('live-indicator');
    if (!indicator) return;
    if (is_realtime_window()) {
        indicator.classList.add('active');
    } else {
        indicator.classList.remove('active');
    }
}

function init_range_defaults() {
    const now = new Date();
    const start_of_day = get_start_of_day(now);
    const end_of_day = new Date(start_of_day.getTime() + FULL_DAY_MS);
    document.getElementById('range-start').value = format_datetime_local(start_of_day);
    document.getElementById('range-end').value = format_datetime_local(end_of_day);
    update_live_indicator();
}

function shift_range(offset_ms) {
    const start_input = document.getElementById('range-start');
    const end_input = document.getElementById('range-end');
    const new_start = new Date(new Date(start_input.value).getTime() + offset_ms);
    const new_end = new Date(new Date(end_input.value).getTime() + offset_ms);
    start_input.value = format_datetime_local(new_start);
    end_input.value = format_datetime_local(new_end);
    update_live_indicator();
    reload_history();
}

function on_range_change() {
    update_live_indicator();
    reload_history();
}

function init_range_controls() {
    init_range_defaults();

    document.getElementById('range-start').addEventListener('change', on_range_change);
    document.getElementById('range-end').addEventListener('change', on_range_change);
    document.getElementById('range-back').addEventListener('click', () => shift_range(-FULL_DAY_MS));
    document.getElementById('range-forward').addEventListener('click', () => shift_range(FULL_DAY_MS));
}

async function reload_history() {
    clear_chart(energy_chart);
    clear_chart(consumption_chart);
    if (price_chart) clear_chart(price_chart);
    if (typeof clear_solar_charts === 'function') clear_solar_charts();

    if (ha_connection) {
        const start_time = get_start_time();
        const end_time = get_end_time();

        if (price_chart) {
            price_chart.options.scales.x.min = start_time;
            price_chart.options.scales.x.max = end_time;
            price_chart.update('none');
        }
        if (typeof update_solar_chart_range === 'function') {
            update_solar_chart_range(start_time, end_time);
        }

        await fetch_and_render_statistics(ha_connection);
        await fetch_and_render_price_history(ha_connection);
        await fetch_and_render_solar_history(ha_connection);
    }
}

async function fetch_and_render_statistics(connection) {
    const config = window.HA_CONFIG.sensors;
    const statistic_ids = [config.consumption, config.injection, config.production];
    if (config.usage) statistic_ids.push(config.usage);
    const valid_ids = statistic_ids.filter(id => id);

    if (valid_ids.length === 0) {
        today_history = null;
        reset_today_use_section();
        return;
    }

    const start_time = get_start_time();
    const now = new Date();
    const end_time = new Date(Math.min(get_end_time().getTime(), now.getTime()));

    try {
        const stats = await connection.sendMessagePromise({
            type: 'recorder/statistics_during_period',
            start_time: start_time.toISOString(),
            end_time: end_time.toISOString(),
            statistic_ids: valid_ids,
            period: '5minute',
            types: ['mean'],
        });

        if (!stats) {
            today_history = null;
            reset_today_use_section();
            return;
        }

        const consumption_points = statistics_to_data_points(stats[config.consumption]);
        const injection_points = statistics_to_data_points(stats[config.injection]);
        const production_points = statistics_to_data_points(stats[config.production]);

        const usage_mode = window.HA_CONFIG.usage_mode || 'auto';
        const manual_usage_points = usage_mode === 'manual' && config.usage
            ? statistics_to_data_points(stats[config.usage])
            : [];
        const timestamps = get_history_timestamps([
            consumption_points,
            injection_points,
            production_points,
            manual_usage_points,
        ]);

        const aligned_consumption_points = align_history_points(consumption_points, timestamps);
        const aligned_injection_points = align_history_points(injection_points, timestamps);
        const aligned_production_points = align_history_points(production_points, timestamps);
        let usage_points;

        if (usage_mode === 'manual' && config.usage) {
            usage_points = align_history_points(manual_usage_points, timestamps);
        } else {
            usage_points = build_auto_usage_points(
                aligned_consumption_points,
                aligned_production_points,
                aligned_injection_points,
                timestamps,
            );
        }

        set_chart_dataset(energy_chart, 0, usage_points);
        set_chart_dataset(energy_chart, 1, aligned_production_points.map(p => ({
            x: p.x, y: p.y > 0.001 ? p.y : null
        })));

        set_chart_dataset(consumption_chart, 0, aligned_consumption_points.map(p => ({
            x: p.x, y: p.y > 0.001 ? p.y : null
        })), true);
        set_chart_dataset(consumption_chart, 1, aligned_injection_points.map(p => ({
            x: p.x, y: p.y > 0.001 ? -p.y : null
        })), true);

        today_history = {
            consumption: aligned_consumption_points,
            injection: aligned_injection_points,
            production: aligned_production_points,
            usage: usage_points,
        };
        update_today_use_section();
    } catch (error) {
        console.error('Error fetching statistics:', error);
        today_history = null;
        reset_today_use_section();
    }
}

function update_dashboard(entities) {
    const config = window.HA_CONFIG.sensors;

    const get_entity_data = (entity_id) => {
        if (!entity_id || !entities[entity_id]) return { val: 0, unit: 'kW', text: '-- kW' };
        const state = entities[entity_id].state;
        const unit = entities[entity_id].attributes?.unit_of_measurement || 'kW';
        const numeric_state = parseFloat(state);
        return {
            val: isNaN(numeric_state) ? 0 : numeric_state,
            unit: unit,
            text: isNaN(numeric_state) ? `-- ${unit}` : format_power(numeric_state, unit)
        };
    };

    const usage = get_entity_data(config.usage);
    const production = get_entity_data(config.production);
    const consumption = get_entity_data(config.consumption);
    const injection = get_entity_data(config.injection);

    const usage_mode = window.HA_CONFIG.usage_mode || 'auto';
    let computed_usage = usage;
    if (usage_mode === 'auto') {
        const auto_val = consumption.val + production.val - injection.val;
        const clamped = Math.max(0, auto_val);
        computed_usage = { val: clamped, unit: 'kW', text: format_power(clamped) };
    }

    update_text('val-usage', computed_usage.text);
    update_text('val-production', production.text);
    update_text('val-consumption', consumption.text);
    update_text('val-injection', injection.text);

    if (!is_realtime_window()) return;

    const now = new Date();
    const start_time = get_start_time();

    if (today_history) {
        append_history_point(today_history.consumption, now, consumption.val, false);
        append_history_point(today_history.injection, now, injection.val, false);
        append_history_point(today_history.production, now, production.val, false);

        append_history_point(today_history.usage, now, computed_usage.val, false);
        update_today_use_section();
    }

    if (energy_chart) {
        update_chart_realtime(energy_chart, now, [computed_usage.val, production.val], start_time);
    }
    if (consumption_chart) {
        update_chart_realtime(consumption_chart, now, [
            consumption.val === 0 ? null : consumption.val,
            injection.val === 0 ? null : -injection.val
        ], start_time);
    }
}

function update_energy_flow(import_kwh, self_kwh, export_kwh, production_kwh) {
    const usage_kwh = import_kwh + self_kwh;

    const set_flex = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.style.flex = value > 0 ? String(value) : '0.001';
    };

    set_flex('flow-seg-import', import_kwh);
    set_flex('flow-seg-self', self_kwh);
    set_flex('flow-seg-export', export_kwh);

    set_flex('flow-total-usage', usage_kwh);
    set_flex('flow-total-production', production_kwh);
}

function reset_energy_flow() {
    ['flow-seg-import', 'flow-seg-self', 'flow-seg-export', 'flow-total-usage', 'flow-total-production'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.flex = '1';
    });
}

function update_text(element_id, text) {
    const el = document.getElementById(element_id);
    if (el) el.innerText = text;
}

async function fetch_and_render_price_history(connection) {
    const price_sensors = window.HA_CONFIG.price_sensors || [];
    if (!price_chart || price_sensors.length === 0) return;

    const start_time = get_start_time();
    const end_time = get_end_time();
    const entity_ids = price_sensors.map(s => s.entity_id).filter(id => id);

    if (entity_ids.length === 0) return;

    try {
        const history_data = await connection.sendMessagePromise({
            type: 'history/history_during_period',
            start_time: start_time.toISOString(),
            end_time: end_time.toISOString(),
            entity_ids: entity_ids,
            minimal_response: true,
            no_attributes: true
        });

        if (!history_data) return;

        price_sensors.forEach((sensor, index) => {
            const entity_history = history_data[sensor.entity_id];
            if (!entity_history) return;

            const data_points = entity_history
                .filter(item => item.s && !isNaN(parseFloat(item.s)))
                .map(item => ({
                    x: new Date((item.lc || item.lu) * 1000).getTime(),
                    y: parseFloat(item.s)
                }))
                .sort((a, b) => a.x - b.x);

            price_chart.data.datasets[index].data = data_points;
        });

        price_chart.update('none');
    } catch (error) {
        console.error('Error fetching price history:', error);
    }
}

function update_price_chart_realtime(entities) {
    const price_sensors = window.HA_CONFIG.price_sensors || [];
    if (!price_chart || price_sensors.length === 0) return;

    const now = new Date();

    price_sensors.forEach((sensor, index) => {
        if (!sensor.entity_id || !entities[sensor.entity_id]) return;
        const state = parseFloat(entities[sensor.entity_id].state);
        if (isNaN(state)) return;

        const dataset = price_chart.data.datasets[index];
        const last = dataset.data.length > 0 ? dataset.data[dataset.data.length - 1] : null;

        if (last && (now.getTime() - last.x) < 60000) {
            last.x = now.getTime();
            last.y = state;
        } else {
            dataset.data.push({ x: now.getTime(), y: state });
        }
    });

    price_chart.update('none');
}

async function fetch_and_render_solar_history(connection) {
    if (!window.HA_CONFIG.solar_configured) return;
    if (typeof solar_production_chart === 'undefined' || !solar_production_chart) return;

    const sensors = window.HA_CONFIG.solar_sensors;
    const now = new Date();
    const start_of_day = get_start_time();
    const end_of_day = get_end_time();

    if (sensors.actual_production) {
        try {
            const end_time = end_of_day > now ? now : end_of_day;
            const history_data = await connection.sendMessagePromise({
                type: 'history/history_during_period',
                start_time: start_of_day.toISOString(),
                end_time: end_time.toISOString(),
                entity_ids: [sensors.actual_production],
                minimal_response: true,
                no_attributes: true
            });

            if (history_data && history_data[sensors.actual_production]) {
                history_data[sensors.actual_production].forEach(item => {
                    const val = parseFloat(item.s);
                    if (!isNaN(val)) {
                        solar_production_chart.data.datasets[0].data.push({
                            x: new Date(item.lu * 1000),
                            y: val
                        });
                    }
                });
                solar_production_chart.update('none');
            }
        } catch (error) {
            console.error('Error fetching solar production history:', error);
        }
    }

    const est_entity_id = sensors.estimated_actual_production;
    const offset_entity_id = sensors.estimated_actual_production_offset_day;

    if (est_entity_id) {
        try {
            const est_end = end_of_day > now ? now : end_of_day;
            const est_history = await connection.sendMessagePromise({
                type: 'history/history_during_period',
                start_time: start_of_day.toISOString(),
                end_time: est_end.toISOString(),
                entity_ids: [est_entity_id],
                minimal_response: true,
                no_attributes: true
            });

            if (est_history && est_history[est_entity_id]) {
                est_history[est_entity_id].forEach(item => {
                    const val = parseFloat(item.s);
                    if (!isNaN(val)) {
                        solar_production_chart.data.datasets[1].data.push({
                            x: new Date(item.lu * 1000),
                            y: val
                        });
                    }
                });
            }
        } catch (error) {
            console.error('Error fetching forecast history:', error);
        }
    }

    if (offset_entity_id) {
        const offset_start = new Date(start_of_day.getTime() - FULL_DAY_MS);
        const offset_end = new Date(Math.min(end_of_day.getTime() - FULL_DAY_MS, now.getTime()));

        if (offset_end > offset_start) {
            try {
                const offset_history = await connection.sendMessagePromise({
                    type: 'history/history_during_period',
                    start_time: offset_start.toISOString(),
                    end_time: offset_end.toISOString(),
                    entity_ids: [offset_entity_id],
                    minimal_response: true,
                    no_attributes: true
                });

                if (offset_history && offset_history[offset_entity_id]) {
                    offset_history[offset_entity_id].forEach(item => {
                        const val = parseFloat(item.s);
                        if (!isNaN(val)) {
                            const shifted_ts = new Date(item.lu * 1000 + FULL_DAY_MS);
                            if (shifted_ts > now) {
                                solar_production_chart.data.datasets[1].data.push({
                                    x: shifted_ts,
                                    y: val
                                });
                            }
                        }
                    });
                }
            } catch (error) {
                console.error('Error fetching offset forecast history:', error);
            }
        }
    }

    solar_production_chart.data.datasets[1].data.sort((a, b) => a.x - b.x);
    solar_production_chart.update('none');
}

function update_solar_chart_live(entities) {
    if (!window.HA_CONFIG.solar_configured) return;
    if (typeof solar_production_chart === 'undefined' || !solar_production_chart) return;

    const sensors = window.HA_CONFIG.solar_sensors;
    if (!sensors.actual_production || !entities[sensors.actual_production]) return;

    const val = parseFloat(entities[sensors.actual_production].state);
    if (isNaN(val)) return;

    if (typeof update_solar_production_chart_realtime === 'function') {
        update_solar_production_chart_realtime(new Date(), val);
    }
}

document.addEventListener('DOMContentLoaded', async function () {
    init_range_controls();

    const start_time = get_start_time();
    const end_time = get_end_time();

    energy_chart = create_energy_chart();
    consumption_chart = create_consumption_chart();

    const price_sensors = window.HA_CONFIG.price_sensors || [];
    if (price_sensors.length > 0) {
        price_chart = create_price_chart(price_sensors, start_time, end_time);
    }

    if (window.HA_CONFIG.solar_configured && typeof create_solar_production_chart === 'function') {
        create_solar_production_chart();
        if (typeof update_solar_chart_range === 'function') {
            update_solar_chart_range(start_time, end_time);
        }
    }

    reset_today_use_section();

    ha_connection = await get_ha_connection();

    await fetch_and_render_statistics(ha_connection);
    await fetch_and_render_price_history(ha_connection);
    await fetch_and_render_solar_history(ha_connection);

    subscribeEntities(ha_connection, (entities) => {
        update_dashboard(entities);
        if (is_realtime_window()) {
            update_price_chart_realtime(entities);
            update_solar_chart_live(entities);
        }
    });
});
