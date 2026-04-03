from flask import Blueprint, redirect, url_for

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@main_bp.route('/home')
def home():
    return redirect(url_for('dashboard.live'))
