import os
import requests
import time
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Jolpica supports these motorcycle series:
# moto1 = 500cc / MotoGP premier class
# moto2, moto3 for lower classes
MOTOGP_BASE = "https://api.jolpi.ca/ergast/moto1"

def fetch_json(url):
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"  rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if attempt == 2:
                raise
            time.sleep(5)
    return None

def upsert_circuit(circuit_data):
    circuit_key = f"motogp_{circuit_data.get('circuitId', 'unknown')}"
    circuit = {
        "circuit_key": circuit_key,
        "name": circuit_data.get("circuitName", "Unknown"),
        "country": circuit_data.get("Location", {}).get("country", "Unknown"),
    }
    supabase.table("circuits").upsert(
        circuit, on_conflict="circuit_key"
    ).execute()
    row = supabase.table("circuits").select("id").eq(
        "circuit_key", circuit_key
    ).single().execute()
    return row.data["id"]

def ingest_season(season):
    print(f"--- ingesting MotoGP season {season} ---")
    url = f"{MOTOGP_BASE}/{season}/results.json?limit=1000"
    data = fetch_json(url)

    if not data:
        print(f"  no data for {season}, skipping")
        return

    races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    print(f"  found {len(races)} races")

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
        race_id = race_db.data["id"]

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
                "finish_position": int(entry["position"]) if entry.get("position", "").isdigit() else None,
                "fastest_lap_secs": fastest_secs,
                "points": int(float(entry.get("points", 0))),
                "dnf": not (entry.get("position", "").isdigit()),
            })

        if rows:
            supabase.table("motogp_sessions").insert(rows).execute()

        time.sleep(2)

    print(f"  MotoGP season {season} done")

if __name__ == "__main__":
    # moto1 covers 1949-2014 (500cc era + early MotoGP)
    for season in range(2003, 2015):
        try:
            ingest_season(season)
        except Exception as e:
            print(f"  season {season} failed: {e}, skipping")
        time.sleep(8)
    print("MotoGP ingestion complete.")