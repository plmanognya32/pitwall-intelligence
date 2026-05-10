import os
import google.generativeai as genai
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

EMBED_MODEL = "models/embedding-001"

def get_query_embedding(text):
    result = genai.embed_content(
        model=EMBED_MODEL,
        content=text,
        task_type="retrieval_query"
    )
    return result["embedding"]

def retrieve(query, series=None, season=None, top_k=5):
    query_vector = get_query_embedding(query)

    results = supabase.rpc(
        "match_race_documents",
        {"query_embedding": query_vector, "match_count": top_k}
    ).execute().data

    if series:
        results = [r for r in results if r.get("series") == series]
    if season:
        results = [r for r in results if r.get("season") == season]

    return [r["chunk_text"] for r in results]