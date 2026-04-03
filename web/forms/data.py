from flask_wtf import FlaskForm
from wtforms import SubmitField, TextAreaField
from wtforms.validators import DataRequired


class DataJsonEditForm(FlaskForm):
    json_content = TextAreaField(
        'Settings JSON', validators=[DataRequired(message='JSON content is required')], render_kw={'rows': 30}
    )
    submit = SubmitField('Save')
