import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

SEASON = "2026"  # Understat names a season by its start year
THRESHOLD = 0.15
H = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}

league = requests.get(f"https://understat.com/getLeagueData/EPL/{SEASON}", headers=H, timeout=30).json()
finished = [m["id"] for m in league["dates"] if m["isResult"]]

# Finished matches never change, so cache each one and only fetch new ones
cache = Path(f"data/raw/understat/{SEASON}")
cache.mkdir(parents=True, exist_ok=True)
shots = []
for mid in finished:
    f = cache / f"{mid}.json"
    if not f.exists():
        m = requests.get(f"https://understat.com/getMatchData/{mid}", headers=H, timeout=30).json()
        f.write_text(json.dumps(m["shots"]))
        time.sleep(0.5)  # be polite to Understat
    s = json.loads(f.read_text())
    shots += s["h"] + s["a"]

shots = pd.DataFrame(shots)
shots["xG"] = shots["xG"].astype(float)
shots["team"] = shots["h_team"].where(shots["h_a"] == "h", shots["a_team"])
big = shots[shots["xG"] > THRESHOLD]
pens = big["situation"] == "Penalty"

ranking = pd.DataFrame({
    "team": big.groupby("player")["team"].last(),
    "shots_015": big.groupby("player").size(),
    "excl_pens": big[~pens].groupby("player").size(),
    "xG_from_them": big.groupby("player")["xG"].sum().round(2),
}).fillna(0)

minutes = pd.DataFrame(league["players"]).set_index("player_name")["time"].astype(int)
ranking["per90"] = (ranking["shots_015"] / minutes.reindex(ranking.index) * 90).round(2)
ranking = ranking.sort_values(["shots_015", "xG_from_them"], ascending=False)

n = int(sys.argv[1]) if len(sys.argv) > 1 else 25
print(f"{len(finished)} matches, {len(shots)} shots, {len(big)} with xG > {THRESHOLD}\n")
print(ranking.head(n).to_string())
