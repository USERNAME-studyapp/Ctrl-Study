# Purpose:
# This file is the Flask entrypoint for the template-based question generator app

# Function:
# - Displays one template input textbox and one question-name textbox
# - Supports Preview, Save, Load, Delete, and New actions
# - Uses parser_engine.generateQuestion to build preview output
# - Persists named question templates in a local JSON file for editing later


from __future__ import annotations

from flask import Flask, render_template, session                               # Flask imports provide routing, form access, session state, and redirects

from Frontend import QuestionFetch
from Frontend.forms import RadioQuestionForm, SetupQuizForm, QuestionForm

from concurrent.futures import ThreadPoolExecutor

from typing import cast
from datetime import timedelta
from flask_session import Session

import supabase_client
import template_builder


# app is the Flask application instance
app = Flask(__name__)
app.secret_key = "template-question-builder-secret"

app.config["SESSION_FILE_DIR"] = "./flask_session_cache"

app.config["SESSION_PERMANENT"] = False  # Sessions expire when the browser is closed
app.config["SESSION_TYPE"] = "filesystem"  # Store session data in files
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=6)

Session(app)


# proper home page
@app.route("/", methods=["GET"])
@app.route("/index", methods=["GET"])
def home():
    return render_template("index.html", title="Ctrl-Study: Home")

@app.route("/template", methods=["GET", "POST"])
def templateIndex():
    return template_builder.templateIndex()


@app.route("/question", methods=["GET", "POST"])
def question():
    if "SingleQuestionState" not in session:
        session["SingleQuestionState"] = "NewQuestion"
    elif session["SingleQuestionState"] == "ToNewQuestion":
        session["SingleQuestionState"] = "NewQuestion"


    question: QuestionFetch.QuestionContainer
    if "randQuestion" not in session:
        question = QuestionFetch.getRandomQuestion()
        session["randQuestion"] = QuestionFetch.getRandomQuestion()

    question = session["randQuestion"]
    form = QuestionFetch.getQuestionForm(question)

    status: str = "Please answer the question."
    state = session["SingleQuestionState"]

    if form.validate_on_submit():
        match state:
            case "Answered":
                session.pop("randQuestion")
                session["SingleQuestionState"] = "ToNewQuestion"
                return redirect(url_for("question"))
            case "NewQuestion":
                session["SingleQuestionState"] = "Answered"
                if form.answer.data in form.correct:
                    status = "Correct"
                    print("correct")
                else:
                    status = "Incorrect"
                    print("incorrect")
                return render_template(
                    "individualQuestion.html", title="Question", form=form, status=status, showingAnswer=True
                )

    return render_template(
        "individualQuestion.html", title="Question", form=form, status=status, showingAnswer=False
    )


@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    tags = supabase_client.FetchAllTags()
    types = ["multiple_choice", "multiple_select", "short_answer", "true_false"]
    tags = [(tag["id"], tag["name"]) for tag in tags]
    form = SetupQuizForm(types=types, tags=tags)
    # if form.validate_on_submit():
    #     selected_tag_ids = form.tagSelection.data
    #     return redirect(url_for("quiz", selected_tag_ids=selected_tag_ids))
    return render_template("QuizSetup.html", tags=tags, form=form)

@app.route("/quizQuestions", methods=["GET", "POST"])
def manyQuestions():
    with ThreadPoolExecutor() as executor:
        questions = list(executor.map(lambda _: QuestionFetch.getRandomQuestion(generateNew=True), range(10)))

    forms = [QuestionFetch.getQuestionForm(q) for q in questions]
    return render_template("quizQuestions.html", questions=forms)


# Starts local development server when run directly
if __name__ == "__main__":
    app.run(debug=True)
