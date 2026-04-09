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

def getRandomQuestions(count: int = 1, tags: list[str] = [], types: list[str] = []) -> list[QuestionContainer] | None:
    def getDbQuestions() -> list[dict[str, str]] | None:
        print(f"Fetching question with tags: {tags} and types: {types}")
        options = supabase_client.FetchFilteredQuestions(tags=tags, questionTypes=types)
        print(options)
        if not options:
            return None

        questions = []

        for _ in range(count):
            questionID = random.choice(options)
            c = supabase_client.FetchQuestionById(questionID)
            if c is None:
                raise ValueError("Question not found.")
            questions.append({"type": c["question_type"], "template": c["prompt_template"], "prompt": c["question_template"], "feedback": c["feedback_template"]})


        return questions

    def shuffleAnswers(answers: list[tuple[str, str]]) -> Any:
        opt = answers
        random.shuffle(opt)
        return cast(Any, opt)

    q = getDbQuestions()
    if q is None:
        return None

    questions = []

    for qu in q:
        gq = generateQuestion(
            templateText=qu["template"], promptText=qu["prompt"], feedbackText=qu["feedback"]
        )
        gq["answers"] = shuffleAnswers([*gq["incorrect"], *gq["answer"]])
        gq["type"] = qu["type"]
        questions.append(QuestionContainer(
            prompt=gq["prompt"],
            question=gq["question"],
            correct=gq["answer"],
            feedback=gq["feedback"],
            answer=gq["answers"],
            type=gq["type"],
        ))

    return questions

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
