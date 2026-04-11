import { get_ha_connection } from './ha-connection.js';
import { subscribeEntities } from 'https://esm.sh/home-assistant-js-websocket@9.6.0';

const TWO_HOURS_MS = 2 * 60 * 60 * 1000;
const REALTIME_THRESHOLD_MS = 3 * 60 * 1000;
const MAX_POINTS_PER_MINUTE = 5;

let energy_chart = null;
let consumption_chart = null;
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

function reset_range_energy_counters() {
    ['usage', 'production', 'consumption', 'injection'].forEach(key => update_text(`energy-${key}`, '-- kWh'));
}

function update_range_energy_counters() {
    if (!energy_chart || !consumption_chart) return;

    const usage_mode = window.HA_CONFIG.usage_mode || 'auto';
    const usage_dataset = energy_chart.data.datasets[0]?.data || [];
    const production_dataset = energy_chart.data.datasets[1]?.data || [];
    const consumption_dataset = consumption_chart.data.datasets[0]?.data || [];
    const injection_dataset = consumption_chart.data.datasets[1]?.data || [];

    const production_kwh = compute_energy_from_points(production_dataset);
    const consumption_kwh = compute_energy_from_points(consumption_dataset);
    const injection_kwh = compute_energy_from_points(injection_dataset, true);
    const usage_kwh = usage_mode === 'manual'
        ? compute_energy_from_points(usage_dataset)
        : Math.max(0, consumption_kwh + production_kwh - injection_kwh);

    update_text('energy-usage', format_energy(usage_kwh));
    update_text('energy-production', format_energy(production_kwh));
    update_text('energy-consumption', format_energy(consumption_kwh));
    update_text('energy-injection', format_energy(injection_kwh));
}

function reset_today_use_section() {
    update_text('today-total-used', '-- kWh');
    update_text('today-grid-import', '-- kWh');
    update_text('today-direct-solar', '-- kWh');
    update_text('today-grid-export', '-- kWh');
    update_text('today-self-sufficiency', '--%');
    update_text('today-net-grid-balance', '-- kWh');
}

function update_today_use_section() {
    if (!today_history) {
        reset_today_use_section();
        return;
    }

    const usage_mode = window.HA_CONFIG.usage_mode || 'auto';
    const consumption_kwh = compute_energy_from_points(today_history.consumption);
    const injection_kwh = compute_energy_from_points(today_history.injection, true);
    const production_kwh = compute_energy_from_points(today_history.production);
    const usage_kwh = usage_mode === 'manual'
        ? compute_energy_from_points(today_history.usage)
        : Math.max(0, consumption_kwh + production_kwh - injection_kwh);
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
        .map(stat => ({
            x: stat.start,
            y: transform_value(stat.mean)
        }));
}

function build_today_history_from_statistics(statistics_data) {
    const config = window.HA_CONFIG.sensors;
    const usage_mode = window.HA_CONFIG.usage_mode || 'auto';

    return {
        consumption: statistics_to_data_points(statistics_data[config.consumption]),
        injection: statistics_to_data_points(statistics_data[config.injection], value => -value),
        production: statistics_to_data_points(statistics_data[config.production]),
        usage: usage_mode === 'manual'
            ? statistics_to_data_points(statistics_data[config.usage])
            : []
    };
}

function get_history_entity_ids() {
    const config = window.HA_CONFIG.sensors;

    return [
        config.consumption,
        config.injection,
        config.usage,
        config.production
    ].filter(id => id);
}

async function fetch_history_data(connection, start_time, end_time) {
    const entity_ids = get_history_entity_ids();

    if (entity_ids.length === 0) return null;

    return connection.sendMessagePromise({
        type: 'history/history_during_period',
        start_time: start_time.toISOString(),
        end_time: end_time.toISOString(),
        entity_ids: entity_ids,
        minimal_response: true,
        no_attributes: true
    });
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
    const end_time = get_end_time();
    const now = new Date();
    return Math.abs(now.getTime() - end_time.getTime()) < REALTIME_THRESHOLD_MS;
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
    const two_hours_ago = new Date(now.getTime() - TWO_HOURS_MS);
    document.getElementById('range-start').value = format_datetime_local(two_hours_ago);
    document.getElementById('range-end').value = format_datetime_local(now);
    update_live_indicator();
}

function shift_range(offset_ms) {
    const start_input = document.getElementById('range-start');
    const end_input = document.getElementById('range-end');
    let new_start = new Date(new Date(start_input.value).getTime() + offset_ms);
    let new_end = new Date(new Date(end_input.value).getTime() + offset_ms);
    const now = new Date();
    if (new_end.getTime() > now.getTime()) {
        new_end = now;
        new_start = new Date(now.getTime() - TWO_HOURS_MS);
    }
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
    document.getElementById('range-back').addEventListener('click', () => shift_range(-TWO_HOURS_MS));
    document.getElementById('range-forward').addEventListener('click', () => shift_range(TWO_HOURS_MS));
}

async function reload_history() {
    clear_chart(energy_chart);
    clear_chart(consumption_chart);
    reset_range_energy_counters();
    if (ha_connection) {
        await fetch_and_render_history(ha_connection);
        await fetch_and_render_today_details(ha_connection);
    }
}

function compute_usage_from_history(consumption_history, production_history, injection_history) {
    const parse_series = (history) => {
        if (!history) return [];
        return history
            .filter(item => item.s && !isNaN(parseFloat(item.s)))
            .map(item => ({ ts: item.lc || item.lu, val: parseFloat(item.s) }))
            .sort((a, b) => a.ts - b.ts);
    };

    const cons_series = parse_series(consumption_history);
    const prod_series = parse_series(production_history);
    const inj_series = parse_series(injection_history);

    const all_timestamps = new Set();
    [cons_series, prod_series, inj_series].forEach(s => s.forEach(p => all_timestamps.add(p.ts)));
    const sorted_timestamps = [...all_timestamps].sort((a, b) => a - b);

    if (sorted_timestamps.length === 0) return [];

    const last_known_at = (series, t) => {
        let val = 0;
        for (const point of series) {
            if (point.ts > t) break;
            val = point.val;
        }
        return val;
    };

    const all_points = sorted_timestamps.map(t => {
        const cons = last_known_at(cons_series, t);
        const prod = last_known_at(prod_series, t);
        const inj = last_known_at(inj_series, t);
        const usage = Math.max(0, cons + prod - inj);
        return { s: usage.toString(), lc: t };
    });

    if (MAX_POINTS_PER_MINUTE >= 60) return all_points;

    const interval_s = 60 / MAX_POINTS_PER_MINUTE;
    const result = [];
    let i = 0;
    while (i < all_points.length) {
        const minute_start = Math.floor(all_points[i].lc / 60) * 60;
        const minute_end = minute_start + 60;
        const minute_points = [];
        while (i < all_points.length && all_points[i].lc < minute_end) {
            minute_points.push(all_points[i]);
            i++;
        }
        for (let slot = 0; slot < MAX_POINTS_PER_MINUTE; slot++) {
            const slot_start = minute_start + slot * interval_s;
            const slot_end = slot_start + interval_s;
            const slot_points = minute_points.filter(p => p.lc >= slot_start && p.lc < slot_end);
            if (slot_points.length > 0) {
                result.push(slot_points[Math.floor(slot_points.length / 2)]);
            }
        }
    }

    return result;
}

async function fetch_and_render_history(connection) {
    const config = window.HA_CONFIG.sensors;
    const start_time = get_start_time();
    const end_time = get_end_time();

    try {
        const history_data = await fetch_history_data(connection, start_time, end_time);
        if (!history_data) {
            reset_range_energy_counters();
            return;
        }

        const usage_mode = window.HA_CONFIG.usage_mode || 'auto';

        if (usage_mode === 'manual' && history_data[config.usage]) {
            process_history_for_chart(energy_chart, history_data[config.usage], 0);
        }

        if (history_data[config.production]) {
            process_history_for_chart(energy_chart, history_data[config.production], 1, true);
        }

        window.process_activity_history_for_chart(
            consumption_chart,
            history_data[config.consumption],
            history_data[config.injection],
            0,
            value => value
        );

        window.process_activity_history_for_chart(
            consumption_chart,
            history_data[config.injection],
            history_data[config.consumption],
            1,
            value => -value
        );

        if (usage_mode === 'auto') {
            const computed_usage = compute_usage_from_history(
                history_data[config.consumption],
                history_data[config.production],
                history_data[config.injection]
            );
            process_history_for_chart(energy_chart, computed_usage, 0);
        }

        update_range_energy_counters();
    } catch (error) {
        console.error('Error fetching history:', error);
        reset_range_energy_counters();
    }
}

async function fetch_today_statistics(connection) {
    const config = window.HA_CONFIG.sensors;
    const statistic_ids = [config.consumption, config.injection, config.production];

    if (config.usage) statistic_ids.push(config.usage);

    const valid_ids = statistic_ids.filter(id => id);
    if (valid_ids.length === 0) return null;

    return connection.sendMessagePromise({
        type: 'recorder/statistics_during_period',
        start_time: get_start_of_day(new Date()).toISOString(),
        statistic_ids: valid_ids,
        period: '5minute',
        types: ['mean'],
    });
}

async function fetch_and_render_today_details(connection) {
    try {
        const statistics_data = await fetch_today_statistics(connection);

        if (!statistics_data) {
            today_history = null;
            reset_today_use_section();
            return;
        }

        today_history = build_today_history_from_statistics(statistics_data);
        update_today_use_section();
    } catch (error) {
        console.error('Error fetching today statistics:', error);
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

    if (today_history) {
        const now = new Date();

        append_history_point(today_history.consumption, now, consumption.val, false);
        append_history_point(today_history.injection, now, -injection.val, false);
        append_history_point(today_history.production, now, production.val, false);

        if (usage_mode === 'manual') {
            append_history_point(today_history.usage, now, usage.val, false);
        }

        update_today_use_section();
    }

    if (!is_realtime_window()) return;

    const now = new Date();
    const start_time = get_start_time();

    document.getElementById('range-end').value = format_datetime_local(now);

    if (energy_chart) {
        update_chart_realtime(energy_chart, now, [computed_usage.val, production.val], start_time);
    }
    if (consumption_chart) {
        update_chart_realtime(consumption_chart, now, [
            consumption.val === 0 ? null : consumption.val,
            injection.val === 0 ? null : -injection.val
        ], start_time);
    }

    update_range_energy_counters();
}

function update_text(element_id, text) {
    const el = document.getElementById(element_id);
    if (el) el.innerText = text;
}

document.addEventListener('DOMContentLoaded', async function () {
    energy_chart = create_energy_chart();
    consumption_chart = create_consumption_chart();

    init_range_controls();
    reset_range_energy_counters();
    reset_today_use_section();

    ha_connection = await get_ha_connection();

    await fetch_and_render_history(ha_connection);
    await fetch_and_render_today_details(ha_connection);

    subscribeEntities(ha_connection, (entities) => {
        update_dashboard(entities);
    });
});
