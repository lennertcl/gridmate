import io
import json
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from web.forms import DataJsonEditForm
from web.model.data.data_connector import DataConnector

settings_main_bp = Blueprint('settings_main', __name__)


@settings_main_bp.route('/settings/settings-json', methods=['GET', 'POST'])
def edit_settings_json():
    form = DataJsonEditForm()
    data_connector = DataConnector()

    if form.validate_on_submit():
        try:
            json_data = json.loads(form.json_content.data)
            data_connector.repository.save(json_data)

            flash('Settings file saved successfully!', 'success')
            return redirect(url_for('settings_main.edit_settings_json'))
        except json.JSONDecodeError as e:
            flash(f'Invalid JSON format: {str(e)}', 'error')
        except Exception as e:
            flash(f'Error saving settings.json: {str(e)}', 'error')

    if request.method == 'GET':
        try:
            data = data_connector.export()
            form.json_content.data = json.dumps(data, indent=2)
        except Exception as e:
            flash(f'Error loading settings.json: {str(e)}', 'error')

    return render_template('settings/settings-json.html', form=form)


@settings_main_bp.route('/settings/settings-json/download', methods=['GET'])
def download_settings_json():
    data_connector = DataConnector()
    try:
        data = data_connector.export()
        json_str = json.dumps(data, indent=2)

        file_obj = io.BytesIO(json_str.encode('utf-8'))

        return send_file(
            file_obj,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'settings-{datetime.now().strftime("%Y%m%d-%H%M%S")}.json',
        )
    except Exception as e:
        flash(f'Error downloading settings.json: {str(e)}', 'error')
        return redirect(url_for('settings_main.edit_settings_json'))
