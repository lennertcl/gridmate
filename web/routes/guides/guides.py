from flask import Blueprint, render_template

guides_bp = Blueprint('guides', __name__)


@guides_bp.route('/guides')
def getting_started():
    return render_template('guides/getting-started.html')


@guides_bp.route('/guides/energy-feed')
def energy_feed():
    return render_template('guides/energy-feed.html')


@guides_bp.route('/guides/solar-panels')
def solar_panels():
    return render_template('guides/solar-panels.html')


@guides_bp.route('/guides/devices')
def devices():
    return render_template('guides/devices.html')


@guides_bp.route('/guides/energy-contract')
def energy_contract():
    return render_template('guides/energy-contract.html')


@guides_bp.route('/guides/optimization')
def optimization():
    return render_template('guides/optimization.html')
