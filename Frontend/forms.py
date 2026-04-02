from flask.app import Flask
from flask_wtf import FlaskForm
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import CppLexer
from wtforms import RadioField, SubmitField, SelectMultipleField, widgets
from wtforms.validators import DataRequired

class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

class SetupQuizForm(FlaskForm):
    tagSelection = MultiCheckboxField("Tag Selection")
    submit = SubmitField("Submit")

    def __init__(self, tags: list[tuple[str, str]], *args, **kwargs):
        super(SetupQuizForm, self).__init__(*args, **kwargs)
        self.tagSelection.choices = [(id, name) for (id,name) in tags]

class QuestionForm(FlaskForm):
    prompt: str
    question: str
    feedback: str

class RadioQuestionForm(QuestionForm):
    prompt: str
    question: str
    correct: list[str]
    feedback: str
    choice = RadioField("Answers", validators=[DataRequired()])
    submit = SubmitField("Submit")

    def __init__(
        self,
        prompt: str,
        question: str,
        correct: list[str],
        feedback: str,
        answerChoices: list[str],
        *args,
        **kwargs,
    ):
        super(RadioQuestionForm, self).__init__(*args, **kwargs)
        self.prompt = prompt
        self.question = question
        self.correct = correct
        self.feedback = feedback
        self.choice.choices = [(item, item) for item in answerChoices]

    def format_html(self) -> str:
        formatter = HtmlFormatter(style="monokai", noclasses=True)
        highlighted = highlight(self.question, CppLexer(), formatter)
        return highlighted
