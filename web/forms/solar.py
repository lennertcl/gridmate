from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import Length, Optional


class SolarConfigForm(FlaskForm):
    actual_production = StringField('Actual Power Production (kW)', validators=[Optional(), Length(max=100)])
    energy_production_today = StringField('Energy Produced Today (kWh)', validators=[Optional(), Length(max=100)])
    energy_production_lifetime = StringField(
        'Lifetime Energy Production (kWh)', validators=[Optional(), Length(max=100)]
    )

    forecast_provider_type = SelectField(
        'Solar Forecast Provider',
        choices=[
            ('', 'None'),
            ('forecast_solar', 'Forecast.Solar'),
            ('solcast', 'Solcast'),
            ('naive', 'Naive (yesterday as forecast)'),
        ],
        validators=[Optional()],
    )

    forecast_solar_sensor = StringField('Forecast.Solar Offset Sensor', validators=[Optional(), Length(max=100)])
    solcast_forecast_entity = StringField('Solcast Forecast Entity', validators=[Optional(), Length(max=100)])
    naive_production_sensor = StringField('Production Sensor (for Naive)', validators=[Optional(), Length(max=100)])

    submit = SubmitField('Save Solar Configuration')
