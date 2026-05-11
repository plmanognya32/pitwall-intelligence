import os
from google import genai
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

EMBED_MODEL = "models/text-embedding-004"

def get_query_embedding(text):
    result = client.models.embed_content(
        model="text-embedding-004",
        contents=text,
    )
    return result.embeddings[0].values

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