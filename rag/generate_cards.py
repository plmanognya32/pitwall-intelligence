import os
import json
import google.generativeai as genai
from supabase import create_client
from retrieve import retrieve

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
GEMINI_AI_KEY = os.environ["GEMINI_AI_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-1.5-flash")

CARD_TOPICS = [
    {
        "topic": "wet weather race strategy in F1",
        "series": "f1",
        "tag": "Strategy"
    },
    {
        "topic": "closest finish and last lap lead changes in F1",
        "series": "f1",
        "tag": "Drama"
    },
    {
        "topic": "dominant wins and fastest lap records in F1",
        "series": "f1",
        "tag": "Performance"
    },
    {
        "topic": "MotoGP races with most DNFs and crashes",
        "series": "motogp",
        "tag": "Incident"
    },
    {
        "topic": "MotoGP championship deciding races",
        "series": "motogp",
        "tag": "Championship"
    },
]

def generate_card(topic_config):
    """generating brief card for topic"""
    topic = topic_config["topic"]
    series = topic_config["series"]
    tag = topic_config["tag"]
    
    # retrieving relevant race docs
    docs = retrieve(topic, series=series, top_k=4)
    if not docs:
        print(f" no docs found for: {topic}")
        return None

    context = "\n\n--\n\n".join(docs)

    prompt =f"""
    You are PitWall, a motorsport intelligence analyst.
    Based only on the race data below, write a concise briefing card.
    Topic: {topic}

    Race Data: {context}

    Write a briefing card with:
    - A sharp, specific title (max 10 words)
    - A 2-3 sentence insight grounded in the data above
    - Do not invent facts that are not present in the data

    Respond in this exact JSON format:
    {{
        "title": "...",
        "body": "...",
        "tag": "{tag}"
    }}
    """

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        card = json.loads(text.strip())
        return card
    except Exception as e:
        print(f" card generation failed: {e}")
        return None

def generate_all_cards():
    """ generate all briefing cards and store in supabase """
    print("--- generating AI briefing cards ---")

    # create cards table if doesnt exist
    cards = []
    for topic_config in CARD_TOPICS:
        print(f" generating: {topic_config['topic']}")
        card = generate_card(topic_config)
        if card:
            cards.append(card)
            print(f" done: {card['title']}")

    # store cards in supabase
    if cards:
        supabase.table("briefing_cards").delete().neq(
            "id", 0
        ).execute()
        supabase.table("briefing_cards").insert(cards).execute()
        print(f" stored {len(cards)} cards")

    return cards

if __name__ == "__main__":
    generate_all_cards()
    print("Card generation complete.")