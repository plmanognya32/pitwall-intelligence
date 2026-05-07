import os
import requests
import time
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# MotoGP public API - free, no key needed
MOTOGP_BASE = "https://api.motogp.pulselive.com/motogp/v1"

def fetch_json(url):
    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json()

def upsert_circuit(circuit_name, country):
    """MotoGP API gives less circuit detail so we keep it simple."""
    circuit_key = circuit_name.lower().replace(" ", "_")
    circuit = {
        "circuit_key": f"motogp_{circuit_key}",
        "name": circuit_name,
        "country": country,
    }
    supabase.table("circuits").upsert(
        circuit, on_conflict="circuit_key"
    ).execute()
    row = supabase.table("circuits").select("id").eq(
        "circuit_key", f"motogp_{circuit_key}"
    ).single().execute()
    return row.data["id"]

def ingest_season(season):
    """Pull MotoGP race results for a season."""
    print(f"--- ingesting MotoGP season {season} ---")
    # fetch the event calendar for the season
    url = f"{MOTOGP_BASE}/results/seasons/{season}/events"
    try:
        events = fetch_json(url)
    except Exception as e:
        print(f"  could not fetch events: {e}")
        return

    for event in events:
        event_id = event.get("id")
        event_name = event.get("name", "Unknown GP")
        country = event.get("country", {}).get("name", "Unknown")

        circuit_id = upsert_circuit(event_name, country)

        # upsert the race row
        race = {
            "series": "motogp",
            "season": int(season),
            "round": event.get("number", 0),
            "race_name": event_name,
            "circuit_id": circuit_id,
        }
        supabase.table("races").upsert(
            race, on_conflict="series,season,round"
        ).execute()
        race_row = supabase.table("races").select("id").eq(
            "series", "motogp"
        ).eq("season", int(season)).eq(
            "round", event.get("number", 0)
        ).single().execute()
        race_id = race_row.data["id"]

        # fetch session results for this event
        ingest_event_results(event_id, race_id)
        time.sleep(0.5)

    print(f"  MotoGP season {season} done")

def ingest_event_results(event_id, race_id):
    """Pull rider results for one MotoGP event."""
    url = f"{MOTOGP_BASE}/results/events/{event_id}/categories/MotoGP/sessions/RAC/classification"
    try:
        data = fetch_json(url)
    except Exception as e:
        print(f"  skipping event {event_id}: {e}")
        return

    rows = []
    for entry in data.get("classification", []):
        rows.append({
            "race_id": race_id,
            "rider_name": entry.get("rider", {}).get("full_name", "Unknown"),
            "team": entry.get("team", {}).get("name", "Unknown"),
            "finish_position": entry.get("position"),
            "fastest_lap_secs": entry.get("best_lap_time"),
            "points": entry.get("points", 0),
            "dnf": entry.get("status", "").upper() in ["DNF", "DNS", "RET"],
        })

    if rows:
        supabase.table("motogp_sessions").insert(rows).execute()

if __name__ == "__main__":
    seasons = range(2010, 2025)
    for season in seasons:
        try:
            ingest_season(2023)
        except:
            print(f" MotoGP season {season} failed: {e}, skipping.")
    print("MotoGP ingestion complete.")