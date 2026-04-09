from flask_wtf import FlaskForm
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import CppLexer
from wtforms import Field, RadioField, SubmitField, SelectMultipleField, TextAreaField, FieldList, FormField, validators, widgets
from wtforms.fields import IntegerField
from wtforms.validators import DataRequired
from typing import TypeVar, Generic

class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

class SetupQuizForm(FlaskForm):
    questionTypes = MultiCheckboxField("Question Types")
    tagSelection = MultiCheckboxField("Tag Selection")
    questionCount = IntegerField("Question Count", validators=[DataRequired(), validators.number_range(min=1)], default=10)

    submit = SubmitField("Submit")

    def __init__(self, types: list[str], tags: list[tuple[str, str]], *args, **kwargs):
        super(SetupQuizForm, self).__init__(*args, **kwargs)
        self.questionTypes.choices = [(t, t) for t in types]
        self.tagSelection.choices = [(id, name) for (id,name) in tags]

# QUESTION TYPES

# generic question form, from which all questions descend
# T is a Field
# this type should never be instantiated directly
T = TypeVar("T", bound=Field)
class QuestionForm(FlaskForm, Generic[T]):
    prompt: str
    question: str
    correct: list[str]
    feedback: str
    answer: T

    def format_html(self) -> str:
        formatter = HtmlFormatter(style="monokai", noclasses=True)
        highlighted = highlight(self.question, CppLexer(), formatter)
        return highlighted


class RussianNestingForm(FlaskForm):
    forms = FieldList(FormField(QuestionForm), min_entries=1)


class RadioQuestionForm(QuestionForm[RadioField]):
    prompt: str
    question: str
    correct: list[str]
    feedback: str
    answer: RadioField = RadioField("Answers", validators=[DataRequired()])
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
        self.answer.choices = [(item, item) for item in answerChoices]

class CheckboxQuestionForm(QuestionForm[MultiCheckboxField]):
    prompt: str
    question: str
    correct: list[str]
    feedback: str
    answer: MultiCheckboxField = MultiCheckboxField("Answers", validators=[DataRequired()])
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
        super(CheckboxQuestionForm, self).__init__(*args, **kwargs)
        self.prompt = prompt
        self.question = question
        self.correct = correct
        self.feedback = feedback
        self.answer.choices = [(item, item) for item in answerChoices]

class ShortAnswerQuestionForm(QuestionForm[TextAreaField]):
    prompt: str
    question: str
    correct: list[str]
    feedback: str
    answer: TextAreaField = TextAreaField("Answers", validators=[DataRequired()], default=None)
    submit = SubmitField("Submit")

    def __init__(
        self,
        prompt: str,
        question: str,
        correct: list[str],
        feedback: str,
        *args,
        **kwargs,
    ):
        super(ShortAnswerQuestionForm, self).__init__(*args, **kwargs)
        self.prompt = prompt
        self.question = question
        self.correct = correct
        self.feedback = feedback
