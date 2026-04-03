import {
    createLongLivedTokenAuth,
    createConnection,
} from 'https://esm.sh/home-assistant-js-websocket@9.6.0';

let cached_connection = null;
let connection_promise = null;

function resolve_hass_url(config_url) {
    if (window.GRIDMATE_BASE) {
        return window.location.origin;
    }
    return config_url;
}

async function create_ha_connection() {
    const response = await fetch(baseUrl('/api/ha/config'));
    if (!response.ok) {
        throw new Error('Failed to fetch Home Assistant configuration');
    }
    const config = await response.json();

    if (!config.access_token) {
        throw new Error('No Home Assistant access token configured');
    }

    const hass_url = resolve_hass_url(config.hass_url);
    const auth = createLongLivedTokenAuth(hass_url, config.access_token);
    return await createConnection({ auth });
}

async function get_ha_connection() {
    if (cached_connection) return cached_connection;

    if (!connection_promise) {
        connection_promise = create_ha_connection().then(conn => {
            cached_connection = conn;
            return conn;
        }).catch(err => {
            connection_promise = null;
            throw err;
        });
    }

    return connection_promise;
}

export { get_ha_connection };
