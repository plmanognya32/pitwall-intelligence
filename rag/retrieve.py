import os
import google.generativeai as genai
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

def get_query_embedding(text):
    """embed search query"""
    result = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="retrieval_query"
    )
    return result["embedding"]

def retrieve(query, series=None, season=None, top_k=5):
    """ filter race documents by relevance, series and season. returns a list of chunk text string """
    query_vector = get_query_embedding(query)

    params = {
        "query_embedding": query_vector,
        "match_count": top_k,
    }

    # supabase for vector search
    results = supabase.rpc(
        "match_race_documents", params
    ).execute().data

    if series:
        results = [r for r in results if r.get("series") == series]

    if season:
        results = [r for f in results if r.get("season") == season]

    return [r["chunk_text"] for r in results]

if __name__ == "__main__":
    docs = retrieve("wet weather race strategy", series="f1")
    for d in docs:
        print(d)
        print("---")