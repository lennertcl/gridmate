import { get_ha_connection } from './ha-connection.js';
import { subscribeEntities } from 'https://esm.sh/home-assistant-js-websocket@9.6.0';

const TWO_HOURS_MS = 2 * 60 * 60 * 1000;
const REALTIME_THRESHOLD_MS = 3 * 60 * 1000;
const MAX_POINTS_PER_MINUTE = 5;

let energy_chart = null;
let consumption_chart = null;
let ha_connection = null;

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
    if (ha_connection) {
        await fetch_and_render_history(ha_connection);
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

    const entity_ids = [
        config.consumption,
        config.injection,
        config.usage,
        config.production
    ].filter(id => id);

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

        const usage_mode = window.HA_CONFIG.usage_mode || 'auto';

        if (usage_mode === 'manual' && history_data[config.usage]) {
            process_history_for_chart(energy_chart, history_data[config.usage], 0);
        }

        if (history_data[config.production]) {
            process_history_for_chart(energy_chart, history_data[config.production], 1);
        }

        if (history_data[config.consumption]) {
            process_history_for_chart(consumption_chart, history_data[config.consumption], 0, true);
        }

        if (history_data[config.injection]) {
            history_data[config.injection].forEach(item => {
                if (item.s && !isNaN(parseFloat(item.s))) {
                    item.s = (-parseFloat(item.s)).toString();
                }
            });
            process_history_for_chart(consumption_chart, history_data[config.injection], 1, true);
        }

        if (usage_mode === 'auto') {
            const computed_usage = compute_usage_from_history(
                history_data[config.consumption],
                history_data[config.production],
                history_data[config.injection]
            );
            process_history_for_chart(energy_chart, computed_usage, 0);
        }
    } catch (error) {
        console.error('Error fetching history:', error);
    }
}

function update_dashboard(entities) {
    const config = window.HA_CONFIG.sensors;

    const get_entity_data = (entity_id) => {
        if (!entity_id || !entities[entity_id]) return { val: 0, text: '--' };
        const state = entities[entity_id].state;
        const unit = entities[entity_id].attributes?.unit_of_measurement || 'kW';
        const numeric_state = parseFloat(state);
        return {
            val: isNaN(numeric_state) ? 0 : numeric_state,
            text: isNaN(numeric_state) ? '--' : `${state} ${unit}`
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
        computed_usage = { val: clamped, text: clamped.toFixed(3) + ' kW' };
    }

    update_text('val-usage', computed_usage.text);
    update_text('val-production', production.text);
    update_text('val-consumption', consumption.text);
    update_text('val-injection', injection.text);

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
}

function update_text(element_id, text) {
    const el = document.getElementById(element_id);
    if (el) el.innerText = text;
}

document.addEventListener('DOMContentLoaded', async function () {
    energy_chart = create_energy_chart();
    consumption_chart = create_consumption_chart();

    init_range_controls();

    ha_connection = await get_ha_connection();

    await fetch_and_render_history(ha_connection);

    subscribeEntities(ha_connection, (entities) => {
        update_dashboard(entities);
    });
});
