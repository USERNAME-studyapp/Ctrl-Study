# Purpose:
# This file is the Flask entrypoint for the template-based question generator app

# Function:
# - Displays one template input textbox and one question-name textbox
# - Supports Preview, Save, Load, Delete, and New actions
# - Uses parser_engine.generateQuestion to build preview output
# - Persists named question templates in a local JSON file for editing later


from __future__ import annotations

import json                                                                     # JSON is used to persist saved questions.# JSON is used to persist saved questions
import uuid                                                                     # UUID is used to assign stable ids to saved question records
from pathlib import Path                                                        # Path is used for local file operations
from typing import Any                                                          # Any is used for payload typing flexibility
from flask import Flask, redirect, render_template, request, session, url_for   # Flask imports provide routing, form access, session state, and redirects
from parser_engine import TemplateProcessingError, generateQuestion             # Parser imports provide generation and normalized error handling
from supabase_client import FetchQuestionsTable                                 # Supabase client import provides database access for question records

# app is the Flask application instance
app = Flask(__name__)
app.secret_key = "template-question-builder-secret"


# defaultTemplate pre-fills the editor with a working starter template
defaultTemplate = """variables:
var1 = UInt("myVar", 4, 10);
var2 = greaterThan(var1);
out1 = UInt();
out2 = UInt();
out3 = UInt();
out4 = UInt();

question:
int {{ var1.name }} = {{ var1 }};
if ({{ var1.name }} < {{ var2 }})
    if ({{ var1.name }} > {{ lessThan(var1) }})
        if ({{ var1.name }} != {{ var1 }})
            cout << "{{ out1 }} ";
        else
            cout << "{{ out2 }} ";
else
        cout << "{{ out3 }} ";
cout << "{{ out4 }} ";

answer:
{{ out2 }} {{ out4 }}

incorrect:
combinations("{{ x }} {{ y }}", out1, out2, out3, out4)
"""


# questionsFile is where saved question templates are stored for now
questionsFile = Path(__file__).resolve().parent / "questions.json"


# formatPreview converts generated payload into readable textarea output
def formatPreview(payload: dict[str, Any]) -> str:
    # Pulls prompt text if present
    prompt = payload.get("prompt", "")
    # Pulls incorrect answers and formats them as bullet-like lines
    incorrect = payload.get("incorrect", [])
    incorrectLines = "\n".join(f"- {item}" for item in incorrect) or "(none)"

    # Returns one readable preview block
    return (
        "PROMPT:\n"
        f"{prompt}\n\n"
        "QUESTION:\n"
        f"{payload['question']}\n\n"
        "ANSWER:\n"
        f"{payload['answer']}\n\n"
        "INCORRECT OPTIONS:\n"
        f"{incorrectLines}\n"
    )


# loadSavedQuestions reads all saved templates from disk
def loadSavedQuestions() -> list[dict[str, Any]]:
    # Returns an empty list when no save file exists yet
    if not questionsFile.exists():
        return []

    # Tries to load JSON safely; falls back to empty list on invalid file content
    try:
        try:
            with questionsFile.open("r", encoding="utf-8") as fileHandle:
                loaded = json.load(fileHandle)
        except json.JSONDecodeError:
            with questionsFile.open("r", encoding="utf-8-sig") as fileHandle:
                loaded = json.load(fileHandle)

        if not isinstance(loaded, list):
            return []

        # Normalizes saved records so only template "recipe" fields are kept
        normalized: list[dict[str, Any]] = []
        for item in loaded:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "id": str(item.get("id", "")),
                    "name": str(item.get("name", "Untitled Question")),
                    "templateText": str(item.get("templateText", defaultTemplate)),
                    "promptText": str(item.get("promptText", "")),
                }
            )
        return normalized
    except json.JSONDecodeError:
        return []


# writeSavedQuestions writes the full saved-question list back to disk
def writeSavedQuestions(savedQuestions: list[dict[str, Any]]) -> None:
    with questionsFile.open("w", encoding="utf-8") as fileHandle:
        json.dump(savedQuestions, fileHandle, indent=2)


# findQuestionById returns a saved question record by id
def findQuestionById(savedQuestions: list[dict[str, Any]], questionId: str) -> dict[str, Any] | None:
    for item in savedQuestions:
        if item.get("id") == questionId:
            return item
    return None


# index handles page load and all form actions
@app.route("/", methods=["GET", "POST"])
def index() -> str:
    # Initializes page state defaults
    templateText = defaultTemplate
    promptText = ""
    questionName = ""
    selectedQuestionId = ""
    previewOutput = ""
    statusMessage = ""

    # Loads saved questions for sidebar display and operations
    savedQuestions = loadSavedQuestions()

    # ==================== TEST-ONLY SUPABASE FETCH ====================
    try:
        supabaseQuestions = FetchQuestionsTable()
    except Exception:
        supabaseQuestions = [{"error": "Supabase fetch failed (TEST ONLY)"}]

    # Restores one-time state after redirect to prevent duplicate POST submits on refresh
    restoredState = session.pop("pageState", None)
    if isinstance(restoredState, dict):
        templateText = str(restoredState.get("templateText", templateText))
        promptText = str(restoredState.get("promptText", promptText))
        questionName = str(restoredState.get("questionName", questionName))
        selectedQuestionId = str(restoredState.get("selectedQuestionId", selectedQuestionId))
        previewOutput = str(restoredState.get("previewOutput", previewOutput))
        statusMessage = str(restoredState.get("statusMessage", statusMessage))

    # Processes form actions when user submits the page
    if request.method == "POST":
        # Reads main form fields from request data
        templateText = request.form.get("template_text", "")
        promptText = request.form.get("prompt_text", "")
        questionName = request.form.get("question_name", "")
        action = request.form.get("action", "preview")

        # Reads selection sources for sidebar and hidden current selection state
        chosenQuestionId = request.form.get("chosen_question_id", "").strip()
        hiddenSelectedId = request.form.get("selected_question_id", "").strip()
        selectedQuestionId = chosenQuestionId or hiddenSelectedId

        # Handles loading a selected saved question into the editor
        if action == "load":
            selected = findQuestionById(savedQuestions, chosenQuestionId)
            if selected:
                selectedQuestionId = str(selected.get("id", ""))
                questionName = str(selected.get("name", ""))
                templateText = str(selected.get("templateText", defaultTemplate))
                promptText = str(selected.get("promptText", ""))
                previewOutput = ""
                statusMessage = "Loaded saved question."
            else:
                statusMessage = "Select a saved question to load."

        # Handles deleting a selected saved question
        elif action == "delete":
            beforeCount = len(savedQuestions)
            savedQuestions = [item for item in savedQuestions if item.get("id") != chosenQuestionId]
            afterCount = len(savedQuestions)

            if afterCount < beforeCount:
                writeSavedQuestions(savedQuestions)
                selectedQuestionId = ""
                questionName = ""
                templateText = defaultTemplate
                promptText = ""
                previewOutput = ""
                statusMessage = "Deleted saved question."
            else:
                statusMessage = "Select a saved question to delete."

        # Handles resetting the editor to start a new question
        elif action == "new":
            selectedQuestionId = ""
            questionName = ""
            templateText = defaultTemplate
            promptText = ""
            previewOutput = ""
            statusMessage = "Ready for a new question."

        # Handles preview and save flows that require generation
        else:
            try:
                # Generates rendered question data from current template text
                payload = generateQuestion(templateText, promptText)
                previewOutput = formatPreview(payload)

                # Saves either as new or as an update to selected question
                if action == "save":
                    normalizedName = questionName.strip() or "Untitled Question"
                    questionId = selectedQuestionId or str(uuid.uuid4())        #creates random 128 bit id apparently

                    record = {
                        "id": questionId,
                        "name": normalizedName,
                        "templateText": templateText,
                        "promptText": promptText,
                    }

                    existing = findQuestionById(savedQuestions, questionId)
                    if existing:
                        existing.update(record)
                        statusMessage = "Updated saved question."
                    else:
                        savedQuestions.append(record)
                        statusMessage = "Saved new question."

                    writeSavedQuestions(savedQuestions)
                    selectedQuestionId = questionId
                    questionName = normalizedName
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
            "questionName": questionName,
            "selectedQuestionId": selectedQuestionId,
            "previewOutput": previewOutput,
            "statusMessage": statusMessage,
        }

        # Redirects to GET so browser refresh does not replay a POST action
        return redirect(url_for("index"))

    # Renders the page with current form state and saved-question list
    return render_template(
        "index.html",
        template_text=templateText,
        prompt_text=promptText,
        question_name=questionName,
        selected_question_id=selectedQuestionId,
        saved_questions=savedQuestions,
        preview_output=previewOutput,
        status_message=statusMessage,

        #TESTING ONLY FOR DATABASE CONNECTION
        supabase_questions=supabaseQuestions, 
    )


# Starts local development server when run directly
if __name__ == "__main__":
    app.run(debug=True)
