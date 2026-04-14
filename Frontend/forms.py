from flask_wtf import FlaskForm
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import CppLexer, PythonLexer, MarkdownLexer
from wtforms import Field, RadioField, SubmitField, SelectMultipleField, TextAreaField, FieldList, FormField, validators, widgets
from wtforms.fields import IntegerField
from wtforms.validators import DataRequired, Optional, InputRequired
from typing import TypeVar, Generic

class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

class SetupQuizForm(FlaskForm):
    questionTypes = MultiCheckboxField("Question Types")
    tagSelection = MultiCheckboxField("Tag Selection")
    languageSelection = MultiCheckboxField("Programming Language")
    questionCount = IntegerField("Question Count", validators=[DataRequired(), validators.number_range(min=1)], default=10)
    seed = IntegerField("Seed", validators=[Optional()])

    submit = SubmitField("Submit")

    def __init__(self, types: list[str], tags: list[tuple[str, str]], languages: list[str], *args, **kwargs):
        super(SetupQuizForm, self).__init__(*args, **kwargs)
        self.questionTypes.choices = [(t, t) for t in types]
        self.tagSelection.choices = [(id, name) for (id,name) in tags]
        self.languageSelection.choices = [(l, l) for l in languages]

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
    language: str
    answer: T

    def getCorrect(self) -> list[str]:
        return self.correct

    def format_html(self) -> str:
        match self.language:
            case "C++":
                lexer = CppLexer()
            case "Python":
                lexer = PythonLexer()
            case _:
                lexer = MarkdownLexer()
        formatter = HtmlFormatter(style="monokai", noclasses=True)
        highlighted = highlight(self.question, lexer, formatter)
        return highlighted


class RussianNestingForm(FlaskForm):
    forms = FieldList(FormField(QuestionForm), min_entries=1)


class RadioQuestionForm(QuestionForm[RadioField]):
    prompt: str
    question: str
    correct: list[str]
    feedback: str
    answer: RadioField = RadioField("Answers", validators=[InputRequired()])
    submit = SubmitField("Submit")

    def getCorrect(self) -> list[str]:
        return [self._choice_map[correct] for correct in self.correct]

    def __init__(
        self,
        prompt: str,
        question: str,
        correct: list[str],
        feedback: str,
        language: str,
        answerChoices: list[str],
        *args,
        **kwargs,
    ):
        super(RadioQuestionForm, self).__init__(*args, **kwargs)
        self.prompt = prompt
        self.question = question
        self.feedback = feedback
        self.language = language

        self._choice_map = {
            f"choice_{i}": text for i, text in enumerate(answerChoices)
        }
        self.answer.choices = list(self._choice_map.items())
        self.correct = [
            key for key, text in self._choice_map.items() if text in correct
        ]

class CheckboxQuestionForm(QuestionForm[MultiCheckboxField]):
    prompt: str
    question: str
    correct: list[str]
    feedback: str
    answer: MultiCheckboxField = MultiCheckboxField("Answers", validators=[InputRequired()])
    submit = SubmitField("Submit")

    def getCorrect(self) -> list[str]:
        return [self._choice_map[correct] for correct in self.correct]

    def __init__(
        self,
        prompt: str,
        question: str,
        correct: list[str],
        feedback: str,
        language: str,
        answerChoices: list[str],
        *args,
        **kwargs,
    ):
        super(CheckboxQuestionForm, self).__init__(*args, **kwargs)
        self.prompt = prompt
        self.question = question
        self.correct = correct
        self.feedback = feedback
        self.language = language
        self._choice_map = {
            f"choice_{i}": text for i, text in enumerate(answerChoices)
        }
        self.answer.choices = list(self._choice_map.items())
        self.correct = [
            key for key, text in self._choice_map.items() if text in correct
        ]

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
        language: str,
        feedback: str,
        *args,
        **kwargs,
    ):
        super(ShortAnswerQuestionForm, self).__init__(*args, **kwargs)
        self.prompt = prompt
        self.question = question
        self.correct = correct
        self.feedback = feedback
        self.language = language
