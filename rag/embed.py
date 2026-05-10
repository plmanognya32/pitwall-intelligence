import os
import google.generativeai as genai
from supabase import create_client

# connections
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

def get_embedding(text):
    """ text to vector """
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_document"
    )
    return result["embedding"]

def build_f1_chunk(race, laps):
    """converting race and lap data into readable texts"""
    last_lap = max((l["lap_number"] for l in laps), default=0)
    final_positions = [l for l in laps if l["lap_number"] == last_lap]
    final_positions.sort(key=lambda x: x["position"])
    winner = final_positions[0]["driver_code"] if final_positions else "Unknown"

    valid_laps = [l for l in laps if l["lap_time_secs"]]
    fastest = min(valid_laps, key=lambda x: x["lap_time_secs"]) if valid_laps else None
    fastest_str = (
        f"{fastest['driver_code']} ({fastest['lap_time_secs']:.3f}s)"
        if fastest else "Unknown"
    )

    pit_counts = {}
    for l in laps:
        if l.get("pit_in"):
            d = l["driver_code"]
            pit_counts[d] = pit_counts.get(d, 0) + 1

    compounds_used = list(set(
        l["compound"] for l in laps if l.get("compound")
    ))

    chunk = f"""
    F1 Race Report: {race['race_name']} {race['season']}
    Series: Formula 1
    Season: {race['season']}
    Round: {race['round']}
    Date: {race.get('race_date', 'Unknown')}
    Circuit: {race.get('circuit_name', 'Unknown')}, {race.get('circuit_country', 'Unknown')}
    Conditions: {race.get('conditions', 'Unknown')}
    Winner: {winner}
    Fastest Lap: {fastest_str}
    Total Lap: {last_lap}
    Tyre Compounds Used: {', '.join(compounds_used) if compounds_used else 'Unknown'}
    Pit Stop Summary: {', '.join(f'{d}:{c} stops' for d, c in pit_counts.items()) if pit_counts else 'No pit data'}
    """.strip()

    return chunk

def build_motogp_chunk(race, sesions):
    """ convert motogp race and session data into readable texts"""
    sessions_sorted = sorted(
        sesions, key=lambda x: x.get("finish_position") or 99
    )
    top3 = sessions_sorted[:3]
    top3_str = ", ".join(
        f"{s['rider_name']} ({s['team']})" for s in top3
    )
    dnf_count = sum(1 for s in sesions if s.get("dnf"))
    fastest = min(
        (s for s in sessions if s.get("fastest_lap_secs")),
        key=lambda x: x["fastest_lap_secs"],
        default=None
    )
    fastest_str = (
        f"{fastest['rider_name']} ({fastest['fastest_lap_secs']:.3f}s)"
        if fastest else "Unknown"
    )

    chunk = f"""
    MotoGP Race Report: {race['race_name']} {race['season']}
    Series: MotoGP
    Season: {race['season']}
    Round: {race['round']}
    Date: {race.get('race_date', 'Unknown')}
    Conditions: {race.get('conditions', 'Unknown')}
    Top 3 Finishers: {top3_str}
    Fastest Lap: {fastest_str}
    DNFs: {dnf_count}
    Total Classified Riders: {len(sessions)}
    """.strip()

    return chunk

def embed_season(season):
    """ embed all races of a season """
    print(f" embed season {season} ")

    races = supabase.table("races").select(
        "*, circuits(name, country)"
    ).eq("season", season).execute().data

    for race in races:
        race_id = race["id"]
        series = race["series"]

        circuit = race.get("circuits") or {}
        race["circuit_name"] = circuit.get("name", "Unknown")
        race["circuit_country"] = circuit.get("country", "Unknown")

        existing = supabase.table("race_documents").select("id").eq(
            "race_id", race_id
        ).execute().data
        if existing:
            print(f" skipping {race['race_name']} - already embedded")
            continue
        
        if series == "f1":
            laps = supabase.table("f1_laps").select("*").eq(
                "race_id", race_id
            ).execute().data
            if not laps:
                print(f" skipping {race['race_name']} - no lap data")
                continue
            chunk_text = build_f1_chunk(race, laps)

        elif series == "motogp":
            sessions = supabase.table("motogp_sessions").select("*").eq(
                "rece_id", race_id
            ).execute().data
            if not sessions:
                print(f" skipping {race['race_name']} - no session data")
                continue

            chunk_text = build_motogp_chunk(race, sessions)

        else:
            continue

        try:
            embedding = get_embedding(chunk_text)
        except Exception as e:
            print(f" embedding failed for {race['race_name']}: {e}")
            continue

        supabase.table("race_documents").insert({
            "race_id": race_id,
            "series": series,
            "chunk_text": chunk_text,
            "embedding": embedding,
            "chunk_type": "race_summary",
            "season": season,
        }).execute()

        print(f" embedded: {race['race_name']} ({series})")

    print(f" season {season} done")

if __name__ == "__main__":
    for season in range(2003, 2025):
        try:
            embed_season(season)
        except Exception as e:
            print(f"season {season} failed: {e}")
    
    print("Embedding complete.")