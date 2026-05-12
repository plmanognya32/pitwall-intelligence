import os
import requests
import time
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

ERGAST_BASE = "https://api.jolpi.ca/ergast/f1"

def fetch_json(url):
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"  rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if attempt == 2:
                raise
            time.sleep(5)
    raise Exception("max retries exceeded")

def upsert_circuit(circuit_data):
    circuit = {
        "circuit_key": circuit_data["circuitId"],
        "name": circuit_data["circuitName"],
        "country": circuit_data["Location"]["country"],
        "lat": float(circuit_data["Location"]["lat"]),
        "lng": float(circuit_data["Location"]["long"]),
    }
    supabase.table("circuits").upsert(
        circuit, on_conflict="circuit_key"
    ).execute()
    row = supabase.table("circuits").select("id").eq(
        "circuit_key", circuit["circuit_key"]
    ).single().execute()
    return row.data["id"]

def upsert_race(season, round_num, race_data, circuit_id):
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
    row = supabase.table("races").select("id").eq(
        "series", "f1"
    ).eq("season", int(season)).eq(
        "round", int(round_num)
    ).single().execute()
    return row.data["id"]

def ingest_laps(season, round_num, race_id):
    """Only fetch laps for recent seasons to avoid rate limits."""
    page = 0
    limit = 100
    while True:
        offset = page * limit
        url = (
            f"{ERGAST_BASE}/{season}/{round_num}/laps.json"
            f"?limit={limit}&offset={offset}"
        )
        try:
            data = fetch_json(url)
        except Exception as e:
            print(f"    lap fetch failed: {e}")
            break

        laps_table = data["MRData"]["RaceTable"]["Races"]
        if not laps_table:
            break
        laps_raw = laps_table[0]["Laps"]
        if not laps_raw:
            break

        rows = []
        for lap in laps_raw:
            lap_num = int(lap["number"])
            for timing in lap["Timings"]:
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
        time.sleep(2)

def ingest_season_results(season):
    print(f"--- ingesting F1 season {season} ---")
    url = f"{ERGAST_BASE}/{season}/results.json?limit=1000"
    data = fetch_json(url)
    races = data["MRData"]["RaceTable"]["Races"]
    print(f"  found {len(races)} races")

    for race in races:
        round_num = race["round"]
        circuit_id = upsert_circuit(race["Circuit"])
        race_id = upsert_race(season, round_num, race, circuit_id)

        # only fetch laps for 2021 onwards — reduces API hammering
        if int(season) >= 2021:
            ingest_laps(season, round_num, race_id)

        time.sleep(3)

    print(f"  season {season} done")

if __name__ == "__main__":
    for season in range(2003, 2025):
        try:
            ingest_season_results(season)
        except Exception as e:
            print(f"  season {season} failed: {e}, skipping")
        time.sleep(8)
    print("F1 ingestion complete.")