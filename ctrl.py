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
from Frontend.forms import SetupQuizForm

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from flask_session import Session

from flask import redirect, url_for

import supabase_client
import template_builder

import shutil
cache_path = "./flask_session_cache"
try:
    shutil.rmtree(cache_path)
except FileNotFoundError:
    pass

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
    if "quizQuestions" not in session:
        raise RuntimeError("quizQuestions not in session")

    if "progress" not in session:
        session["progress"] = 0

    if session["progress"] >= len(session["quizQuestions"]):
        raise IndexError("progress out of range")


    question = session["quizQuestions"][session["progress"]]
    form = QuestionFetch.getQuestionForm(question)

    status: str = "Please answer the question."
    state = session["SingleQuestionState"]

    if form.validate_on_submit():
        match state:
            case "Answered":
                session["SingleQuestionState"] = "ToNewQuestion"
                session["progress"] += 1
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
    ts = [(tag["id"], tag["name"]) for tag in tags]
    form = SetupQuizForm(types=types, tags=ts)
    if "questions" in session:
        session.pop("questions")
    if "quizQuestionTags" in session:
        session.pop("quizQuestionTags")
    if "quizQuestionTypes" in session:
        session.pop("quizQuestionTypes")
    if form.validate_on_submit():
        print(form.tagSelection.data, form.questionTypes.data)
        t = form.tagSelection.data
        types = form.questionTypes.data
        print(t)
        if t is not None and types is not None:
            tag = [ts[int(id)-1][1] for id in t]
            session["quizQuestions"] = QuestionFetch.getRandomQuestions(count=10, tags=tag, types=types)
        return redirect(url_for("question"))
    return render_template("QuizSetup.html", tags=tags, form=form)

# Starts local development server when run directly
if __name__ == "__main__":
    app.run(debug=True)
