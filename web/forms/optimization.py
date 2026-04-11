from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, SelectField, StringField, SubmitField
from wtforms.validators import NumberRange, Optional


class OptimizationSettingsForm(FlaskForm):
    emhass_url = StringField('EMHASS URL', default='http://localhost:5000')
    enabled = BooleanField('Enable Optimization')
    dayahead_schedule_time = StringField('Day-Ahead Run Time', default='05:30')

    max_grid_import_w = IntegerField(
        'Max Grid Import (W)',
        default=9000,
        validators=[Optional(), NumberRange(min=0)],
    )
    max_grid_export_w = IntegerField(
        'Max Grid Export (W)',
        default=9000,
        validators=[Optional(), NumberRange(min=0)],
    )

    actuation_mode = SelectField(
        'Actuation Mode',
        choices=[
            ('manual', 'Manual — show schedule only'),
            ('automatic', 'Automatic — control devices directly'),
        ],
    )

    load_power_source_type = SelectField(
        'Load Power Source',
        choices=[
            ('sensor', 'Home Assistant Sensor'),
            ('schedule', 'Fixed Schedule'),
        ],
    )
    load_power_sensor_entity = StringField('Load Power Sensor Entity')

    submit = SubmitField('Save Settings')
