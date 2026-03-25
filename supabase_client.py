from supabase import create_client, Client
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from typing import Any

# load variables from the .flaskenv file
load_dotenv()

# load the supabase url and key from the .flaskenv file
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

ctrlDB: Client = create_client(url, key)

# ================ FetchAllQuestions: FETCH ALL QUESTIONS FROM "questions" TABLE ================
def FetchAllQuestions() -> list[dict[str, Any]]:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    # Fetches only the fields needed to populate the select list
    response = ctrlDB.table("questions").select("id,title").order("id").execute()
    fetchError = getattr(response, "error", None)
    if fetchError:
        raise RuntimeError(f"Supabase fetch failed: {fetchError}")

    data = getattr(response, "data", None)
    if isinstance(data, list):
        return data

    return []

# ================ FetchQuestionById: FETCH A SINGLE QUESTION BY ID FROM "questions" TABLE ================
def FetchQuestionById(questionId: int) -> dict[str, Any] | None:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    response = (
        ctrlDB.table("questions")
        # TEMP: DB columns are swapped. TODO: swap back to prompt_template, question_template once fixed.
        .select("id,title,question_template,prompt_template")
        .eq("id", questionId)
        .execute()
    )
    fetchError = getattr(response, "error", None)
    if fetchError:
        raise RuntimeError(f"Supabase fetch failed: {fetchError}")

    data = getattr(response, "data", None)
    if isinstance(data, list) and data:
        return data[0]

    return None

# ================ SaveQuestion: SAVE QUESTION TO "questions" TABLE IN DATABASE ================
def SaveQuestion(title: str, promptTemplate: str, answerTemplate: str) -> dict[str, Any] | None:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    # TEMP: DB columns are swapped. TODO: write prompt to prompt_template once fixed.
    payload = {
        "title": title,
        "question_template": promptTemplate,
        # TEMP: DB columns are swapped. TODO: write question to question_template once fixed.
        "prompt_template": answerTemplate,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    response = ctrlDB.table("questions").insert(payload).execute()
    insertError = getattr(response, "error", None)
    if insertError:
        raise RuntimeError(f"Supabase insert failed: {insertError}")

    data = getattr(response, "data", None)
    if isinstance(data, list) and data:
        return data[0]
    raise RuntimeError("Supabase insert returned no rows.")


# ================ UpdateQuestion: UPDATE QUESTION IN "questions" TABLE ================
def UpdateQuestion( questionId: int, title: str, promptTemplate: str, answerTemplate: str) -> dict[str, Any] | None:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    # TEMP: DB columns are swapped. TODO: write prompt to prompt_template once fixed.
    payload = {
        "title": title,
        "question_template": promptTemplate,
        # TEMP: DB columns are swapped. TODO: write question to question_template once fixed.
        "prompt_template": answerTemplate,
    }

    response = ctrlDB.table("questions").update(payload).eq("id", questionId).execute()
    updateError = getattr(response, "error", None)
    if updateError:
        raise RuntimeError(f"Supabase update failed: {updateError}")

    data = getattr(response, "data", None)
    if isinstance(data, list) and data:
        return data[0]
    return None


# ================ DeleteQuestion: DELETE QUESTION FROM "questions" TABLE ================
def DeleteQuestion(questionId: int) -> None:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    response = ctrlDB.table("questions").delete().eq("id", questionId).execute()
    deleteError = getattr(response, "error", None)
    if deleteError:
        raise RuntimeError(f"Supabase delete failed: {deleteError}")
