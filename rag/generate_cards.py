import os
import json
import requests
from supabase import create_client
from retrieve import retrieve

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

GEMINI_GENERATE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent?key={key}"
)

CARD_TOPICS = [
    {"topic": "wet weather race strategy in F1", "series": "f1", "tag": "Strategy"},
    {"topic": "closest finish and last lap lead changes in F1", "series": "f1", "tag": "Drama"},
    {"topic": "dominant wins and fastest lap records in F1", "series": "f1", "tag": "Performance"},
    {"topic": "MotoGP races with most DNFs and crashes", "series": "motogp", "tag": "Incident"},
    {"topic": "MotoGP championship deciding races", "series": "motogp", "tag": "Championship"},
]

def generate_text(prompt):
    url = GEMINI_GENERATE_URL.format(key=GEMINI_AI_KEY)
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 512
        }
    }
    resp = requests.post(url, json=payload, timeout=30)
    if not resp.ok:
        print(f"  generate error: {resp.status_code} {resp.text[:200]}")
        resp.raise_for_status()
    candidates = resp.json().get("candidates", [])
    if not candidates:
        return None
    return candidates[0]["content"]["parts"][0]["text"]

def generate_card(topic_config):
    topic = topic_config["topic"]
    series = topic_config["series"]
    tag = topic_config["tag"]

    docs = retrieve(topic, series=series, top_k=4)
    if not docs:
        print(f"  no docs found for: {topic}")
        return None

    context = "\n\n---\n\n".join(docs)
    prompt = f"""You are PitWall, a motorsport intelligence analyst.
Based only on the race data below, write a concise briefing card.

Topic: {topic}

Race Data:
{context}

Write a briefing card with:
- A sharp, specific title (max 10 words)
- A 2-3 sentence insight grounded in the data above
- Do not invent facts not present in the data

Respond in this exact JSON format with no markdown or code fences:
{{"title": "...", "body": "...", "tag": "{tag}"}}"""

    try:
        text = generate_text(prompt)
        if not text:
            return None
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        print(f"  card generation failed: {e}")
        return None

def generate_all_cards():
    print("--- generating AI briefing cards ---")
    cards = []
    for topic_config in CARD_TOPICS:
        print(f"  generating: {topic_config['topic']}")
        card = generate_card(topic_config)
        if card:
            cards.append(card)
            print(f"  done: {card['title']}")

    if cards:
        supabase.table("briefing_cards").delete().neq("id", 0).execute()
        supabase.table("briefing_cards").insert(cards).execute()
        print(f"  stored {len(cards)} cards")

    return cards

if __name__ == "__main__":
    generate_all_cards()
    print("Card generation complete.")