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

def getRandomQuestion(tags: list[str] | None = None, generateNew: bool = False) -> QuestionContainer:
    def getDbQuestion() -> dict[str, str]:
        questionID = random.choice(questionIDs)
        c = supabase_client.FetchQuestionById(questionID["id"])
        if c is None:
            raise ValueError("Question not found.")
        return {"type": c["question_type"], "template": c["prompt_template"], "prompt": c["question_template"], "feedback": c["feedback_template"]}

    def randomizeAnswers(answers: list[tuple[str, str]]) -> Any:
        opt = answers
        random.shuffle(opt)
        return cast(Any, opt)

    q = getDbQuestion()
    gq = generateQuestion(
        templateText=q["template"], promptText=q["prompt"], feedbackText=q["feedback"]
    )

    gq["answers"] = randomizeAnswers( [*gq["incorrect"], *gq["answer"]] )
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
