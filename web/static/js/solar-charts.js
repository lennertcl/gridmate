var solar_production_chart = null;
var solar_tooltip_time_formatter = new Intl.DateTimeFormat(undefined, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit'
});

function get_solar_point_timestamp(point) {
    if (!point || point.x === null || point.x === undefined) return null;

    var timestamp = point.x instanceof Date ? point.x.getTime() : new Date(point.x).getTime();
    return isNaN(timestamp) ? null : timestamp;
}

function find_solar_dataset_index_at_time(dataset, hover_timestamp, prefer_previous) {
    if (!dataset || !dataset.data || dataset.data.length === 0) return -1;

    var best_index = -1;
    var best_distance = Infinity;
    var previous_index = -1;
    var previous_timestamp = -Infinity;

    dataset.data.forEach(function(point, index) {
        if (!point || point.y === null || point.y === undefined) return;

        var point_timestamp = get_solar_point_timestamp(point);
        if (point_timestamp === null) return;

        if (prefer_previous && point_timestamp <= hover_timestamp && point_timestamp >= previous_timestamp) {
            previous_timestamp = point_timestamp;
            previous_index = index;
        }

        var distance = Math.abs(point_timestamp - hover_timestamp);
        if (distance < best_distance) {
            best_distance = distance;
            best_index = index;
        }
    });

    if (prefer_previous && previous_index !== -1) return previous_index;
    return best_index;
}

function get_solar_hover_items(chart, event, _use_final_position) {
    if (!chart || !chart.scales || !chart.scales.x) return [];

    var position = Chart.helpers.getRelativePosition(event, chart);
    var hover_timestamp = chart.scales.x.getValueForPixel(position.x);
    if (hover_timestamp === null || hover_timestamp === undefined) return [];

    var items = [];

    chart.data.datasets.forEach(function(dataset, dataset_index) {
        var point_index = find_solar_dataset_index_at_time(dataset, hover_timestamp, dataset.type === 'bar');
        if (point_index === -1) return;

        var meta = chart.getDatasetMeta(dataset_index);
        if (!meta || !meta.data || !meta.data[point_index]) return;

        items.push({
            datasetIndex: dataset_index,
            index: point_index,
            element: meta.data[point_index]
        });
    });

    return items;
}

if (Chart.Interaction && Chart.Interaction.modes && !Chart.Interaction.modes.solar_hover) {
    Chart.Interaction.modes.solar_hover = function(chart, event, options, use_final_position) {
        return get_solar_hover_items(chart, event, use_final_position);
    };
}

function format_solar_tooltip_time(value) {
    if (value === null || value === undefined) return 'Unknown time';

    var timestamp = value instanceof Date ? value : new Date(value);
    if (isNaN(timestamp.getTime())) return 'Unknown time';

    return solar_tooltip_time_formatter.format(timestamp);
}

function create_solar_production_chart() {
    var ctx = document.getElementById('solar-production-chart');
    if (!ctx) return null;

    var now = new Date();
    var start_of_day = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var end_of_day = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);

    solar_production_chart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            datasets: [
                {
                    type: 'bar',
                    label: 'Actual Production (kW)',
                    data: [],
                    borderColor: '#ebe730',
                    backgroundColor: 'rgba(235, 231, 48, 0.45)',
                    borderWidth: 1,
                    barThickness: 'flex',
                    barPercentage: .8,
                    categoryPercentage: 1,
                    order: 1,
                },
                {
                    label: 'Forecast (kW)',
                    data: [],
                    borderColor: '#1e90ff',
                    backgroundColor: 'rgba(30, 144, 255, 0.05)',
                    borderWidth: 2,
                    borderDash: [6, 4],
                    tension: 0.35,
                    fill: false,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    order: 0,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: { mode: 'solar_hover', axis: 'x', intersect: false },
            plugins: {
                legend: { position: 'top', labels: { usePointStyle: true, padding: 16 } },
                tooltip: {
                    mode: 'solar_hover',
                    axis: 'x',
                    intersect: false,
                    position: 'nearest',
                    callbacks: {
                        title: function() {
                            return '';
                        },
                        label: function(ctx) {
                            var formatted_time = format_solar_tooltip_time(ctx.parsed.x);
                            var formatted_value = ctx.parsed.y !== null ? ctx.parsed.y.toFixed(2) + ' kW' : 'N/A';
                            return ctx.dataset.label + ' (' + formatted_time + '): ' + formatted_value;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: { unit: 'hour', displayFormats: { hour: 'HH:mm' }, tooltipFormat: 'HH:mm' },
                    min: start_of_day,
                    max: end_of_day,
                    grid: { display: false },
                    ticks: { maxTicksLimit: 12 }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(0,0,0,0.05)' },
                    ticks: { callback: function(v) { return v + ' kW'; } }
                }
            }
        }
    });

    return solar_production_chart;
}

function update_solar_chart_range(start_time, end_time) {
    if (!solar_production_chart) return;
    solar_production_chart.options.scales.x.min = start_time;
    solar_production_chart.options.scales.x.max = end_time;
    solar_production_chart.update('none');
}

function update_solar_production_chart_realtime(timestamp, actual_value) {
    if (!solar_production_chart) return;
    if (actual_value === null || actual_value === undefined) return;

    var actual_data = solar_production_chart.data.datasets[0].data;
    var parsed_value = parseFloat(actual_value);
    var last = actual_data.length > 0 ? actual_data[actual_data.length - 1] : null;

    if (last && (timestamp - last.x) < 60000) {
        last.x = timestamp;
        last.y = parsed_value;
    } else {
        actual_data.push({ x: timestamp, y: parsed_value });
    }

    solar_production_chart.update('none');
}

function clear_solar_charts() {
    if (solar_production_chart) {
        solar_production_chart.data.datasets.forEach(function(ds) { ds.data = []; });
        solar_production_chart.update('none');
    }
}
