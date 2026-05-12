import os
import requests
import time
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

MOTOGP_BASE = "https://api.jolpi.ca/ergast/moto1"

def fetch_json(url):
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.json()

def upsert_circuit(circuit_name, country):
    circuit = {
        "circuit_key": f"motogp_{circuit_data.get('circuitId', 'unknown')}",
        "name": circuit_data.get("circuitName", "Unknown"),
        "country": circuit_data.get("Location", {}).get("country", "Unknown"),
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
    url = f"{MOTOGP_BASE}/{season}/results.json?limit=1000"
    try:
        events = fetch_json(url)
    except Exception as e:
        print(f"  could not fetch events {season}: {e}")
        return

    races = data.get("MRData", {}).get("RaceTable", {}).get("Races, []")
    print(f" found {len(races)} races")

    for race in races:
        round_num = race.get("round", 0)
        circuit_id = upsert_circuit(race.get("Circuit", {}))

        race_row = {
            "series": "motogp",
            "season": int(season),
            "round": int(round_num),
            "race_name": race.get("raceName", "Unknown GP"),
            "circuit_id": circuit_id,
            "race_date": race.get("date"),
        }
        supabase.table("races").upsert(
            race_row, on_conflict="series,season,round"
        ).execute()
        race_db = supabase.table("races").select("id").eq(
            "series", "motogp"
        ).eq("season", int(season)).eq(
            "round", int(round_num)
        ).single().execute()
        race_id = race_row.data["id"]

        results = race.get("Results", [])
        rows = []
        for entry in results:
            fastest = entry.get("FastestLap", {}).get("Time", {}).get("time")
            fastest_secs = None
            if fastest:
                try:
                    parts = fastest.split(":")
                    fastest_secs = float(parts[0]) * 60 + float(parts[1])
                except Exception:
                    pass

            status = entry.get("status", "")
            rows.append({
                "race_id": race_id,
                "rider_name": entry.get("Driver", {}).get("familyName", "Unknown"),
                "team": entry.get("Constructor", {}).get("name", "Unknown"),
                "finish_position": int(entry.get("position")) if entry.get("position") else None,
                "fastest_lap_secs": fastest_secs,
                "points": int(float(entry.get("points", 0))),
                "dnf": status.upper() not in ["FINISHED", ""] and not status.isdigit(),
            })

        if rows:
            supabase.table("motogp_sessions").insert(rows).execute()

        time.sleep(2)

    print(f" MotoGP season {season} done")

if __name__ == "__main__":
    seasons = range(2003, 2025)
    for season in seasons:
        try:
            ingest_season(2023)
        except:
            print(f" MotoGP season {season} failed: {e}, skipping.")
    print("MotoGP ingestion complete.")