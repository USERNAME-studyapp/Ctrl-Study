from flask_wtf import FlaskForm
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import CppLexer
from wtforms import RadioField, SubmitField
from wtforms.validators import DataRequired

class QuestionForm(FlaskForm):
    prompt: str
    question: str
    feedback: str

class RadioQuestionForm(QuestionForm):
    prompt: str
    question: str
    correct: str
    feedback: str
    choice = RadioField("Answers", validators=[DataRequired()])
    submit = SubmitField("Submit")

    def __init__(
        self,
        prompt: str,
        question: str,
        correct: str,
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
