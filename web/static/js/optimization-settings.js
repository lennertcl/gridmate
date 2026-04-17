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
    initWeeklySchedule();
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

var WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
var wsScheduleData = {};
var wsActiveCell = null;

function initWeeklySchedule() {
    var hidden = document.getElementById('weekly_schedule_data');
    if (!hidden) return;

    try {
        wsScheduleData = JSON.parse(hidden.value) || {};
    } catch {
        wsScheduleData = {};
    }

    renderAllBadges();

    var cells = document.querySelectorAll('.ws-cell');
    cells.forEach(function(cell) {
        cell.addEventListener('click', function() {
            openCellEditor(cell);
        });
    });

    var closeBtn = document.getElementById('ws-editor-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeEditor);
    }

    var applyBtn = document.getElementById('ws-editor-apply');
    if (applyBtn) {
        applyBtn.addEventListener('click', saveCellFromEditor);
    }

    var copyAllBtn = document.getElementById('ws-editor-copy-all');
    if (copyAllBtn) {
        copyAllBtn.addEventListener('click', applyToAllDays);
    }

    var toggles = document.querySelectorAll('.ws-opt-toggle');
    toggles.forEach(function(toggle) {
        toggle.addEventListener('change', function() {
            var deviceId = toggle.getAttribute('data-device');
            toggleDeviceOpt(toggle, deviceId);
        });
    });
}

function toggleDeviceOpt(checkbox, deviceId) {
    fetch(baseUrl('/api/optimization/device/' + deviceId + '/toggle'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            var row = document.querySelector('.ws-device-row[data-device-id="' + deviceId + '"]');
            if (row) {
                if (data.opt_enabled) {
                    row.classList.remove('ws-device-disabled');
                } else {
                    row.classList.add('ws-device-disabled');
                }
                renderAllBadges();
            }
        } else {
            checkbox.checked = !checkbox.checked;
        }
    })
    .catch(function() {
        checkbox.checked = !checkbox.checked;
    });
}

function getEntry(day, deviceId) {
    var dayEntries = wsScheduleData[day] || [];
    for (var i = 0; i < dayEntries.length; i++) {
        if (dayEntries[i].device_id === deviceId) {
            return dayEntries[i];
        }
    }
    return null;
}

function setEntry(day, deviceId, entry) {
    if (!wsScheduleData[day]) {
        wsScheduleData[day] = [];
    }
    var dayEntries = wsScheduleData[day];
    for (var i = 0; i < dayEntries.length; i++) {
        if (dayEntries[i].device_id === deviceId) {
            dayEntries[i] = entry;
            return;
        }
    }
    dayEntries.push(entry);
}

function renderAllBadges() {
    var cells = document.querySelectorAll('.ws-cell');
    cells.forEach(function(cell) {
        var day = cell.getAttribute('data-day');
        var deviceId = cell.getAttribute('data-device');
        renderBadge(cell, day, deviceId);
    });
}

function renderBadge(cell, day, deviceId) {
    var entry = getEntry(day, deviceId);
    var badge = cell.querySelector('.ws-badge');
    if (!badge) return;

    var row = cell.closest('.ws-device-row');
    var isDeviceDisabled = row && row.classList.contains('ws-device-disabled');
    var numCycles = entry ? entry.num_cycles : 1;

    if (isDeviceDisabled || numCycles <= 0) {
        badge.textContent = numCycles;
        badge.className = 'ws-badge ws-badge-empty';
    } else {
        badge.textContent = numCycles;
        badge.className = 'ws-badge ws-badge-active';
        if (numCycles > 1 && entry && entry.hours_between_runs > 0) {
            badge.title = numCycles + ' cycles, ' + entry.hours_between_runs + 'h between runs';
        } else {
            badge.title = numCycles + ' cycle(s)';
        }
    }
}

function openCellEditor(cell) {
    var row = cell.closest('.ws-device-row');
    if (row && row.classList.contains('ws-device-disabled')) return;

    var day = cell.getAttribute('data-day');
    var deviceId = cell.getAttribute('data-device');
    var entry = getEntry(day, deviceId);

    if (wsActiveCell) {
        wsActiveCell.classList.remove('ws-cell-active');
    }
    cell.classList.add('ws-cell-active');
    wsActiveCell = cell;

    var deviceName = row ? row.querySelector('.ws-device-name').textContent.trim().split('\n')[0].trim() : deviceId;
    var dayLabel = day.charAt(0).toUpperCase() + day.slice(1);

    var titleEl = document.getElementById('ws-editor-title');
    titleEl.textContent = deviceName + ' — ' + dayLabel;

    var cyclesInput = document.getElementById('ws-editor-num-cycles');
    var gapInput = document.getElementById('ws-editor-gap');
    var startInput = document.getElementById('ws-editor-start');
    var endInput = document.getElementById('ws-editor-end');

    var defaults = (typeof DEVICE_DEFAULTS !== 'undefined' && DEVICE_DEFAULTS[deviceId]) || {};

    cyclesInput.value = entry ? entry.num_cycles : 1;
    gapInput.value = entry ? entry.hours_between_runs : 0;
    startInput.value = (entry && entry.earliest_start_time) ? entry.earliest_start_time : (defaults.earliest_start_time || '');
    endInput.value = (entry && entry.latest_end_time) ? entry.latest_end_time : (defaults.latest_end_time || '');

    var editor = document.getElementById('ws-editor');
    editor.style.display = 'block';
}

function closeEditor() {
    var editor = document.getElementById('ws-editor');
    editor.style.display = 'none';
    if (wsActiveCell) {
        wsActiveCell.classList.remove('ws-cell-active');
        wsActiveCell = null;
    }
}

function saveCellFromEditor() {
    if (!wsActiveCell) return;

    var day = wsActiveCell.getAttribute('data-day');
    var deviceId = wsActiveCell.getAttribute('data-device');

    setEntry(day, deviceId, buildEditorEntry(deviceId));
    renderBadge(wsActiveCell, day, deviceId);
    syncWeeklyScheduleHidden();
}

function buildEditorEntry(deviceId) {
    var numCycles = parseInt(document.getElementById('ws-editor-num-cycles').value) || 0;
    var gap = parseFloat(document.getElementById('ws-editor-gap').value) || 0;
    var startTime = document.getElementById('ws-editor-start').value || '';
    var endTime = document.getElementById('ws-editor-end').value || '';

    var defaults = (typeof DEVICE_DEFAULTS !== 'undefined' && DEVICE_DEFAULTS[deviceId]) || {};
    if (startTime === defaults.earliest_start_time) startTime = '';
    if (endTime === defaults.latest_end_time) endTime = '';

    return {
        device_id: deviceId,
        num_cycles: numCycles,
        hours_between_runs: gap,
        earliest_start_time: startTime,
        latest_end_time: endTime,
    };
}

function applyToAllDays() {
    if (!wsActiveCell) return;

    var deviceId = wsActiveCell.getAttribute('data-device');
    var entry = buildEditorEntry(deviceId);

    for (var i = 0; i < WEEKDAYS.length; i++) {
        setEntry(WEEKDAYS[i], deviceId, {
            device_id: deviceId,
            num_cycles: entry.num_cycles,
            hours_between_runs: entry.hours_between_runs,
            earliest_start_time: entry.earliest_start_time,
            latest_end_time: entry.latest_end_time,
        });
    }

    renderAllBadges();
    syncWeeklyScheduleHidden();
}

function syncWeeklyScheduleHidden() {
    var hidden = document.getElementById('weekly_schedule_data');
    if (hidden) {
        hidden.value = JSON.stringify(wsScheduleData);
    }
}