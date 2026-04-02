from __future__ import annotations

from typing import Any

from flask import redirect, render_template, request, session, url_for
from parser_engine import TemplateProcessingError, generateQuestion
from supabase_client import (
    FetchAllQuestions,
    FetchQuestionById,
    FetchAllTags,
    FetchTagIdsForQuestion,
    SaveQuestion,
    UpdateQuestion,
    DeleteQuestion,
)

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
    # Pulls answers and formats them as bullet-like lines
    answers = payload.get("answer", [])
    if isinstance(answers, list):
        answerLines = "\n".join(f"- {item}" for item in answers) or "(none)"
    else:
        answerLines = str(answers)

    # Pulls incorrect answers and formats them as bullet-like lines
    incorrect = payload.get("incorrect", [])
    incorrectLines = "\n".join(f"- {item}" for item in incorrect) or "(none)"
    # Pull feedback text if present, or defaults to "Incorrect" to avoid "None" in output (hardcoded because database defaults to Incorrect if NA)
    feedback = payload.get("feedback", "") or "Incorrect"

    # Returns one readable preview block
    return (
        "PROMPT:\n"
        f"{prompt}\n\n"
        "QUESTION:\n"
        f"{payload['question']}\n\n"
        "ANSWER(S):\n"
        f"{answerLines}\n\n"
        "INCORRECT OPTIONS:\n"
        f"{incorrectLines}\n\n"
        "FEEDBACK:\n"
        f"{feedback}\n"
    )


def parseQuestionId(rawId: str) -> int | None:
    try:
        return int(rawId)
    except (TypeError, ValueError):
        return None


def defaultState() -> dict[str, Any]:
    return {
        "templateText": defaultTemplate,
        "promptText": "",
        "feedbackText": "",
        "questionName": "",
        "questionType": "multiple_choice",
        "selectedTagIds": [],
        "selectedQuestionId": "",
        "previewOutput": "",
        "statusMessage": "",
    }


def applyRestoredState(state: dict[str, Any], restoredState: Any) -> None:
    if not isinstance(restoredState, dict):
        return

    state["templateText"] = str(restoredState.get("templateText", state["templateText"]))
    state["promptText"] = str(restoredState.get("promptText", state["promptText"]))
    state["feedbackText"] = str(restoredState.get("feedbackText", state["feedbackText"]))
    state["questionName"] = str(restoredState.get("questionName", state["questionName"]))
    state["questionType"] = str(restoredState.get("questionType", state["questionType"]))
    restoredTagIds = restoredState.get("selectedTagIds", state["selectedTagIds"])
    if isinstance(restoredTagIds, list):
        state["selectedTagIds"] = [int(tagId) for tagId in restoredTagIds]
    state["selectedQuestionId"] = str(
        restoredState.get("selectedQuestionId", state["selectedQuestionId"])
    )
    state["previewOutput"] = str(restoredState.get("previewOutput", state["previewOutput"]))
    state["statusMessage"] = str(restoredState.get("statusMessage", state["statusMessage"]))


def readFormIntoState(state: dict[str, Any]) -> tuple[str, str, int | None]:
    state["templateText"] = request.form.get("template_text", "")
    state["promptText"] = request.form.get("prompt_text", "")
    state["feedbackText"] = request.form.get("feedback_text", "")
    state["questionName"] = request.form.get("question_name", "")
    state["questionType"] = request.form.get("question_type", state["questionType"])
    action = request.form.get("action", "preview")
    rawTagIds = request.form.getlist("tag_ids")
    state["selectedTagIds"] = [int(tagId) for tagId in rawTagIds if tagId.isdigit()]

    chosenQuestionId = request.form.get("chosen_question_id", "").strip()
    hiddenSelectedId = request.form.get("selected_question_id", "").strip()
    state["selectedQuestionId"] = chosenQuestionId or hiddenSelectedId
    selectedQuestionIdValue = parseQuestionId(state["selectedQuestionId"])

    return action, chosenQuestionId, selectedQuestionIdValue


def handleLoad(state: dict[str, Any], chosenQuestionId: str) -> None:
    chosenIdValue = parseQuestionId(chosenQuestionId)
    if chosenIdValue is None:
        state["statusMessage"] = "Select a saved question to load."
        return

    try:
        selected = FetchQuestionById(chosenIdValue)
        if selected:
            state["selectedQuestionId"] = str(selected.get("id", ""))
            state["questionName"] = str(selected.get("title", ""))
            # TEMP: DB columns are swapped. TODO: swap back to question_template once fixed.
            state["templateText"] = str(selected.get("prompt_template", defaultTemplate))
            # TEMP: DB columns are swapped. TODO: swap back to prompt_template once fixed.
            state["promptText"] = str(selected.get("question_template", ""))
            state["feedbackText"] = str(selected.get("feedback_template", ""))
            state["questionType"] = str(selected.get("question_type", state["questionType"]))
            state["selectedTagIds"] = FetchTagIdsForQuestion(chosenIdValue)
            state["previewOutput"] = ""
            state["statusMessage"] = "Loaded saved question."
        else:
            state["statusMessage"] = "Select a saved question to load."
    except Exception as exc:
        state["statusMessage"] = f"Load failed: {exc}"


def handleDelete(state: dict[str, Any], chosenQuestionId: str) -> None:
    chosenIdValue = parseQuestionId(chosenQuestionId)
    if chosenIdValue is None:
        state["statusMessage"] = "Select a saved question to delete."
        return

    try:
        DeleteQuestion(chosenIdValue)
        state.update(defaultState())
        state["statusMessage"] = "Deleted saved question."
    except Exception as exc:
        state["statusMessage"] = f"Delete failed: {exc}"


def handleNew(state: dict[str, Any]) -> None:
    state.update(defaultState())
    state["statusMessage"] = "Ready for a new question."


def handleGenerate(action: str, state: dict[str, Any], selectedQuestionIdValue: int | None) -> None:
    try:
        payload = generateQuestion(
            state["templateText"], state["promptText"], state["feedbackText"]
        )
        state["previewOutput"] = formatPreview(payload)

        if action == "save":
            normalizedName = state["questionName"].strip() or "Untitled Question"
            try:
                if selectedQuestionIdValue is None:
                    created = SaveQuestion(
                        normalizedName,
                        state["promptText"],
                        state["templateText"],
                        state["feedbackText"],
                        state["questionType"],
                        state["selectedTagIds"],
                    )
                    if created:
                        state["selectedQuestionId"] = str(created.get("id", ""))
                    state["statusMessage"] = "Saved new question."
                else:
                    UpdateQuestion(
                        selectedQuestionIdValue,
                        normalizedName,
                        state["promptText"],
                        state["templateText"],
                        state["feedbackText"],
                        state["questionType"],
                        state["selectedTagIds"],
                    )
                    state["statusMessage"] = "Updated saved question."

                state["questionName"] = normalizedName
            except Exception as exc:
                state["statusMessage"] = f"Save failed: {exc}"
        else:
            state["statusMessage"] = "Preview generated."

    except TemplateProcessingError as exc:
        state["previewOutput"] = str(exc)
        state["statusMessage"] = "Generation failed."


# index handles page load and all form actions
def templateIndex():
    state = defaultState()

    # Loads questions and tags
    try:
        savedQuestions = FetchAllQuestions()
    except Exception:
        savedQuestions = []

    try:
        availableTags = FetchAllTags()
    except Exception:
        availableTags = []

    # Restores one-time state after redirect to prevent duplicate POST submits on refresh
    restoredState = session.pop("pageState", None)
    applyRestoredState(state, restoredState)

    # Processes form actions when user submits the page
    if request.method == "POST":
        action, chosenQuestionId, selectedQuestionIdValue = readFormIntoState(state)
        if action == "load":
            handleLoad(state, chosenQuestionId)
        elif action == "delete":
            handleDelete(state, chosenQuestionId)
        elif action == "new":
            handleNew(state)
        else:
            handleGenerate(action, state, selectedQuestionIdValue)

        # Stores post-action state for redirect-based rendering and redirect so browser refresh does not replay POST data
        session["pageState"] = state
        return redirect(url_for("templateIndex"))

    # Renders the page with current form state and saved-question list
    return render_template(
        "builder.html",
        template_text=state["templateText"],
        prompt_text=state["promptText"],
        feedback_text=state["feedbackText"],
        question_name=state["questionName"],
        question_type=state["questionType"],
        selected_question_id=state["selectedQuestionId"],
        saved_questions=savedQuestions,
        selected_tag_ids=state["selectedTagIds"],
        available_tags=availableTags,
        preview_output=state["previewOutput"],
        status_message=state["statusMessage"],
    )
