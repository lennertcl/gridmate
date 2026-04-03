from flask_wtf import FlaskForm
from wtforms import (
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, Length


class AddDeviceForm(FlaskForm):
    device_name = StringField(
        'Device Name', validators=[DataRequired(message='Device name is required'), Length(min=1, max=100)]
    )
    primary_type = SelectField('Primary Type', validators=[DataRequired()], choices=[])
    submit = SubmitField('Save Device')


class EditDeviceForm(FlaskForm):
    device_name = StringField(
        'Device Name', validators=[DataRequired(message='Device name is required'), Length(min=1, max=100)]
    )
    primary_type = SelectField('Primary Type', validators=[DataRequired()], choices=[])
    submit = SubmitField('Update Device')
