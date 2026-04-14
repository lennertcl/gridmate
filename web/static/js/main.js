/**
 * GridMate - Main JavaScript
 * Provides interactive functionality for the frontend
 */

// ============================================
// Initialization
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    initializeNavigation();
    initializeNavigationLoader();
    initializeForms();
    initializeTooltips();
    initializeResponsive();
});

// ============================================
// Navigation
// ============================================

function initializeNavigation() {
    const navToggle = document.getElementById('nav-toggle');
    const navMenu = document.querySelector('.nav-menu');
    const navLinks = document.querySelectorAll('.nav-sublink');

    if (navToggle) {
        navToggle.addEventListener('click', function() {
            navMenu.classList.toggle('active');
        });
    }

    document.querySelectorAll('.nav-group-toggle').forEach(function(toggle) {
        toggle.addEventListener('click', function(e) {
            if (window.innerWidth > 768) return;
            e.preventDefault();
            e.stopPropagation();
            var group = this.closest('.nav-group');
            document.querySelectorAll('.nav-group').forEach(function(g) {
                if (g !== group) g.classList.remove('open');
            });
            group.classList.toggle('open');
        });
    });

    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            if (navMenu) {
                navMenu.classList.remove('active');
            }
            document.querySelectorAll('.nav-group').forEach(function(g) {
                g.classList.remove('open');
            });
        });
    });

    document.addEventListener('click', function(e) {
        if (navMenu && navMenu.classList.contains('active') && !navMenu.contains(e.target) && e.target !== navToggle && !navToggle.contains(e.target)) {
            navMenu.classList.remove('active');
            document.querySelectorAll('.nav-group').forEach(function(g) {
                g.classList.remove('open');
            });
        }
    });
}

// ============================================
// Navigation Loading Overlay
// ============================================

function showNavigationLoader() {
    var overlay = document.getElementById('nav-loading-overlay');
    if (overlay) overlay.style.display = 'flex';
}

function initializeNavigationLoader() {
    document.addEventListener('click', function(e) {
        var link = e.target.closest('a[href]');
        if (!link) return;

        var href = link.getAttribute('href');
        if (!href || href.startsWith('#') || href.startsWith('javascript:') || link.target === '_blank') return;

        showNavigationLoader();
    });

    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', showNavigationLoader);
    });

    window.addEventListener('pageshow', function(e) {
        if (e.persisted) {
            var overlay = document.getElementById('nav-loading-overlay');
            if (overlay) overlay.style.display = 'none';
        }
    });
}

// ============================================
// Forms
// ============================================

function initializeForms() {
    // Handle form submissions
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', handleFormSubmit);
    });

    // Handle conditional inputs
    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', handleConditionalInput);
    });

    // Handle range sliders
    const sliders = document.querySelectorAll('input[type="range"]');
    sliders.forEach(slider => {
        slider.addEventListener('input', handleSliderInput);
    });
}

function handleFormSubmit(e) {
    // Show success message
    const form = e.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    
    if (submitBtn) {
        const originalText = submitBtn.textContent;
        submitBtn.textContent = '✓ Saved';
        submitBtn.disabled = true;
        
        setTimeout(() => {
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        }, 2000);
    }
}

function handleConditionalInput(e) {
    const checkbox = e.target;
    const parent = checkbox.closest('.checkbox-label');
    
    if (parent) {
        const conditionalInput = parent.nextElementSibling;
        if (conditionalInput && conditionalInput.classList.contains('conditional-input')) {
            conditionalInput.style.display = checkbox.checked ? 'block' : 'none';
        }
    }
}

function handleSliderInput(e) {
    const slider = e.target;
    const valueDisplay = document.getElementById(slider.id + 'Display');
    
    if (valueDisplay) {
        valueDisplay.textContent = slider.value + '%';
    }
}

// ============================================
// Tooltips
// ============================================

function initializeTooltips() {
    // Add tooltip functionality for elements with data-tooltip
    const tooltips = document.querySelectorAll('[data-tooltip]');
    
    tooltips.forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
    });
}

function showTooltip(e) {
    const tooltip = e.target.getAttribute('data-tooltip');
    if (!tooltip) return;

    const tooltipEl = document.createElement('div');
    tooltipEl.className = 'tooltip';
    tooltipEl.textContent = tooltip;
    tooltipEl.style.position = 'absolute';
    tooltipEl.style.backgroundColor = '#111827';
    tooltipEl.style.color = 'white';
    tooltipEl.style.padding = '0.5rem 0.75rem';
    tooltipEl.style.borderRadius = '0.375rem';
    tooltipEl.style.fontSize = '0.75rem';
    tooltipEl.style.zIndex = '1000';
    tooltipEl.style.whiteSpace = 'nowrap';

    document.body.appendChild(tooltipEl);

    const rect = e.target.getBoundingClientRect();
    tooltipEl.style.top = (rect.top - tooltipEl.offsetHeight - 10) + 'px';
    tooltipEl.style.left = (rect.left + rect.width / 2 - tooltipEl.offsetWidth / 2) + 'px';

    e.target._tooltip = tooltipEl;
}

function hideTooltip(e) {
    if (e.target._tooltip) {
        e.target._tooltip.remove();
        delete e.target._tooltip;
    }
}

// ============================================
// Responsive
// ============================================

function initializeResponsive() {
    const navMenu = document.querySelector('.nav-menu');
    
    // Close menu on window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768 && navMenu) {
            navMenu.classList.remove('active');
        }
    });
}

// ============================================
// Utility Functions
// ============================================

/**
 * Format energy value with appropriate unit
 */
function formatEnergy(value, precision = 2) {
    if (value >= 1000) {
        return (value / 1000).toFixed(precision) + ' MWh';
    }
    return value.toFixed(precision) + ' kWh';
}

/**
 * Format power value with appropriate unit
 */
function formatPower(value, precision = 2) {
    if (Math.abs(value) >= 1000) {
        return (value / 1000).toFixed(precision) + ' MW';
    }
    return value.toFixed(precision) + ' kW';
}

/**
 * Format currency
 */
function formatCurrency(value, currency = '€') {
    return currency + value.toFixed(2);
}

/**
 * Format time as HH:MM
 */
function formatTime(hours, minutes) {
    return String(hours).padStart(2, '0') + ':' + String(minutes).padStart(2, '0');
}

/**
 * Parse time string (HH:MM) to minutes
 */
function parseTime(timeStr) {
    const [hours, minutes] = timeStr.split(':').map(Number);
    return hours * 60 + minutes;
}

/**
 * Get random number in range
 */
function getRandomInRange(min, max) {
    return Math.random() * (max - min) + min;
}

/**
 * Show notification
 * @param {string} message - The notification message
 * @param {string} type - Notification type: 'info', 'success', 'error', 'warning', 'usage', 'production', 'consumption', 'injection'
 * @param {number} duration - Duration to show notification in milliseconds (0 = don't auto-close)
 */
function showNotification(message, type = 'info', duration = 0) {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <span>${message}</span>
        <button class="alert-close">×</button>
    `;

    document.querySelector('.content-wrapper').prepend(alert);

    const closeBtn = alert.querySelector('.alert-close');
    closeBtn.addEventListener('click', () => {
        alert.remove();
    });

    if (duration > 0) {
        setTimeout(() => {
            alert.remove();
        }, duration);
    }
}

function baseUrl(path) {
    return (window.GRIDMATE_BASE || '') + path;
}

async function fetchData(endpoint) {
    try {
        const response = await fetch(baseUrl(endpoint));
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return await response.json();
    } catch (error) {
        console.error('Fetch error:', error);
        showNotification('Error loading data', 'error');
        return null;
    }
}

/**
 * Post data to API endpoint
 */
async function postData(endpoint, data) {
    try {
        const response = await fetch(baseUrl(endpoint), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return await response.json();
    } catch (error) {
        console.error('Post error:', error);
        showNotification('Error saving data', 'error');
        return null;
    }
}

// ============================================
// UI Interactions
// ============================================

/**
 * Initialize tab navigation
 */
function initializeTabs(containerSelector) {
    const container = document.querySelector(containerSelector);
    if (!container) return;

    const tabs = container.querySelectorAll('[data-tab]');
    const tabContents = container.querySelectorAll('[data-tab-content]');

    tabs.forEach(tab => {
        tab.addEventListener('click', function(e) {
            e.preventDefault();
            
            const tabName = this.getAttribute('data-tab');
            
            // Remove active class from all tabs and contents
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(tc => tc.classList.remove('active'));
            
            // Add active class to clicked tab and corresponding content
            this.classList.add('active');
            const activeContent = container.querySelector(`[data-tab-content="${tabName}"]`);
            if (activeContent) {
                activeContent.classList.add('active');
            }
        });
    });
}

/**
 * Initialize collapsible sections
 */
function initializeCollapsibles() {
    const collapsibles = document.querySelectorAll('[data-collapsible]');
    
    collapsibles.forEach(collapsible => {
        const header = collapsible.querySelector('[data-collapsible-header]');
        const content = collapsible.querySelector('[data-collapsible-content]');
        
        if (header && content) {
            header.addEventListener('click', function() {
                const isOpen = content.style.display !== 'none';
                content.style.display = isOpen ? 'none' : 'block';
                collapsible.classList.toggle('open');
            });
        }
    });
}

/**
 * Initialize confirmation dialogs
 */
function confirmAction(message) {
    return confirm(message);
}

/**
 * Show modal dialog
 */
function showModal(title, content, onConfirm, onCancel) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-overlay"></div>
        <div class="modal-content">
            <div class="modal-header">
                <h3>${title}</h3>
                <button class="modal-close">&times;</button>
            </div>
            <div class="modal-body">
                ${content}
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" id="modal-cancel">Cancel</button>
                <button class="btn btn-primary" id="modal-confirm">Confirm</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    const closeBtn = modal.querySelector('.modal-close');
    const cancelBtn = modal.querySelector('#modal-cancel');
    const confirmBtn = modal.querySelector('#modal-confirm');

    function closeModal() {
        modal.remove();
    }

    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', () => {
        if (onCancel) onCancel();
        closeModal();
    });
    confirmBtn.addEventListener('click', () => {
        if (onConfirm) onConfirm();
        closeModal();
    });
}

// ============================================
// Data Validation
// ============================================

/**
 * Validate email
 */
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Validate time range
 */
function validateTimeRange(startTime, endTime) {
    const start = parseTime(startTime);
    const end = parseTime(endTime);
    return start < end;
}

/**
 * Validate power value
 */
function validatePowerValue(value, max) {
    return !isNaN(value) && value >= 0 && value <= max;
}

/**
 * Validate percentage
 */
function validatePercentage(value) {
    return !isNaN(value) && value >= 0 && value <= 100;
}

// ============================================
// Data JSON Editor Functions
// ============================================

function downloadJsonData() {
    const jsonContent = document.querySelector('textarea[name="json_content"]').value;
    
    // Validate JSON before download
    try {
        JSON.parse(jsonContent);
    } catch (e) {
        showNotification('Invalid JSON: ' + e.message, 'error');
        return;
    }
    
    // Create a blob and download
    const blob = new Blob([jsonContent], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'settings.json';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

// ============================================
// Export Functions (for use in other scripts)
// ============================================

window.GridMateEMS = {
    baseUrl,
    formatEnergy,
    formatPower,
    formatCurrency,
    formatTime,
    parseTime,
    showNotification,
    fetchData,
    postData,
    initializeTabs,
    initializeCollapsibles,
    confirmAction,
    showModal,
    validateEmail,
    validateTimeRange,
    validatePowerValue,
    validatePercentage,
    downloadJsonData
};
