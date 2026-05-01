from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, SelectField, StringField, SubmitField
from wtforms.validators import Length, NumberRange, Optional, Regexp


class EnergyFeedConfigForm(FlaskForm):
    total_consumption_high_tariff = StringField(
        'Total Energy Consumed - High Tariff', validators=[Optional(), Length(max=100)]
    )
    total_consumption_low_tariff = StringField(
        'Total Energy Consumed - Low Tariff', validators=[Optional(), Length(max=100)]
    )

    total_injection_high_tariff = StringField(
        'Total Energy Injected - High Tariff', validators=[Optional(), Length(max=100)]
    )
    total_injection_low_tariff = StringField(
        'Total Energy Injected - Low Tariff', validators=[Optional(), Length(max=100)]
    )

    actual_consumption = StringField('Current Power Consumption (Live)', validators=[Optional(), Length(max=100)])
    actual_injection = StringField('Current Power Injection (Live)', validators=[Optional(), Length(max=100)])

    usage_mode = SelectField(
        'Usage Calculation Mode',
        validators=[Optional()],
        choices=[
            ('auto', 'Automatic (consumption + production - injection)'),
            ('manual', 'Manual (specify sensors)'),
        ],
    )
    actual_usage = StringField('Current Power Usage (Live)', validators=[Optional(), Length(max=100)])
    total_usage_high_tariff = StringField('Total Energy Usage - High Tariff', validators=[Optional(), Length(max=100)])
    total_usage_low_tariff = StringField('Total Energy Usage - Low Tariff', validators=[Optional(), Length(max=100)])

    high_tariff_start = StringField(
        'High Tariff Start',
        validators=[Optional(), Regexp(r'^\d{2}:\d{2}$', message='Use HH:MM format')],
        default='07:00',
    )
    high_tariff_end = StringField(
        'High Tariff End',
        validators=[Optional(), Regexp(r'^\d{2}:\d{2}$', message='Use HH:MM format')],
        default='22:00',
    )
    exclude_weekend = BooleanField('Exclude weekend for high tariff', default=True)
    single_tariff = BooleanField('Treat as single tariff (no high/low split)', default=False)

    submit = SubmitField('Save Configuration')


class EnergyCostsForm(FlaskForm):
    period_type = SelectField(
        'Period Type',
        choices=[
            ('month', 'Monthly'),
            ('year', 'Yearly'),
        ],
        default='month',
    )

    month = SelectField(
        'Month',
        choices=[
            ('1', 'January'),
            ('2', 'February'),
            ('3', 'March'),
            ('4', 'April'),
            ('5', 'May'),
            ('6', 'June'),
            ('7', 'July'),
            ('8', 'August'),
            ('9', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December'),
        ],
    )

    year = IntegerField('Year', validators=[NumberRange(min=2000)])

    submit = SubmitField('View Period')
