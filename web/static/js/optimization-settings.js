document.addEventListener('DOMContentLoaded', function() {
    checkEmhassConnection();

    var btnTest = document.getElementById('btn-test-connection');
    if (btnTest) {
        btnTest.addEventListener('click', checkEmhassConnection);
    }

    var btnFetch = document.getElementById('btn-fetch-config');
    if (btnFetch) {
        btnFetch.addEventListener('click', fetchEmhassConfig);
    }

    var sourceType = document.getElementById('load_power_source_type');
    if (sourceType) {
        toggleLoadPowerSource(sourceType.value);
        sourceType.addEventListener('change', function() {
            toggleLoadPowerSource(this.value);
        });
    }

    var btnAddBlock = document.getElementById('btn-add-schedule-block');
    if (btnAddBlock) {
        btnAddBlock.addEventListener('click', addScheduleBlock);
    }

    initScheduleBlocks();
});

function checkEmhassConnection() {
    var statusEl = document.getElementById('emhass-status');
    var dot = statusEl.querySelector('.status-dot');
    var text = statusEl.querySelector('.status-text');

    text.textContent = 'Checking...';
    dot.className = 'status-dot';

    var urlField = document.getElementById('emhass_url');
    var url = urlField ? urlField.value.trim() : '';
    var endpoint = '/api/optimization/emhass/status';
    if (url) {
        endpoint += '?url=' + encodeURIComponent(url);
    }

    fetch(baseUrl(endpoint))
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.available) {
                dot.className = 'status-dot connected';
                text.textContent = 'Connected';
            } else {
                dot.className = 'status-dot disconnected';
                text.textContent = 'Not reachable';
            }
        })
        .catch(function() {
            dot.className = 'status-dot disconnected';
            text.textContent = 'Error';
        });
}

function toggleLoadPowerSource(sourceType) {
    var sensorSection = document.getElementById('load-power-sensor-section');
    var scheduleSection = document.getElementById('load-power-schedule-section');
    if (sensorSection) sensorSection.style.display = sourceType === 'sensor' ? 'block' : 'none';
    if (scheduleSection) scheduleSection.style.display = sourceType === 'schedule' ? 'block' : 'none';
}

function initScheduleBlocks() {
    var hidden = document.getElementById('load_power_schedule_blocks');
    if (!hidden) return;

    try {
        var blocks = JSON.parse(hidden.value);
        if (blocks.length === 0) {
            blocks.push({ start_time: '00:00', end_time: '23:59', power_w: 0 });
        };
        blocks.forEach(function(block) {
            renderScheduleBlock(block.start_time, block.end_time, block.power_w);
        });
    } catch (e) {
        console.warn('Failed to parse schedule blocks:', e);
    }
}

function addScheduleBlock() {
    var container = document.getElementById('schedule-blocks-container');
    var existing = container.querySelectorAll('.schedule-block-row');
    var startTime = '00:00';
    if (existing.length > 0) {
        var lastEnd = existing[existing.length - 1].querySelector('.block-end').value;
        startTime = lastEnd;
    }
    renderScheduleBlock(startTime, '23:59', 0);
}

function renderScheduleBlock(startTime, endTime, powerW) {
    var container = document.getElementById('schedule-blocks-container');
    var row = document.createElement('div');
    row.className = 'schedule-block-row';
    row.innerHTML =
        '<input type="time" class="form-control block-start" value="' + startTime + '">' +
        '<span class="block-separator">&ndash;</span>' +
        '<input type="time" class="form-control block-end" value="' + endTime + '">' +
        '<input type="number" class="form-control block-power" value="' + powerW + '" min="0" placeholder="W">' +
        '<span class="block-unit">W</span>' +
        '<button type="button" class="btn btn-danger btn-xs btn-remove-block"><i class="fas fa-times"></i></button>';

    row.querySelector('.btn-remove-block').addEventListener('click', function() {
        row.remove();
        updateScheduleBlocksHidden();
    });

    row.querySelectorAll('input').forEach(function(input) {
        input.addEventListener('change', updateScheduleBlocksHidden);
    });

    container.appendChild(row);
    updateScheduleBlocksHidden();
}

function updateScheduleBlocksHidden() {
    var container = document.getElementById('schedule-blocks-container');
    var rows = container.querySelectorAll('.schedule-block-row');
    var blocks = [];
    rows.forEach(function(row) {
        blocks.push({
            start_time: row.querySelector('.block-start').value,
            end_time: row.querySelector('.block-end').value,
            power_w: parseFloat(row.querySelector('.block-power').value) || 0,
        });
    });
    document.getElementById('load_power_schedule_blocks').value = JSON.stringify(blocks);
}

function fetchEmhassConfig() {
    var pre = document.getElementById('emhass-config-preview');
    var btn = document.getElementById('btn-fetch-config');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Fetching...';

    fetch(baseUrl('/api/optimization/emhass/config'))
        .then(function(r) { return r.json(); })
        .then(function(data) {
            pre.textContent = JSON.stringify(data, null, 2);
            pre.style.display = 'block';
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-download"></i> Fetch Config';
        })
        .catch(function(err) {
            pre.textContent = 'Failed to fetch config: ' + err.message;
            pre.style.display = 'block';
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-download"></i> Fetch Config';
        });
}


