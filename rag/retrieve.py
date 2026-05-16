import os
import requests
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

GEMINI_EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-embedding-001:embedContent?key={key}"
)

def get_query_embedding(text):
    url = GEMINI_EMBED_URL.format(key=GEMINI_API_KEY)
    payload = {
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": text}]},
        "taskType": "RETRIEVAL_QUERY"
    }
    resp = requests.post(url, json=payload, timeout=30)
    if not resp.ok:
        print(f"  embed error: {resp.status_code} {resp.text[:200]}")
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]

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