from Frontend.forms import QuestionForm
import random
from typing import Any, cast
from Frontend.forms import RadioQuestionForm, CheckboxQuestionForm, ShortAnswerQuestionForm
from parser_engine import generateQuestion
# from flask import session
from dataclasses import dataclass
import supabase_client

questionIDs = supabase_client.FetchAllQuestions()

@dataclass
class QuestionContainer:
    prompt: str
    question: str
    correct: list[str]
    feedback: str
    answer: list[str]
    type: str

    def __init__(self, prompt: str, question: str, correct: list[str], feedback: str, answer: list[str], type: str):
        self.prompt = prompt
        self.question = question
        self.correct = correct
        self.feedback = feedback
        self.answer = answer
        self.type = type

    def __hash__(self):
        return hash(
            (self.prompt,
            self.question,
            self.feedback,
            self.type)
        )

def getRandomQuestion(tags: list[str] | None = None, types: list[str] | None = None, generateNew: bool = False) -> QuestionContainer | None:
    def getDbQuestion() -> dict[str, str] | None:
        print(f"Fetching question with tags: {tags} and types: {types}")
        options = supabase_client.FetchFilteredQuestions(tags=tags, questionTypes=types)
        print(options)
        if not options:
            return None
        questionID = random.choice(options)
        c = supabase_client.FetchQuestionById(questionID)

        if c is None:
            raise ValueError("Question not found.")
        return {"type": c["question_type"], "template": c["prompt_template"], "prompt": c["question_template"], "feedback": c["feedback_template"]}

    def shuffleAnswers(answers: list[tuple[str, str]]) -> Any:
        opt = answers
        random.shuffle(opt)
        return cast(Any, opt)

    q = getDbQuestion()
    if q is None:
        return None
    gq = generateQuestion(
        templateText=q["template"], promptText=q["prompt"], feedbackText=q["feedback"]
    )

    if q["type"] != "true_false":
        gq["answers"] = shuffleAnswers([*gq["incorrect"], *gq["answer"]])
    else:
        gq["answers"] = [*gq["incorrect"], *gq["answer"]]
    gq["type"] = q["type"]
    return QuestionContainer(
        prompt=gq["prompt"],
        question=gq["question"],
        correct=gq["answer"],
        feedback=gq["feedback"],
        answer=gq["answers"],
        type=gq["type"],
    )

def getQuestionForm(question: QuestionContainer) -> QuestionForm:

    match question.type:
        case "multiple_choice":
            form = RadioQuestionForm(
                prompt=question.prompt,
                question=question.question,
                correct=question.correct,
                feedback=question.feedback,
                answerChoices=question.answer,
            )
        case "multiple_select":
            form = CheckboxQuestionForm(
                prompt=question.prompt,
                question=question.question,
                correct=question.correct,
                feedback=question.feedback,
                answerChoices=question.answer,
            )
        case "true_false":
            form = RadioQuestionForm(
                prompt=question.prompt,
                question=question.question,
                correct=question.correct,
                feedback=question.feedback,
                answerChoices=question.answer,
            )
        case "short_answer":
            form = ShortAnswerQuestionForm(
                prompt=question.prompt,
                question=question.question,
                correct=question.correct,
                feedback=question.feedback,
            )
        case _:
            raise ValueError("Unknown question type.")

    return form
