var solar_production_chart = null;

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
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', labels: { usePointStyle: true, padding: 16 } },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            return ctx.dataset.label + ': ' + (ctx.parsed.y !== null ? ctx.parsed.y.toFixed(2) + ' kW' : 'N/A');
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
