import { get_ha_connection } from './ha-connection.js';
import { subscribeEntities, callService } from 'https://esm.sh/home-assistant-js-websocket@9.6.0';

function getEntityDomain(entityId) {
    return entityId.split('.')[0];
}

function formatEntityState(entityId, state, attributes) {
    const domain = getEntityDomain(entityId);

    switch (domain) {
        case 'sensor':
        case 'input_number':
            return {
                display: state + (attributes.unit_of_measurement ? ' ' + attributes.unit_of_measurement : ''),
                stateClass: 'entity-sensor'
            };
        case 'switch':
        case 'input_boolean':
            return {
                display: state === 'on' ? 'On' : 'Off',
                stateClass: state === 'on' ? 'entity-on' : 'entity-off'
            };
        case 'binary_sensor':
            return {
                display: state === 'on' ? (attributes.device_class === 'door' ? 'Open' : 'Active')
                    : (attributes.device_class === 'door' ? 'Closed' : 'Inactive'),
                stateClass: state === 'on' ? 'entity-on' : 'entity-off'
            };
        case 'climate': {
            const temp = attributes.current_temperature;
            const action = attributes.hvac_action || state;
            return {
                display: temp ? temp + '°C · ' + action : action,
                stateClass: state === 'off' ? 'entity-off' : 'entity-on'
            };
        }
        case 'cover':
            return {
                display: state.charAt(0).toUpperCase() + state.slice(1),
                stateClass: state === 'open' ? 'entity-on' : 'entity-off'
            };
        default:
            return {
                display: state + (attributes.unit_of_measurement ? ' ' + attributes.unit_of_measurement : ''),
                stateClass: 'entity-sensor'
            };
    }
}

function updateEntityElements(entityId, state, attributes) {
    const elements = document.querySelectorAll(`[data-entity-id="${entityId}"]`);
    const isUnavailable = state === 'unavailable' || state === 'unknown';
    const formatted = formatEntityState(entityId, state, attributes);

    elements.forEach(el => {
        const valueEl = el.querySelector('.entity-state-value');
        const indicatorEl = el.querySelector('.entity-state-indicator');

        if (valueEl) {
            valueEl.textContent = isUnavailable ? 'Unavailable' : formatted.display;
            valueEl.className = 'entity-state-value' + (isUnavailable ? ' entity-unavailable' : ' ' + formatted.stateClass);
        }

        if (indicatorEl) {
            indicatorEl.className = 'entity-state-indicator'
                + (isUnavailable ? ' indicator-unavailable' : ' indicator-active');
        }

        el.classList.remove('entity-state-loading');
    });
}

function setAllEntitiesState(className, message) {
    document.querySelectorAll('.entity-state-value').forEach(el => {
        el.textContent = message;
        el.className = 'entity-state-value entity-unavailable';
    });
    document.querySelectorAll('.entity-state-indicator').forEach(el => {
        el.className = 'entity-state-indicator ' + className;
    });
    document.querySelectorAll('.entity-state').forEach(el => {
        el.classList.remove('entity-state-loading');
    });
}

function updateToggleElements(entityId, state) {
    document.querySelectorAll(`[data-entity-toggle="${entityId}"]`).forEach(el => {
        el.checked = state === 'on';
    });
}

async function initDeviceEntities() {
    const entityElements = document.querySelectorAll('[data-entity-id]');
    const toggleElements = document.querySelectorAll('[data-entity-toggle]');
    if (entityElements.length === 0 && toggleElements.length === 0) return;

    const trackedEntityIds = new Set();
    entityElements.forEach(el => trackedEntityIds.add(el.dataset.entityId));
    toggleElements.forEach(el => trackedEntityIds.add(el.dataset.entityToggle));

    document.querySelectorAll('.device-toggle-wrapper').forEach(wrapper => {
        wrapper.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    });

    try {
        const connection = await get_ha_connection();

        toggleElements.forEach(el => {
            el.addEventListener('change', async () => {
                const entityId = el.dataset.entityToggle;
                try {
                    await callService(connection, 'homeassistant', 'toggle', { entity_id: entityId });
                } catch {
                    el.checked = !el.checked;
                }
            });
        });

        subscribeEntities(connection, (entities) => {
            for (const entityId of trackedEntityIds) {
                if (entities[entityId]) {
                    updateEntityElements(
                        entityId,
                        entities[entityId].state,
                        entities[entityId].attributes
                    );
                    updateToggleElements(entityId, entities[entityId].state);
                }
            }
        });
    } catch (error) {
        console.error('Failed to connect to Home Assistant:', error);
        setAllEntitiesState('indicator-error', 'Connection failed');
    }
}

document.addEventListener('DOMContentLoaded', initDeviceEntities);
