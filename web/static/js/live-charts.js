const MAX_POINTS_PER_MINUTE = 6;

const CHART_COLORS = {
    usage: { border: '#1e90ff', bg: 'rgba(30, 144, 255, 0.1)' },
    production: { border: '#ebe730', bg: 'rgba(235, 231, 48, 0.1)' },
    consumption: { border: '#ff8c42', bg: 'rgba(255, 140, 66, 0.1)' },
    injection: { border: '#00d97e', bg: 'rgba(0, 217, 126, 0.1)' }
};

function build_chart_options() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: { legend: { position: 'top' } },
        elements: { point: { radius: 0 } },
        scales: {
            x: {
                type: 'time',
                time: { unit: 'minute', displayFormats: { minute: 'HH:mm' } },
                title: { display: true, text: 'Time' }
            },
            y: {
                beginAtZero: true,
                suggestedMax: 3,
                title: { display: true, text: 'Power (kW)' }
            }
        }
    };
}

function build_dataset(label, color_key, overrides = {}) {
    const c = CHART_COLORS[color_key];
    return {
        label: label,
        data: [],
        borderColor: c.border,
        backgroundColor: c.bg,
        tension: 0.3,
        fill: true,
        spanGaps: false,
        ...overrides
    };
}

function create_energy_chart() {
    const ctx = document.getElementById('energyChart').getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [
                build_dataset('Usage', 'usage'),
                build_dataset('Production', 'production')
            ]
        },
        options: build_chart_options()
    });
}

function create_consumption_chart() {
    const ctx = document.getElementById('consumptionChart').getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [
                build_dataset('Consumption', 'consumption', {
                    tension: 0.2,
                    pointHoverRadius: context => context.raw && context.raw.y !== null ? 4 : 0,
                }),
                build_dataset('Injection', 'injection', {
                    tension: 0.2,
                    pointHoverRadius: context => context.raw && context.raw.y !== null ? 4 : 0,
                })
            ]
        },
        options: build_chart_options()
    });
}

function clear_chart(chart) {
    chart.data.datasets.forEach(ds => ds.data = []);
    chart.update('none');
}

function downsample_points(points, preserve_gaps = false) {
    if (points.length === 0 || MAX_POINTS_PER_MINUTE >= 60) return points;

    if (preserve_gaps) {
        const result = [];
        let segment = [];

        points.forEach(point => {
            if (point.y === null) {
                result.push(...downsample_points(segment, false));
                segment = [];
                result.push(point);
                return;
            }

            segment.push(point);
        });

        result.push(...downsample_points(segment, false));
        return result;
    }

    const interval_ms = 60000 / MAX_POINTS_PER_MINUTE;
    const result = [];
    let i = 0;
    while (i < points.length) {
        const minute_start = Math.floor(points[i].x / 60000) * 60000;
        const minute_end = minute_start + 60000;
        const minute_points = [];
        while (i < points.length && points[i].x < minute_end) {
            minute_points.push(points[i]);
            i++;
        }
        for (let slot = 0; slot < MAX_POINTS_PER_MINUTE; slot++) {
            const slot_start = minute_start + slot * interval_ms;
            const slot_end = slot_start + interval_ms;
            const slot_points = minute_points.filter(p => p.x >= slot_start && p.x < slot_end);
            if (slot_points.length > 0) {
                result.push(slot_points[Math.floor(slot_points.length / 2)]);
            }
        }
    }
    return result;
}

function parse_history_points(entity_history, transform_value = value => value, nullify_zero = false) {
    if (!entity_history || entity_history.length === 0) return [];

    return entity_history
        .filter(item => item.s && !isNaN(parseFloat(item.s)))
        .map(item => {
            const value = transform_value(parseFloat(item.s));
            return {
                x: new Date((item.lc || item.lu) * 1000).getTime(),
                y: nullify_zero && value === 0 ? null : value
            };
        })
        .sort((a, b) => a.x - b.x);
}

function set_chart_dataset(chart, dataset_index, data_points, preserve_gaps = false) {
    chart.data.datasets[dataset_index].data = downsample_points(data_points, preserve_gaps);
    chart.update('none');
}

function process_history_for_chart(chart, entity_history, dataset_index, nullify_zero = false, transform_value = value => value) {
    if (!entity_history || entity_history.length === 0) return;

    const data_points = parse_history_points(entity_history, transform_value, nullify_zero);

    set_chart_dataset(chart, dataset_index, data_points, nullify_zero);
}

function process_activity_history_for_chart(chart, entity_history, opposing_history, dataset_index, transform_value = value => value) {
    const own_points = parse_history_points(entity_history, value => value, false);
    const opposing_points = parse_history_points(opposing_history, value => value, false)
        .filter(point => point.y !== null && point.y > 0);

    const own_values = new Map(own_points.map(point => [point.x, point.y]));
    const timestamps = [...new Set([
        ...own_points.map(point => point.x),
        ...opposing_points.map(point => point.x)
    ])].sort((a, b) => a - b);

    const data_points = timestamps.map(timestamp => {
        const own_value = own_values.has(timestamp) ? own_values.get(timestamp) : null;

        return {
            x: timestamp,
            y: own_value !== null && own_value > 0 ? transform_value(own_value) : null
        };
    });

    set_chart_dataset(chart, dataset_index, data_points, true);
}

function update_chart_realtime(chart, timestamp, data_points, start_time) {
    chart.data.datasets.forEach((dataset, index) => {
        if (data_points[index] !== undefined) {
            dataset.data.push({ x: timestamp, y: data_points[index] });
            dataset.data = dataset.data.filter(point => point.x > start_time.getTime());
        }
    });
    chart.update('none');
}
