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


def FetchQuestionsTable() -> list[dict[str, Any]]:
    """Fetch all rows from the questions table in Supabase."""
    response = ctrlDB.table("questions").select("*").execute()
    data = getattr(response, "data", None)
    if isinstance(data, list):
        return data
    return []


def SaveQuestion(
    title: str,
    promptTemplate: str,
    answerTemplate: str,
) -> dict[str, Any] | None:
    if not url or not key:
        raise RuntimeError("Supabase credentials are missing.")

    payload = {
        "title": title,
        "prompt_template": promptTemplate,
        "answer_template": answerTemplate,
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
