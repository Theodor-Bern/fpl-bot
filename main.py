import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests



URL = "https://fantasy.premierleague.com/api/bootstrap-static/"

r = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/",
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
r.raise_for_status()
data = r.json()

#Save a raw dir, timestamped snapshot
raw_dir=Path("data/raw/bootstrap")
raw_dir.mkdir(parents=True, exist_ok=True)
ts=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
(raw_dir / f"{ts}.json").write_text(json.dumps(data))

players = pd.DataFrame(data["elements"])
teams = pd.DataFrame(data["teams"])[["id", "short_name"]]
positions = pd.DataFrame(data["element_types"])[["id", "singular_name_short"]]

players = (
    players
    .merge(teams, left_on="team", right_on="id", suffixes=("", "_team"))
    .merge(positions, left_on="element_type", right_on="id", suffixes=("", "_pos"))
)
players["price"] = players["now_cost"] / 10

cols = ["web_name", "short_name", "singular_name_short", "price", "total_points", "minutes"]
print(players[cols].sort_values("total_points", ascending=False).head(15))
