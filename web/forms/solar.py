from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import Length, Optional


class SolarConfigForm(FlaskForm):
    actual_production = StringField('Actual Power Production (kW)', validators=[Optional(), Length(max=100)])
    energy_production_today = StringField('Energy Produced Today (kWh)', validators=[Optional(), Length(max=100)])
    energy_production_lifetime = StringField(
        'Lifetime Energy Production (kWh)', validators=[Optional(), Length(max=100)]
    )

    estimated_actual_production = StringField(
        'Estimated Actual Production (kW)', validators=[Optional(), Length(max=100)]
    )
    estimated_energy_production_remaining_today = StringField(
        'Estimated Remaining Today (kWh)', validators=[Optional(), Length(max=100)]
    )
    estimated_energy_production_today = StringField(
        'Estimated Production Today (kWh)', validators=[Optional(), Length(max=100)]
    )
    estimated_energy_production_hour = StringField(
        'Estimated Production This Hour (kWh)', validators=[Optional(), Length(max=100)]
    )
    estimated_actual_production_offset_day = StringField(
        'Estimated Production +24h (kW)', validators=[Optional(), Length(max=100)]
    )
    estimated_energy_production_offset_day = StringField(
        'Estimated Energy +24h (kWh)', validators=[Optional(), Length(max=100)]
    )
    estimated_energy_production_offset_hour = StringField(
        'Estimated Energy Next Hour (kWh)', validators=[Optional(), Length(max=100)]
    )

    submit = SubmitField('Save Solar Configuration')
