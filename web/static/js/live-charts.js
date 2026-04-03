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

function build_dataset(label, color_key) {
    const c = CHART_COLORS[color_key];
    return {
        label: label,
        data: [],
        borderColor: c.border,
        backgroundColor: c.bg,
        tension: 0.3,
        fill: true
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
                build_dataset('Consumption', 'consumption'),
                build_dataset('Injection', 'injection')
            ]
        },
        options: build_chart_options()
    });
}

function clear_chart(chart) {
    chart.data.datasets.forEach(ds => ds.data = []);
    chart.update('none');
}

function downsample_points(points) {
    if (points.length === 0 || MAX_POINTS_PER_MINUTE >= 60) return points;
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

function process_history_for_chart(chart, entity_history, dataset_index, nullify_zero = false) {
    if (!entity_history || entity_history.length === 0) return;

    const data_points = entity_history
        .filter(item => item.s && !isNaN(parseFloat(item.s)))
        .map(item => {
            const val = parseFloat(item.s);
            return {
                x: new Date((item.lc || item.lu) * 1000).getTime(),
                y: (nullify_zero && val === 0) ? null : val
            };
        });

    chart.data.datasets[dataset_index].data = downsample_points(data_points);
    chart.update('none');
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
