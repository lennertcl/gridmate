from flask_wtf import FlaskForm
from wtforms import FloatField, StringField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class StaticPriceProviderForm(FlaskForm):
    name = StringField('Provider Name', validators=[DataRequired(), Length(min=1, max=100)])
    price_per_kwh = FloatField('Price (€/kWh)', validators=[DataRequired(), NumberRange(min=0.0)])


class SensorPriceProviderForm(FlaskForm):
    name = StringField('Provider Name', validators=[DataRequired(), Length(min=1, max=100)])
    price_sensor = StringField('Price Sensor', validators=[DataRequired(), Length(min=1, max=200)])


class NordpoolPriceProviderForm(FlaskForm):
    name = StringField('Provider Name', validators=[DataRequired(), Length(min=1, max=100)])
    area = StringField('Area Code', validators=[DataRequired(), Length(min=1, max=20)])


class ActionPriceProviderForm(FlaskForm):
    name = StringField('Provider Name', validators=[DataRequired(), Length(min=1, max=100)])
    action_domain = StringField('Action Domain', validators=[DataRequired(), Length(min=1, max=100)])
    action_service = StringField('Action Service', validators=[DataRequired(), Length(min=1, max=100)])
    action_data = StringField('Action Data (JSON)', validators=[Optional(), Length(max=500)])
    response_price_key = StringField('Response Price Key', validators=[DataRequired(), Length(min=1, max=100)])
