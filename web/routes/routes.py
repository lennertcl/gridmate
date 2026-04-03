from web.routes.dashboards.dashboard import dashboard_bp
from web.routes.dashboards.optimization import dashboard_optimization_bp
from web.routes.guides.guides import guides_bp
from web.routes.main.home import main_bp
from web.routes.settings.device import settings_device_bp
from web.routes.settings.energy import settings_energy_bp
from web.routes.settings.main import settings_main_bp
from web.routes.settings.optimization import settings_optimization_bp


def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(dashboard_optimization_bp)
    app.register_blueprint(guides_bp)
    app.register_blueprint(settings_device_bp)
    app.register_blueprint(settings_energy_bp)
    app.register_blueprint(settings_main_bp)
    app.register_blueprint(settings_optimization_bp)
