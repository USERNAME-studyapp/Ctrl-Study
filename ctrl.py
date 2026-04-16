# Purpose:
# This file is the Flask entrypoint for the template-based question generator app

# Function:
# - Displays one template input textbox and one question-name textbox
# - Supports Preview, Save, Load, Delete, and New actions
# - Uses parser_engine.generateQuestion to build preview output
# - Persists named question templates in a local JSON file for editing later

from __future__ import annotations

from flask import Flask, render_template, session, request                             # Flask imports provide routing, form access, session state, and redirects

from Frontend import QuestionFetch
from Frontend.forms import RadioQuestionForm, SetupQuizForm, QuestionForm, ShortAnswerQuestionForm
from Frontend.LoginForm import LoginForm

from datetime import timedelta
from flask_session import Session

from flask import redirect, url_for
from flask_login import LoginManager, login_required, login_user, current_user, logout_user

import supabase_client
import template_builder

from Frontend.QuestionFetch import QuestionContainer, makeSeed

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

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id: str):
    try:
        return supabase_client.LoadUser(user_id)
    except Exception:
        return None

# proper home page
@app.route("/", methods=["GET"])
@app.route("/index", methods=["GET"])
def home():
    return render_template("index.html", title="Ctrl-Study: Home")


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    error = None

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST" and form.validate_on_submit():
        username = str(form.username.data or "").strip()
        password = str(form.password.data or "")
        try:
            user = supabase_client.AuthenticateUser(username, password)
        except Exception:
            user = None

        if user is not None:
            login_user(user)
            return redirect(url_for("templateIndex"))
        error = "Invalid username or password."

    return render_template("Login.html", title="Ctrl-Study: Login", form=form, error=error)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

@app.route("/template", methods=["GET", "POST"])
@login_required
def templateIndex():
    # template builder access for ONLY ADMINS
    if getattr(current_user, "role", None) != "admin":
        return redirect(url_for("home"))
    return template_builder.templateIndex()


@app.route("/quiz-complete", methods=["GET"])
def quizComplete():
    if "quizQuestions" not in session or "progress" not in session:
        print("User tried to use quiz results page without questions or progress in session")
        return redirect(url_for("quiz"))
    if session["progress"] < len(session["quizQuestions"]):
        print("too soon to see those results, don'cha think?")
        return redirect(url_for("question"))
    if "quizGivenAnswers" not in session:
        print("tried to use quiz results page without answers in session")
        return redirect(url_for("question"))
    if "correctness" not in session:
        print("no correctness huh")
        return redirect(url_for("quiz"))

    correctPercent = len([value for key, value in session["correctness"].items() if value]) / len(session["quizQuestions"])

    forms = list[QuestionForm]()
    for index, question in enumerate(session["quizQuestions"]):
        form = QuestionFetch.getQuestionForm(question, label=f"Answers{index}")
        data: list = session["quizGivenAnswers"][session["quizQuestions"].index(question)]
        print(data)
        print(form)
        if isinstance(form, RadioQuestionForm) or isinstance(form, ShortAnswerQuestionForm):
            form.answer.data = data[0]
        else:
            form.answer.data = data
        forms.append(form)

    print(session["correctness"])


    return render_template (
        "QuizComplete.html",
        title="Ctrl-Study: Quiz Complete",
        questions = session["quizQuestions"],
        givenAnswers = session["quizGivenAnswers"],
        correctness = session["correctness"],
        forms = forms,
        correctPercent = correctPercent
    )

@app.route("/question", methods=["GET", "POST"])
def question():
    if "quizQuestions" not in session:
        print("User tried to use quiz question page without questions in session")
        return redirect(url_for("quiz"))
    if "progress" not in session:
        session["progress"] = 0
    if "correctness" not in session:
        session["correctness"] = {}
    if "quizGivenAnswers" not in session:
        session["quizGivenAnswers"] = {}
    if session["progress"] >= len(session["quizQuestions"]):
        return redirect(url_for("quizComplete"))
    if "SingleQuestionState" not in session:
        session["SingleQuestionState"] = "NewQuestion"
    elif session["SingleQuestionState"] == "ToNewQuestion":
        session["SingleQuestionState"] = "NewQuestion"

    question = session["quizQuestions"][session["progress"]]
    form = QuestionFetch.getQuestionForm(question)

    # STATE MACHINE
    if request.method == "POST":
        action = request.form.get("action")
        if action == "next" and session["SingleQuestionState"] == "Answered":
            session["progress"] += 1
            session["SingleQuestionState"] = "ToNewQuestion"
            session.modified = True
            return redirect(url_for("question"))
        if action == "submit" and session["SingleQuestionState"] == "NewQuestion" and form.validate_on_submit():
            correct = form.correct
            answers = form.answer.data
            if not isinstance(answers, list):
                answers = [answers]
            answers = [answer.replace('\r\n', '\n') for answer in answers]
            isCorrect = set(answers) == set(correct)
            session["quizGivenAnswers"][session["progress"]] = answers
            session["correctness"][session["progress"]] = isCorrect
            session["SingleQuestionState"] = "Answered"
            session.modified = True

    if session["SingleQuestionState"] == "Answered":
        isCorrect = session["correctness"].get(session["progress"], False)
        return render_template(
            "individualQuestion.html",
            title="Question",
            form=form,
            status="Correct" if isCorrect else "Incorrect",
            showingAnswer=True,
            currentQuestion=session["progress"] + 1,
            totalQuestions=len(session["quizQuestions"]),
        )
    else:
        return render_template(
            "individualQuestion.html",
            title="Question",
            form=form,
            status="Please answer the question.",
            showingAnswer=False,
            currentQuestion=session["progress"] + 1,
            totalQuestions=len(session["quizQuestions"]),
        )


@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    tags = supabase_client.FetchUsedTags()
    types = ["multiple_choice", "multiple_select", "short_answer", "true_false"]
    languages = ["Python", "C++"]
    ts = [(tag["id"], tag["name"]) for tag in tags]
    form = SetupQuizForm(types=types, tags=ts, languages=languages)
    if "quizQuestions" in session:
        session.pop("quizQuestions")
    if "SingleQuestionState" in session:
        session.pop("SingleQuestionState")
    if "progress" in session:
        session.pop("progress")
    if "quizGivenAnswers" in session:
        session.pop("quizGivenAnswers")
    if "correctness" in session:
        session.pop("correctness")
    if form.validate_on_submit():
        print(form.tagSelection.data, form.questionTypes.data)
        t = form.tagSelection.data
        types = form.questionTypes.data
        count = form.questionCount.data
        languageSel = form.languageSelection.data
        seed = form.seed.data if form.seed.data else makeSeed()
        session["seed"] = seed
        print(t)
        if t is not None and types is not None and count is not None:
            tag = [ts[int(id)-1][1] for id in t]
            session["quizQuestions"] = QuestionFetch.getRandomQuestions(count=count, tags=tag, types=types, languages=languageSel, seed=seed)
        return redirect(url_for("question"))
    return render_template("QuizSetup.html", tags=tags, form=form)

# Starts local development server when run directly
if __name__ == "__main__":
    app.run(debug=True)
