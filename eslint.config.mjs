import js from '@eslint/js';

const browserGlobals = {
    document: 'readonly',
    window: 'readonly',
    console: 'readonly',
    fetch: 'readonly',
    setTimeout: 'readonly',
    setInterval: 'readonly',
    clearInterval: 'readonly',
    clearTimeout: 'readonly',
    alert: 'readonly',
    confirm: 'readonly',
    Chart: 'readonly',
    URLSearchParams: 'readonly',
    location: 'readonly',
    MutationObserver: 'readonly',
    HTMLElement: 'readonly',
    Event: 'readonly',
    AbortController: 'readonly',
    Headers: 'readonly',
    Request: 'readonly',
    Response: 'readonly',
    FormData: 'readonly',
    Blob: 'readonly',
};

const sharedRules = {
    'quotes': ['warn', 'single', { avoidEscape: true }],
    'semi': ['warn', 'always'],
    'no-unused-vars': ['warn', { vars: 'local', args: 'after-used', argsIgnorePattern: '^_' }],
    'no-undef': 'error',
};

const moduleRules = {
    ...sharedRules,
    'no-unused-vars': ['warn', { args: 'after-used', argsIgnorePattern: '^_' }],
};

const moduleFiles = [
    'web/static/js/ha-connection.js',
    'web/static/js/device-entities.js',
    'web/static/js/live-dashboard.js',
    'web/static/js/solar-dashboard.js',
    'web/static/js/home-battery-dashboard.js',
];

export default [
    js.configs.recommended,
    {
        files: ['web/static/js/**/*.js'],
        ignores: [...moduleFiles, 'web/static/js/main.js'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'script',
            globals: {
                ...browserGlobals,
                baseUrl: 'readonly',
                OPTIMIZATION_RESULT: 'readonly',
                DEVICE_NAMES: 'readonly',
            }
        },
        rules: sharedRules,
    },
    {
        files: ['web/static/js/main.js'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'script',
            globals: browserGlobals,
        },
        rules: sharedRules,
    },
    {
        files: moduleFiles,
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'module',
            globals: {
                ...browserGlobals,
                baseUrl: 'readonly',
                OPTIMIZATION_RESULT: 'readonly',
                DEVICE_NAMES: 'readonly',
            }
        },
        rules: moduleRules,
    },
    {
        files: ['web/static/js/live-dashboard.js'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'module',
            globals: {
                ...browserGlobals,
                baseUrl: 'readonly',
                create_energy_chart: 'readonly',
                create_consumption_chart: 'readonly',
                clear_chart: 'readonly',
                process_history_for_chart: 'readonly',
                update_chart_realtime: 'readonly',
            }
        },
    },
    {
        files: ['web/static/js/solar-dashboard.js'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'module',
            globals: {
                ...browserGlobals,
                baseUrl: 'readonly',
                solar_production_chart: 'writable',
                create_solar_production_chart: 'readonly',
                update_solar_chart_range: 'readonly',
                update_solar_production_chart_realtime: 'readonly',
                clear_solar_charts: 'readonly',
            }
        },
    },
];
