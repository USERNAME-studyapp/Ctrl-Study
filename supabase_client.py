from supabase import create_client, Client
import os
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
