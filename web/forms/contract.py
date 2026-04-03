from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, SelectField, StringField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class ConstantComponentForm(FlaskForm):
    name = StringField('Component Name', validators=[DataRequired(), Length(min=1, max=100)])
    multiplier = FloatField('Multiplier', validators=[DataRequired(), NumberRange(min=0.0)])
    price_constant = FloatField('Price (€/month or year)', validators=[DataRequired(), NumberRange(min=0.0)])
    period = SelectField('Period', choices=[('month', 'Monthly'), ('year', 'Yearly')], default='month')


class FixedComponentForm(FlaskForm):
    name = StringField('Component Name', validators=[DataRequired(), Length(min=1, max=100)])
    multiplier = FloatField('Multiplier', validators=[DataRequired(), NumberRange(min=0.0)])
    fixed_price = FloatField('Price (€/kWh)', validators=[DataRequired(), NumberRange(min=0.0)])
    is_injection_reward = BooleanField('Is Injection Reward', default=False)
    energy_sensor = StringField('Energy Sensor (default: total consumption)', validators=[Optional(), Length(max=200)])


class VariableComponentForm(FlaskForm):
    name = StringField('Component Name', validators=[DataRequired(), Length(min=1, max=100)])
    multiplier = FloatField('Multiplier', validators=[DataRequired(), NumberRange(min=0.0)])
    variable_price_sensor = StringField('Price Sensor', validators=[DataRequired(), Length(min=1, max=200)])
    variable_price_multiplier = FloatField('Price Multiplier', validators=[DataRequired()], default=1.0)
    variable_price_constant = FloatField('Price Constant (€/kWh)', validators=[DataRequired()], default=0.0)
    is_injection_reward = BooleanField('Is Injection Reward', default=False)
    energy_sensor = StringField('Energy Sensor (default: total consumption)', validators=[Optional(), Length(max=200)])


class CapacityComponentForm(FlaskForm):
    name = StringField('Component Name', validators=[DataRequired(), Length(min=1, max=100)])
    multiplier = FloatField('Multiplier', validators=[DataRequired(), NumberRange(min=0.0)])
    capacity_price_multiplier = FloatField('Capacity Price (€/kW)', validators=[DataRequired(), NumberRange(min=0.0)])
    period = SelectField('Period', choices=[('month', 'Monthly'), ('year', 'Yearly')], default='month')


class PercentageComponentForm(FlaskForm):
    name = StringField('Component Name', validators=[DataRequired(), Length(min=1, max=100)])
    multiplier = FloatField('Multiplier', validators=[DataRequired(), NumberRange(min=0.0)])
    percentage = FloatField('Percentage (%)', validators=[DataRequired(), NumberRange(min=0.0)])
