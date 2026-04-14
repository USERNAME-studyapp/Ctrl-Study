from supabase import create_client, Client
import os
import time
import random
import bcrypt
from datetime import datetime, timezone
from dotenv import load_dotenv
from typing import Any
from flask_login import UserMixin

# load variables from the .flaskenv file
load_dotenv()

# load the supabase url and key from the .flaskenv file
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

ctrlDB: Client = create_client(url, key)

class User(UserMixin):
    def __init__(self, username: str, role: str):
        # Flask-Login stores this in the session
        self.id = username
        self.username = username
        self.role = role

# ================ retryQuery: RETRIES THE QUERY 6 TIMES VIA DELAY TO DEAL WITH CONCURRENT REQUESTS ================
# USE: retryQuery(lambda: ctrlDB.table("questions").select("*").execute())
# the lambda thing is so that the following code is not executed until inside the retryQuery function
def retryQuery(op, *, attempts=6, baseDelay=0.2, maxDelay=2.0):
    lastException = None
    for attempt in range(attempts):
        try:
            return op()
        except Exception as e:
            # Keep track of the last exception to raise if we exhaust all attempts
            lastException = e

            # Random delays and jitter help mitigate concurrent request issues collisions i think.
            delay = min(maxDelay, baseDelay * (2 ** attempt))
            delay = delay * (0.5 + random.random())
            time.sleep(delay)
    raise lastException


# ================ FetchAllQuestions: FETCH ALL QUESTIONS FROM "questions" TABLE ================
def FetchAllQuestions() -> list[dict[str, Any]]:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    # Fetches only the fields needed to populate the select list
    response = retryQuery(lambda: ctrlDB.table("questions").select("id,title").order("id").execute())
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

    response = retryQuery(
        lambda: ctrlDB.table("questions")
        # TEMP: DB columns are swapped. TODO: swap back to prompt_template, question_template once fixed.
        .select("id,title,question_template,prompt_template,feedback_template,question_type,language")
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
def SaveQuestion(
    title: str,
    promptTemplate: str,
    answerTemplate: str,
    feedbackTemplate: str,
    questionType: str,
    language: str,
    tagIds: list[int],
) -> dict[str, Any] | None:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    # TEMP: DB columns are swapped. TODO: write prompt to prompt_template once fixed.
    payload = {
        "title": title,
        "question_template": promptTemplate,
        # TEMP: DB columns are swapped. TODO: write question to question_template once fixed.
        "prompt_template": answerTemplate,
        "feedback_template": feedbackTemplate,
        "question_type": questionType,
        "language": language,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    response = retryQuery(lambda: ctrlDB.table("questions").insert(payload).execute())
    insertError = getattr(response, "error", None)
    if insertError:
        raise RuntimeError(f"Supabase insert failed: {insertError}")

    data = getattr(response, "data", None)
    if isinstance(data, list) and data:
        created = data[0]
        questionId = created.get("id")
        if questionId is not None:
            SetQuestionTags(int(questionId), tagIds)
        return created
    raise RuntimeError("Supabase insert returned no rows.")


# ================ UpdateQuestion: UPDATE QUESTION IN "questions" TABLE ================
def UpdateQuestion(
    questionId: int,
    title: str,
    promptTemplate: str,
    answerTemplate: str,
    feedbackTemplate: str,
    questionType: str,
    language: str,
    tagIds: list[int],
) -> dict[str, Any] | None:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    # TEMP: DB columns are swapped. TODO: write prompt to prompt_template once fixed.
    payload = {
        "title": title,
        "question_template": promptTemplate,
        # TEMP: DB columns are swapped. TODO: write question to question_template once fixed.
        "prompt_template": answerTemplate,
        "feedback_template": feedbackTemplate,
        "question_type": questionType,
        "language": language,
    }

    response = retryQuery(lambda: ctrlDB.table("questions").update(payload).eq("id", questionId).execute())
    updateError = getattr(response, "error", None)
    if updateError:
        raise RuntimeError(f"Supabase update failed: {updateError}")

    data = getattr(response, "data", None)
    if isinstance(data, list) and data:
        updated = data[0]
        SetQuestionTags(questionId, tagIds)
        return updated
    return None


# ================ DeleteQuestion: DELETE QUESTION FROM "questions" TABLE ================
def DeleteQuestion(questionId: int) -> None:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    response = retryQuery(lambda: ctrlDB.table("questions").delete().eq("id", questionId).execute())
    deleteError = getattr(response, "error", None)
    if deleteError:
        raise RuntimeError(f"Supabase delete failed: {deleteError}")


# ================ SetQuestionTags: REPLACE TAG MAPPINGS FOR A QUESTION ================
def SetQuestionTags(questionId: int, tagIds: list[int]) -> None:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    deleteResponse = retryQuery(lambda: ctrlDB.table("question_tags").delete().eq("question_id", questionId).execute())
    deleteError = getattr(deleteResponse, "error", None)
    if deleteError:
        raise RuntimeError(f"Supabase delete failed: {deleteError}")

    if not tagIds:
        return

    payload = [{"question_id": questionId, "tag_id": tagId} for tagId in tagIds]
    insertResponse = retryQuery(lambda: ctrlDB.table("question_tags").insert(payload).execute())
    insertError = getattr(insertResponse, "error", None)
    if insertError:
        raise RuntimeError(f"Supabase insert failed: {insertError}")

# ================ FetchFilteredQuestions: FETCH ALL QUESTIONS BASED ON FILTERS ================
def FetchFilteredQuestions(tags: list[str], questionTypes: list[str], languages: list[str]) -> list[int]:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    # remove empty strings from the filters (empty string = no selection in the form, dont filter by that category)
    tags = [tag for tag in tags if str(tag).strip()]
    questionTypes = [qtype for qtype in questionTypes if str(qtype).strip()]
    languages = [lang for lang in languages if str(lang).strip()]

    # build query by only applying non-empty filters (empty list = no restriction)
    query = ctrlDB.table("questions")

    # check if list filters are empty or not and then keep building the query based on thta
    if tags:
        query = query.select("id, question_tags!inner(tags!inner(name))")
        query = query.in_("question_tags.tags.name", tags)
    else:
        query = query.select("id")

    if questionTypes:
        query = query.in_("question_type", questionTypes)

    if languages:
        query = query.in_("language", languages)

    response = retryQuery(lambda: query.execute())
    fetchError = getattr(response, "error", None)

    if fetchError:
        raise RuntimeError(f"Supabase fetch failed: {fetchError}")
    
    data = getattr(response, "data", None)
    if isinstance(data, list):
        # apparently set() is specific for uniqueness
        questionIds = set()
        for item in data:
            questionId = item.get("id")
            if questionId is not None:
                questionIds.add(questionId)
        return list(questionIds)

    return []


# ================ FetchAllTags: FETCH ALL TAGS FROM "tags" TABLE ================
def FetchAllTags() -> list[dict[str, Any]]:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    response = retryQuery(lambda: ctrlDB.table("tags").select("id,name,category").order("id").execute())
    fetchError = getattr(response, "error", None)
    if fetchError:
        raise RuntimeError(f"Supabase fetch failed: {fetchError}")

    data = getattr(response, "data", None)
    if isinstance(data, list):
        return data

    return []

# ================ FetchTagIdsForQuestion: FETCH TAG IDS FOR A QUESTION ================
def FetchTagIdsForQuestion(questionId: int) -> list[int]:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    response = retryQuery(lambda: ctrlDB.table("question_tags").select("tag_id").eq("question_id", questionId).execute())
    fetchError = getattr(response, "error", None)
    if fetchError:
        raise RuntimeError(f"Supabase fetch failed: {fetchError}")

    data = getattr(response, "data", None)
    if isinstance(data, list):
        return [int(item.get("tag_id")) for item in data if item.get("tag_id") is not None]

    return []

# ================ FetchRandomName: FETCH ONE RANDOM NAME FROM "randomnames" TABLE ================
def FetchRandomName() -> dict[str, Any] | None:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    response = retryQuery(
        lambda: ctrlDB.table("randomnames")
        .select("FirstName,MiddleInitial,LastName")
        .execute()
    )
    fetchError = getattr(response, "error", None)
    if fetchError:
        raise RuntimeError(f"Supabase fetch failed: {fetchError}")

    data = getattr(response, "data", None)
    if isinstance(data, list) and data:
        return random.choice(data)

    return None

# ================ AuthenticateUser: AUTHENTICATE USERNAME + PASSWORD FOR LOGIN ================
def AuthenticateUser(username: str, raw_password: str) -> User | None:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    # uhh this might be bad for rls protection but we don't currently have it on, sooo...
    response = retryQuery(
        lambda: ctrlDB.table("users")
        .select("username,password_hash,role")
        .eq("username", username)
        .limit(1)
        .execute()
    )
    fetchError = getattr(response, "error", None)
    if fetchError:
        raise RuntimeError(f"Supabase fetch failed: {fetchError}")

    data = getattr(response, "data", None)
    if not isinstance(data, list) or not data:
        return None
    
    row = data[0]
    stored_hash = row.get("password_hash")
    if not isinstance(stored_hash, str) or not stored_hash:
        return None

    if bcrypt.checkpw(raw_password.encode("utf-8"), stored_hash.encode("utf-8")):
        return User(username=str(row.get("username", "")), role=str(row.get("role", "")))
    return None


# ================ LoadUser: LOAD USER FOR FLASK-LOGIN SESSION ================
def LoadUser(user_id: str) -> User | None:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    response = retryQuery(
        lambda: ctrlDB.table("users")
        .select("username,role")
        .eq("username", user_id)
        .limit(1)
        .execute()
    )
    fetchError = getattr(response, "error", None)
    if fetchError:
        return None

    data = getattr(response, "data", None)
    if not isinstance(data, list) or not data:
        return None

    row = data[0]
    return User(username=str(row.get("username", "")), role=str(row.get("role", "")))
