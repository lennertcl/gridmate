"""
GridMate - Flask Application
Main entry point for the web interface
"""

import logging
import os
import sys

from dotenv import load_dotenv
from flask import Flask, render_template

load_dotenv()

is_local_dev = os.environ.get('LOCAL_DEV', '').lower() == 'true'

format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
if is_local_dev:
    logging.basicConfig(level=logging.DEBUG, format=format)
else:
    logging.basicConfig(level=logging.INFO, format=format)

logger = logging.getLogger(__name__)

app_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_root)


def get_secret_key():
    if is_local_dev:
        return os.environ.get('SECRET_KEY', 'dev-secret-key')
    key_path = '/data/.secret_key'
    try:
        with open(key_path, 'rb') as f:
            return f.read()
    except FileNotFoundError:
        key = os.urandom(32)
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        with open(key_path, 'wb') as f:
            f.write(key)
        return key


class IngressMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        ingress_path = environ.get('HTTP_X_INGRESS_PATH', '')
        if ingress_path:
            environ['SCRIPT_NAME'] = ingress_path
        return self.app(environ, start_response)


app = Flask(
    __name__,
    template_folder=os.path.join(app_root, 'web/templates'),
    static_folder=os.path.join(app_root, 'web/static'),
)

app.config['SECRET_KEY'] = get_secret_key()
app.config['JSON_SORT_KEYS'] = False

app.wsgi_app = IngressMiddleware(app.wsgi_app)

# Import and register all blueprints
try:
    from web.routes.routes import register_blueprints

    register_blueprints(app)
    logger.info('Successfully registered all blueprints')
except Exception as e:
    logger.error(f'Failed to register blueprints: {e}', exc_info=True)
    raise


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    return render_template('errors/500.html'), 500


@app.context_processor
def inject_config():
    """Inject configuration into template context"""
    from web.model.data.data_connector import DataConnector, DeviceManager

    dm = DeviceManager(DataConnector())
    home_batteries = dm.get_devices_by_type('home_battery')
    if len(home_batteries) == 1:
        battery_nav_url = f'/dashboard/device/{home_batteries[0].device_id}'
    else:
        battery_nav_url = '/dashboard/devices?type=home_battery'
    return {
        'app_name': 'GridMate',
        'app_version': '1.0.0',
        'battery_nav_url': battery_nav_url,
    }


if __name__ == '__main__':
    logger.info('Starting GridMate application on 0.0.0.0:8000')
    app.run(host='0.0.0.0', port=8000, debug=False)
