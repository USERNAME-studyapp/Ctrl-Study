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

<<<<<<< HEAD
@app.route("/template", methods=["GET", "POST"])
def templateIndex() -> str:
    return template_builder.templateIndex()
=======
# index handles page load and all form actions
@app.route("/builder", methods=["GET", "POST"])
def builder():
    # Initializes page state defaults
    templateText = defaultTemplate
    promptText = ""
    feedbackText = ""
    questionName = ""
    questionType = "multiple_choice"
    selectedTagIds: list[int] = []
    selectedQuestionId = ""
    previewOutput = ""
    statusMessage = ""

    # Loads saved questions for sidebar display and operations
    try:
        savedQuestions = FetchAllQuestions()
    except Exception:
        savedQuestions = []

    # Loads available tags for the tag dropdown
    try:
        availableTags = FetchAllTags()
    except Exception:
        availableTags = []

    # Restores one-time state after redirect to prevent duplicate POST submits on refresh
    restoredState = session.pop("pageState", None)
    if isinstance(restoredState, dict):
        templateText = str(restoredState.get("templateText", templateText))
        promptText = str(restoredState.get("promptText", promptText))
        feedbackText = str(restoredState.get("feedbackText", feedbackText))
        questionName = str(restoredState.get("questionName", questionName))
        questionType = str(restoredState.get("questionType", questionType))
        restoredTagIds = restoredState.get("selectedTagIds", selectedTagIds)
        if isinstance(restoredTagIds, list):
            selectedTagIds = [int(tagId) for tagId in restoredTagIds]
        selectedQuestionId = str(restoredState.get("selectedQuestionId", selectedQuestionId))
        previewOutput = str(restoredState.get("previewOutput", previewOutput))
        statusMessage = str(restoredState.get("statusMessage", statusMessage))

    # Processes form actions when user submits the page
    if request.method == "POST":
        # Reads main form fields from request data
        templateText = request.form.get("template_text", "")
        promptText = request.form.get("prompt_text", "")
        feedbackText = request.form.get("feedback_text", "")
        questionName = request.form.get("question_name", "")
        questionType = request.form.get("question_type", questionType)
        action = request.form.get("action", "preview")
        rawTagIds = request.form.getlist("tag_ids")
        selectedTagIds = [int(tagId) for tagId in rawTagIds if tagId.isdigit()]

        # Reads selection sources for sidebar and hidden current selection state
        chosenQuestionId = request.form.get("chosen_question_id", "").strip()
        hiddenSelectedId = request.form.get("selected_question_id", "").strip()
        selectedQuestionId = chosenQuestionId or hiddenSelectedId
        selectedQuestionIdValue = parseQuestionId(selectedQuestionId)

        # Handles loading a selected saved question into the editor
        if action == "load":
            chosenIdValue = parseQuestionId(chosenQuestionId)
            if chosenIdValue is None:
                statusMessage = "Select a saved question to load."
            else:
                try:
                    selected = FetchQuestionById(chosenIdValue)
                    if selected:
                        selectedQuestionId = str(selected.get("id", ""))
                        questionName = str(selected.get("title", ""))
                        # TEMP: DB columns are swapped. TODO: swap back to question_template once fixed.
                        templateText = str(selected.get("prompt_template", defaultTemplate))
                        # TEMP: DB columns are swapped. TODO: swap back to prompt_template once fixed.
                        promptText = str(selected.get("question_template", ""))
                        feedbackText = str(selected.get("feedback_template", ""))
                        questionType = str(selected.get("question_type", questionType))
                        selectedTagIds = FetchTagIdsForQuestion(chosenIdValue)
                        previewOutput = ""
                        statusMessage = "Loaded saved question."
                    else:
                        statusMessage = "Select a saved question to load."
                except Exception as exc:
                    statusMessage = f"Load failed: {exc}"

        # Handles deleting a selected saved question
        elif action == "delete":
            chosenIdValue = parseQuestionId(chosenQuestionId)
            if chosenIdValue is None:
                statusMessage = "Select a saved question to delete."
            else:
                try:
                    DeleteQuestion(chosenIdValue)
                    selectedQuestionId = ""
                    questionName = ""
                    templateText = defaultTemplate
                    promptText = ""
                    feedbackText = ""
                    questionType = "multiple_choice"
                    selectedTagIds = []
                    previewOutput = ""
                    statusMessage = "Deleted saved question."
                except Exception as exc:
                    statusMessage = f"Delete failed: {exc}"

        # Handles resetting the editor to start a new question
        elif action == "new":
            selectedQuestionId = ""
            questionName = ""
            templateText = defaultTemplate
            promptText = ""
            feedbackText = ""
            questionType = "multiple_choice"
            selectedTagIds = []
            previewOutput = ""
            statusMessage = "Ready for a new question."

        # Handles preview and save flows that require generation
        else:
            try:
                # Generates rendered question data from current template text
                payload = generateQuestion(templateText, promptText, feedbackText)
                previewOutput = formatPreview(payload)

                # Saves either as new or as an update to selected question
                if action == "save":
                    normalizedName = questionName.strip() or "Untitled Question"
                    try:
                        if selectedQuestionIdValue is None:
                            created = SaveQuestion(
                                normalizedName,
                                promptText,
                                templateText,
                                feedbackText,
                                questionType,
                                selectedTagIds,
                            )
                            if created:
                                selectedQuestionId = str(created.get("id", ""))
                            statusMessage = "Saved new question."
                        else:
                            UpdateQuestion(
                                selectedQuestionIdValue,
                                normalizedName,
                                promptText,
                                templateText,
                                feedbackText,
                                questionType,
                                selectedTagIds,
                            )
                            statusMessage = "Updated saved question."

                        questionName = normalizedName
                    except Exception as exc:
                        statusMessage = f"Save failed: {exc}"
                else:
                    statusMessage = "Preview generated."

            # Displays parse/render errors in preview output area
            except TemplateProcessingError as exc:
                previewOutput = str(exc)
                statusMessage = "Generation failed."

        # Stores post-action state for redirect-based rendering
        session["pageState"] = {
            "templateText": templateText,
            "promptText": promptText,
            "feedbackText": feedbackText,
            "questionName": questionName,
            "questionType": questionType,
            "selectedTagIds": selectedTagIds,
            "selectedQuestionId": selectedQuestionId,
            "previewOutput": previewOutput,
            "statusMessage": statusMessage,
        }

        # Redirects to GET so browser refresh does not replay a POST action
        return redirect(url_for("builder"))

    # Renders the page with current form state and saved-question list
    return render_template(
        "builder.html",
        template_text=templateText,
        prompt_text=promptText,
        feedback_text=feedbackText,
        question_name=questionName,
        question_type=questionType,
        selected_question_id=selectedQuestionId,
        saved_questions=savedQuestions,
        selected_tag_ids=selectedTagIds,
        available_tags=availableTags,
        preview_output=previewOutput,
        status_message=statusMessage,
    )
>>>>>>> 1905361 (Multi-question forms now possible, also better? state machine)


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
