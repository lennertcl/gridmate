from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional


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
            ('notify', 'Notify — send HA notifications'),
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


class EnergyOptimizationForm(FlaskForm):
    optimization_frequency = SelectField(
        'Optimization Frequency',
        validators=[DataRequired()],
        choices=[
            ('15', 'Every 15 minutes'),
            ('30', 'Every 30 minutes'),
            ('60', 'Hourly'),
            ('240', 'Every 4 hours'),
            ('1440', 'Daily'),
        ],
    )
    optimization_horizon = SelectField(
        'Optimization Horizon',
        validators=[DataRequired()],
        choices=[('6', '6 hours ahead'), ('12', '12 hours ahead'), ('24', '24 hours ahead'), ('48', '48 hours ahead')],
    )
    goal = SelectField(
        'Optimization Goal',
        validators=[DataRequired()],
        choices=[
            ('cost', 'Minimize Cost'),
            ('independence', 'Maximize Independence'),
            ('carbon', 'Minimize Carbon'),
            ('balanced', 'Balanced'),
        ],
    )
    max_grid_draw = IntegerField(
        'Maximum Grid Draw (W)', validators=[DataRequired(), NumberRange(min=0, message='Value cannot be negative')]
    )
    max_grid_injection = IntegerField(
        'Maximum Grid Injection (W)',
        validators=[DataRequired(), NumberRange(min=0, message='Value cannot be negative')],
    )
    submit = SubmitField('Save Optimization Settings')
