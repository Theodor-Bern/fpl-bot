import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

FPL = "https://fantasy.premierleague.com/api"
UNDERSTAT = "https://understat.com"
SEASON = "2026"  # Understat names a season by its start year
HEADERS = {"User-Agent": "Mozilla/5.0"}
UNDERSTAT_HEADERS = {"X-Requested-With": "XMLHttpRequest"}  # without it Understat returns HTML
RAW = Path("data/raw")


def get_json(url, extra_headers=None):
    """GET url -> parsed JSON. Raise on HTTP error or a non-JSON reply."""
    r = requests.get(url, headers={**HEADERS, **(extra_headers or {})}, timeout=30)
    r.raise_for_status()
    # A site that is down or blocking us can answer 200 with an HTML page,
    # so raise_for_status passes and only the JSON parse fails
    try:
        return r.json()
    except ValueError:
        raise RuntimeError(f"{url} returned {r.headers.get('content-type')}, not JSON (site down or blocked?)") from None


def save(obj, path):
    """Write obj as JSON to path, creating parent folders."""
    path.parent.mkdir(parents=True, exists_ok=True)
    path.write_text(json.dumps(obj))
    


def fetch_fpl(run_dir):
    """bootstrap + fixtures + element-summary for players with minutes."""
    bootstrap = get_json(f"{FPL}/bootstrap-static/")
    save(bootstrap, run_dir / "bootstrap.json")
    save(get_json(f"{FPL}/fixtures/"), run_dir / "fixtures.json")
    
    #discard players with zero minutes, previous season history is handled later
    ids = [p["id"] for p in bootstrap["elements"] if p["minutes"] > 0]
    for i, pid in enumerate (ids, 1):
        save(get_json(f"{FPL}/element_summary/{pid}/"), run_dir / "element_summary" / f"{pid}.json")
        print(f"element_summary {i}/{len(ids)}", end="\r")
        time.sleep(0.3)
    print()
   


def fetch_understat(run_dir):
    """League data per run + match shots cached forever."""
    
    league = get_json(f"{UNDERSTAT}/getLeagueData/EPL/{SEASON}", UNDERSTAT_HEADERS)
    save(league, run_dir / "understat_league.json")

    # Finished matches never change, so the cache lives outside the run folder
    # and only new matches are fetched
    cache = RAW / "understat" / SEASON
    new = [m["id"] for m in league["dates"] if m["isResult"] and not (cache / f"{m['id']}.json").exists()]
    for i, mid in enumerate(new, 1):
        match = get_json(f"{UNDERSTAT}/getMatchData/{mid}", UNDERSTAT_HEADERS)
        save(match["shots"], cache / f"{mid}.json")
        print(f"understat match {i}/{len(new)}", end="\r")
        time.sleep(0.5)  # be polite to Understat
    print(f"understat: {len(new)} new matches")


if __name__ == "__main__":
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RAW / ts
    fetch_fpl(run_dir)  # no try: without FPL data there is nothing to build
    try:
        fetch_understat(run_dir)
    except (requests.RequestException, RuntimeError) as e:
        print(f"Understat skipped: {e}")
    print(f"Saved to {run_dir}")
