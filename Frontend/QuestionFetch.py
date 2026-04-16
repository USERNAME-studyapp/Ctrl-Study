from Frontend.forms import QuestionForm
import random
from random import choice
from typing import Any, cast
from Frontend.forms import RadioQuestionForm, CheckboxQuestionForm, ShortAnswerQuestionForm
from parser_engine import generateQuestion
# from flask import session
from dataclasses import dataclass
import supabase_client
import sys

questionIDs = supabase_client.FetchAllQuestions()

def makeSeed() -> int:
    aSeed = random.randrange(sys.maxsize)
    return aSeed


@dataclass
class QuestionContainer:
    prompt: str
    question: str
    correct: list[str]
    feedback: str
    answer: list[str]
    type: str
    language: str
    title: str

    def __init__(self, prompt: str, question: str, correct: list[str], feedback: str, answer: list[str], type: str, language: str, title: str):
        self.prompt = prompt
        self.question = question
        self.correct = correct
        self.feedback = feedback
        self.answer = answer
        self.type = type
        self.language = language
        self.title = title

    def __hash__(self):
        return hash(
            (self.prompt,
            self.question,
            self.feedback,
            self.type)
        )

def getRandomQuestions(seed: int, count: int = 1, tags: list[str] = [], types: list[str] = [], languages: list[str] = []) -> list[QuestionContainer] | None:
    def getDbQuestions() -> list[dict[str, str]] | None:
        print(f"Fetching question with tags: {tags} and types: {types}")
        options = supabase_client.FetchFilteredQuestions(tags=tags, questionTypes=types, languages=languages)
        print(f"Got question ids: {options}")
        if not options:
            return None

        questions = []

        random.seed(seed)
        for _ in range(count):
            questionID = choice(options)
            c = supabase_client.FetchQuestionById(questionID)
            if c is None:
                raise ValueError("Question not found.")
            questions.append({
                    "type": c["question_type"],
                    "template": c["prompt_template"],
                    "prompt": c["question_template"],
                    "feedback": c["feedback_template"],
                    "language": c["language"],
                    "title": c["title"],
                })

        return questions

    def shuffleAnswers(answers: list[tuple[str, str]], seed: int) -> Any:
        opt = answers
        random.seed(seed)
        random.shuffle(opt)
        return cast(Any, opt)

    q = getDbQuestions()
    if q is None:
        return None

    questions = []

    random.seed(seed)
    print("individual question seeds as follows:")
    for qu in q:
        randNum = random.randrange(sys.maxsize)
        print(randNum)
        gq = generateQuestion(
            templateText=qu["template"], promptText=qu["prompt"], feedbackText=qu["feedback"], seed=randNum
        )
        gq["answers"] = shuffleAnswers([*gq["incorrect"], *gq["answer"]], seed=randNum)
        gq["type"] = qu["type"]
        questions.append(QuestionContainer(
            prompt=gq["prompt"],
            question=gq["question"],
            correct=gq["answer"],
            feedback=gq["feedback"],
            answer=gq["answers"],
            type=gq["type"],
            language=qu["language"],
            title=qu["title"]
        ))

    return questions

def getQuestionForm(question: QuestionContainer, label: str = "Answers") -> QuestionForm:

    match question.type:
        case "multiple_choice":
            form = RadioQuestionForm(
                prompt=question.prompt,
                question=question.question,
                correct=question.correct,
                feedback=question.feedback,
                answerChoices=question.answer,
                language=question.language,
                prefix = label
            )
        case "multiple_select":
            form = CheckboxQuestionForm(
                prompt=question.prompt,
                question=question.question,
                correct=question.correct,
                feedback=question.feedback,
                answerChoices=question.answer,
                language=question.language,
                prefix=label
            )
        case "true_false":
            form = RadioQuestionForm(
                prompt=question.prompt,
                question=question.question,
                correct=question.correct,
                feedback=question.feedback,
                answerChoices=question.answer,
                language=question.language,
                prefix=label
            )
        case "short_answer":
            form = ShortAnswerQuestionForm(
                prompt=question.prompt,
                question=question.question,
                correct=question.correct,
                feedback=question.feedback,
                language=question.language,
                prefix=label
            )
        case _:
            raise ValueError("Unknown question type.")

    return form
