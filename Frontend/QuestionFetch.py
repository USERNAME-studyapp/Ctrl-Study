from Frontend.forms import QuestionForm
import random
from typing import Any, cast
from Frontend.forms import RadioQuestionForm
from parser_engine import generateQuestion
from flask import session

import supabase_client

questionIDs = supabase_client.FetchAllQuestions()

def getRandomQuestion(tags: list[str] | None = None) -> QuestionForm:
    def getDbQuestion() -> dict[str, str]:
        questionID = random.choice(questionIDs)
        c = supabase_client.FetchQuestionById(questionID["id"])
        if c is None:
            raise ValueError("Question not found.")
        return {"template": c["prompt_template"], "prompt": c["question_template"], "feedback": c["feedback_template"]}

    def randomizeAnswers(answers: list[tuple[str, str]]) -> Any:
        opt = answers
        random.shuffle(opt)
        return cast(Any, opt)

    if "randQuestion" not in session:
        q = getDbQuestion()
        print("Chosen question:\n")
        print(q)
        session["randQuestion"] = generateQuestion(
            templateText=q["template"], promptText=q["prompt"], feedbackText=q["feedback"]
        )
        gq = session["randQuestion"]
        session["randQuestion"]["answers"] = randomizeAnswers(
            [*gq["incorrect"], *gq["answer"]]
        )

    generatedQuestion = session["randQuestion"]

    form = RadioQuestionForm(
        prompt=generatedQuestion["prompt"],
        question=generatedQuestion["question"],
        correct=generatedQuestion["answer"],
        feedback=generatedQuestion["feedback"],
        answerChoices=generatedQuestion["answers"],
    )
    return form
