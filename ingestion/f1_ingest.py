import os
import requests
import time
from supabase import create_client

# --- connect to supabase ---
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Ergast base URL - completely free, no key needed
ERGAST_BASE = "https://api.jolpi.ca/ergast/f1"

def fetch_json(url):
    """Fetch JSON from a URL with basic error handling."""
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.json()

def upsert_circuit(circuit_data):
    """Insert circuit if it doesn't exist yet, skip if it does."""
    circuit = {
        "circuit_key": circuit_data["circuitId"],
        "name": circuit_data["circuitName"],
        "country": circuit_data["Location"]["country"],
        "lat": float(circuit_data["Location"]["lat"]),
        "lng": float(circuit_data["Location"]["long"]),
    }
    result = supabase.table("circuits").upsert(
        circuit, on_conflict="circuit_key"
    ).execute()
    # return the circuit's id
    row = supabase.table("circuits").select("id").eq(
        "circuit_key", circuit["circuit_key"]
    ).single().execute()
    return row.data["id"]

def upsert_race(season, round_num, race_data, circuit_id):
    """Insert race row, skip if already exists."""
    race = {
        "series": "f1",
        "season": int(season),
        "round": int(round_num),
        "race_name": race_data["raceName"],
        "circuit_id": circuit_id,
        "race_date": race_data["date"],
    }
    supabase.table("races").upsert(
        race, on_conflict="series,season,round"
    ).execute()
    row = supabase.table("races").select("id").eq("series", "f1").eq(
        "season", int(season)
    ).eq("round", int(round_num)).single().execute()
    return row.data["id"]

def ingest_season_results(season):
    """Pull every race result for a given F1 season."""
    print(f"--- ingesting F1 season {season} ---")
    url = f"{ERGAST_BASE}/{season}/results.json?limit=1000"
    data = fetch_json(url)
    races = data["MRData"]["RaceTable"]["Races"]
    print(f"  found {len(races)} races")

    for race in races:
        round_num = race["round"]
        circuit_id = upsert_circuit(race["Circuit"])
        race_id = upsert_race(season, round_num, race, circuit_id)

        # pull lap times for this race (separate endpoint)
        ingest_laps(season, round_num, race_id)
        # be polite to the free API - don't hammer it
        time.sleep(0.5)

    print(f"  season {season} done")

def ingest_laps(season, round_num, race_id):
    """Pull lap-by-lap data for one race."""
    page = 0
    limit = 100
    while True:
        offset = page * limit
        url = (
            f"{ERGAST_BASE}/{season}/{round_num}/laps.json"
            f"?limit={limit}&offset={offset}"
        )
        data = fetch_json(url)
        laps_table = data["MRData"]["RaceTable"]["Races"]

        # no more data
        if not laps_table:
            break

        laps_raw = laps_table[0]["Laps"]
        if not laps_raw:
            break

        rows = []
        for lap in laps_raw:
            lap_num = int(lap["number"])
            for timing in lap["Timings"]:
                # convert "1:23.456" to seconds
                t = timing["time"]
                try:
                    parts = t.split(":")
                    secs = float(parts[0]) * 60 + float(parts[1])
                except Exception:
                    secs = None

                rows.append({
                    "race_id": race_id,
                    "driver_code": timing["driverId"],
                    "lap_number": lap_num,
                    "lap_time_secs": secs,
                    "position": int(timing["position"]),
                })

        if rows:
            supabase.table("f1_laps").insert(rows).execute()

        page += 1
        time.sleep(0.3)

if __name__ == "__main__":
    # start with 2023 — a full recent season with clean data
    # once this works we'll add more seasons
    ingest_season_results(2023)
    print("F1 ingestion complete.")