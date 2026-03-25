# Purpose:
# This file is the Flask entrypoint for the template-based question generator app

# Function:
# - Displays one template input textbox and one question-name textbox
# - Supports Preview, Save, Load, Delete, and New actions
# - Uses parser_engine.generateQuestion to build preview output
# - Persists named question templates in a local JSON file for editing later


from __future__ import annotations

from typing import Any                                                          # Any is used for payload typing flexibility
from flask import Flask, redirect, render_template, request, session, url_for   # Flask imports provide routing, form access, session state, and redirects
from parser_engine import TemplateProcessingError, generateQuestion             # Parser imports provide generation and normalized error handling
from supabase_client import (                                                   # Supabase client import provides database access for question records
    FetchAllQuestions,
    FetchQuestionById,
    FetchAllTags,
    FetchTagIdsForQuestion,
    SaveQuestion,
    UpdateQuestion,
    DeleteQuestion,
)

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


def parseQuestionId(rawId: str) -> int | None:
    try:
        return int(rawId)
    except (TypeError, ValueError):
        return None


# index handles page load and all form actions
@app.route("/", methods=["GET", "POST"])
def index() -> str:
    # Initializes page state defaults
    templateText = defaultTemplate
    promptText = ""
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
            questionType = "multiple_choice"
            selectedTagIds = []
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
                    try:
                        if selectedQuestionIdValue is None:
                            created = SaveQuestion(
                                normalizedName,
                                promptText,
                                templateText,
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
            "questionName": questionName,
            "questionType": questionType,
            "selectedTagIds": selectedTagIds,
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
        question_type=questionType,
        selected_question_id=selectedQuestionId,
        saved_questions=savedQuestions,
        selected_tag_ids=selectedTagIds,
        available_tags=availableTags,
        preview_output=previewOutput,
        status_message=statusMessage,
    )


# Starts local development server when run directly
if __name__ == "__main__":
    app.run(debug=True)
